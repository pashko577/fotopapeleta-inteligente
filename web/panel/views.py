"""Panel administrativo — operación: resumen, validación, infracciones y papeletas (A1, A3, A4)."""
import csv
import re
from collections import Counter
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from camaras.models import Camara
from infracciones.models import Alerta, Captura, Infraccion
from validacion.models import Papeleta, Validacion
from validacion.servicios import TransicionInvalida, anular, validar

from .formularios import IngresoForm
from .grafo_svg import lienzo
from .templatetags.fp import NOMBRE_TIPO
from .utilidades import capturas_ordenadas, imagen, infracciones_con_capturas, primera_captura, requiere, resumen_fila

E = Infraccion.Estado


class IngresoView(auth_views.LoginView):
    """A0 · Inicio de sesión (acepta usuario o correo)."""
    template_name = "panel/ingreso.html"
    authentication_form = IngresoForm
    redirect_authenticated_user = True


def _dia_con_datos():
    """Hoy, o el último día con infracciones si hoy aún no hay (útil en la demo)."""
    hoy = timezone.localdate()
    if Infraccion.objects.filter(creada__date=hoy).exists():
        return hoy, True
    ultima = Infraccion.objects.order_by("-creada").first()
    return (timezone.localdate(ultima.creada), False) if ultima else (hoy, True)


@requiere()
def resumen(request):
    """A1 · ¿Cómo está la operación hoy?"""
    dia, es_hoy = _dia_con_datos()
    del_dia = list(Infraccion.objects.filter(creada__date=dia).only("tipo", "creada"))
    ayer = Infraccion.objects.filter(creada__date=dia - timedelta(days=1)).count()
    pendientes = Infraccion.objects.filter(estado=E.EN_VALIDACION).order_by("creada")
    decisiones = Counter(Validacion.objects.filter(fecha__gte=timezone.now() - timedelta(days=7))
                         .values_list("decision", flat=True))
    decididas = decisiones["aprobar"] + decisiones["rechazar"]
    camaras = list(Camara.objects.all())
    activas = sum(c.activa for c in camaras)

    # Infracciones por hora, apiladas por tipo (06:00 a 20:00 y las horas con datos fuera de ese rango)
    por_hora = Counter((timezone.localtime(i.creada).hour, i.tipo) for i in del_dia)
    horas = sorted(set(range(6, 21)) | {h for h, _ in por_hora})
    maximo = max([sum(v for (h2, _), v in por_hora.items() if h2 == h) for h in horas] + [1])
    tipos_presentes = [t for t in NOMBRE_TIPO if any(t == tt for _, tt in por_hora)]
    barras = []
    for h in horas:
        total = sum(por_hora[(h, t)] for t in NOMBRE_TIPO)
        barras.append({"hora": f"{h:02d}", "total": total, "alto": total / maximo * 100,
                       "partes": [(t, por_hora[(h, t)]) for t in NOMBRE_TIPO if por_hora[(h, t)]]})
    por_tipo = Counter(i.tipo for i in del_dia)
    max_tipo = max(por_tipo.values(), default=1)

    ultimas = dict(Captura.objects.values("camara_id").annotate(m=Max("timestamp")).values_list("camara_id", "m"))
    for c in camaras:
        c.ultima = ultimas.get(c.codigo)

    return render(request, "panel/resumen.html", {
        "seccion": "resumen", "dia": dia, "es_hoy": es_hoy,
        "kpi_hoy": len(del_dia), "kpi_variacion": (len(del_dia) - ayer) / ayer * 100 if ayer else None,
        "kpi_pendientes": pendientes.count(), "mas_antigua": pendientes.first(),
        "kpi_tasa": decisiones["aprobar"] / decididas * 100 if decididas else None, "kpi_decididas": decididas,
        "camaras": camaras, "camaras_activas": activas,
        "barras": barras, "tipos_presentes": tipos_presentes,
        "por_tipo": [(t, por_tipo[t], por_tipo[t] / max_tipo * 100) for t in NOMBRE_TIPO],
        "cola": [resumen_fila(i) for i in infracciones_con_capturas().filter(estado=E.EN_VALIDACION).order_by("creada")[:5]],
    })


# ---------------------------------------------------------------- A4 · Validación
ORDEN_COLA = {"antiguas": ("creada", "Más antiguas primero"), "recientes": ("-creada", "Más recientes primero")}


@requiere()
def validacion(request, pk=None):
    orden = request.GET.get("orden", "antiguas")
    cola_qs = infracciones_con_capturas().filter(estado=E.EN_VALIDACION).order_by(ORDEN_COLA.get(orden, ORDEN_COLA["antiguas"])[0])
    cola = [resumen_fila(i) for i in cola_qs]
    if orden == "confianza":
        cola.sort(key=lambda f: f["confianza"] or 0)
    puede_validar = request.user.has_perm("validacion.add_validacion")
    contexto = {"seccion": "validacion", "cola": cola, "orden": orden, "puede_validar": puede_validar,
                "ordenes": [("antiguas", "Más antiguas primero"), ("recientes", "Más recientes primero"),
                            ("confianza", "Menor confianza primero")]}
    if pk is None:
        if not cola:
            return render(request, "panel/validacion.html", contexto)
        actual = cola[0]["inf"]
    else:
        actual = get_object_or_404(infracciones_con_capturas(), pk=pk)

    ids = [f["inf"].pk for f in cola]
    pos = ids.index(actual.pk) if actual.pk in ids else None
    capturas = capturas_ordenadas(actual)
    try:
        activa = next(c for c in capturas if str(c.pk) == request.GET.get("c"))
    except StopIteration:
        activa = capturas[0] if capturas else None
    analisis = getattr(actual, "analisis", None)
    ruta = analisis.ruta if analisis else []
    contexto.update({
        "inf": actual, "capturas": capturas, "activa": activa,
        "img_activa": imagen(activa), "img_placa": imagen(activa, "placa"),
        "miniaturas": [(c, imagen(c), imagen(c, "placa")) for c in capturas],
        "analisis": analisis, "posicion": pos + 1 if pos is not None else None, "total": len(ids),
        "anterior": ids[pos - 1] if pos else None, "siguiente": ids[pos + 1] if pos is not None and pos + 1 < len(ids) else None,
        "mini_grafo": lienzo(ancho=360, alto=210, ruta=ruta, origen=ruta[0] if ruta else None,
                             destino=ruta[-1] if ruta else None, etiquetas=None, margen=34),
        "otras": Captura.objects.filter(placa_clave=activa.placa_clave).exclude(pk__in=[c.pk for c in capturas])
                 .select_related("camara")[:5] if activa else [],
        "validaciones": actual.validaciones.all(),
        "en_cola": actual.estado == E.EN_VALIDACION,
        "motivos_rechazo": ["La placa no es legible en ninguna captura", "Las capturas son de vehículos distintos",
                            "Error de hora en una cámara", "Vehículo de emergencia o exceptuado", "Otro"],
    })
    return render(request, "panel/validacion.html", contexto)


@require_POST
@requiere("validacion.add_validacion", "Tu rol no permite validar infracciones")
def decidir(request, pk):
    inf = get_object_or_404(Infraccion, pk=pk)
    decision = request.POST.get("decision")
    motivo = request.POST.get("motivo", "").strip()
    comentario = request.POST.get("comentario", "").strip()
    if motivo and comentario:
        motivo = f"{motivo}: {comentario}"
    else:
        motivo = motivo or comentario
    try:
        v, papeleta = validar(inf, request.user, decision, motivo=motivo,
                              placa_corregida=request.POST.get("placa_corregida", "").strip())
    except TransicionInvalida as e:
        messages.error(request, str(e))
        return redirect("panel:validacion_detalle", pk=pk)
    if papeleta:
        messages.success(request, f"{inf.codigo} aprobada", extra_tags=f"Papeleta {papeleta.numero} emitida.")
    elif decision == Validacion.Decision.RECHAZAR:
        messages.success(request, f"{inf.codigo} rechazada", extra_tags="El motivo quedó registrado en la auditoría.")
    else:
        messages.warning(request, f"{inf.codigo} escalada", extra_tags="Queda en la cola marcada para un administrador.")
    return redirect(reverse("panel:validacion") + (f"?orden={request.POST['orden']}" if request.POST.get("orden") else ""))


# ---------------------------------------------------------------- A3 · Infracciones
def _filtrar_infracciones(request):
    g = request.GET
    qs = infracciones_con_capturas().order_by("-creada")
    q = g.get("q", "").strip().upper()
    if q:
        m = re.fullmatch(r"INF-?0*(\d+)", q)
        qs = qs.filter(pk=int(m.group(1))) if m else qs.filter(placa__icontains=q.replace("-", ""))
    if g.get("tipo"):
        qs = qs.filter(tipo=g["tipo"])
    if g.get("estado"):
        qs = qs.filter(estado=g["estado"])
    if g.get("camara"):
        qs = qs.filter(capturas__camara_id=g["camara"]).distinct()
    if g.get("desde"):
        qs = qs.filter(creada__date__gte=g["desde"])
    if g.get("hasta"):
        qs = qs.filter(creada__date__lte=g["hasta"])
    return qs


@requiere()
def infracciones(request):
    qs = _filtrar_infracciones(request)
    pagina = Paginator(qs, 20).get_page(request.GET.get("p"))
    g = request.GET
    chips = []
    if g.get("q"):
        chips.append(("q", f"Búsqueda: {g['q']}"))
    if g.get("tipo"):
        chips.append(("tipo", f"Tipo: {NOMBRE_TIPO.get(g['tipo'], g['tipo'])}"))
    if g.get("estado"):
        chips.append(("estado", f"Estado: {dict(E.choices).get(g['estado'], g['estado'])}"))
    if g.get("camara"):
        chips.append(("camara", f"Cámara: {g['camara']}"))
    if g.get("desde") or g.get("hasta"):
        chips.append(("fechas", f"Fechas: {g.get('desde') or '…'} a {g.get('hasta') or '…'}"))
    contexto = {
        "seccion": "infracciones", "pagina": pagina, "filas": [resumen_fila(i) for i in pagina.object_list],
        "total": Infraccion.objects.count(), "pendientes": Infraccion.objects.filter(estado=E.EN_VALIDACION).count(),
        "filtrados": pagina.paginator.count, "chips": chips, "tipos": NOMBRE_TIPO.items(), "estados": E.choices,
        "camaras": Camara.objects.all(), "f": g,
    }
    plantilla = "panel/parciales/tabla_infracciones.html" if request.headers.get("HX-Request") else "panel/infracciones.html"
    return render(request, plantilla, contexto)


@requiere()
def exportar_infracciones(request):
    qs = _filtrar_infracciones(request)
    ids = [int(x) for x in request.GET.get("ids", "").split(",") if x.isdigit()]
    if ids:
        qs = qs.filter(pk__in=ids)
    r = HttpResponse(content_type="text/csv; charset=utf-8")
    r["Content-Disposition"] = f'attachment; filename="infracciones_{timezone.localdate():%Y%m%d}.csv"'
    r.write("﻿")  # Excel reconoce UTF-8
    w = csv.writer(r)
    w.writerow(["id", "placa", "tipo", "camara", "fecha_hora", "confianza", "estado", "km", "v_conservadora_kmh",
                "limite_kmh", "exceso_kmh", "version_grafo", "papeleta"])
    for i in qs:
        f, a = resumen_fila(i), getattr(i, "analisis", None)
        w.writerow([i.codigo, i.placa, i.get_tipo_display(), f["camara"].codigo if f["camara"] else "",
                    timezone.localtime(f["ts"]).strftime("%d/%m/%Y %H:%M:%S"), f["confianza"], i.get_estado_display(),
                    a.km if a else "", a.v_conservadora if a else "", a.limite if a else "", a.exceso if a else "",
                    a.version_grafo if a else "", getattr(getattr(i, "papeleta", None), "numero", "")])
    return r


def auditoria(inf):
    """Registro de auditoría derivado de lo que guarda el sistema (capturas, análisis, validaciones, papeleta)."""
    filas = []
    for n, c in enumerate(capturas_ordenadas(inf)):
        modelo = " · ".join(str(v) for v in (c.modelo or {}).values())
        filas.append((c.timestamp, "worker", "Worker de percepción", "Detectada" if n == 0 else "Captura adicional",
                      f"{c.camara_id} · {modelo} · {c.lecturas_votadas} de {c.lecturas_totales} lecturas".strip(" ·")))
    a = getattr(inf, "analisis", None)
    if a:
        filas.append((inf.creada, "sistema", "Módulo C (grafo)", "Analizada",
                      f"Grafo {a.version_grafo} · {a.algoritmo} {a.km:.1f} km · {a.v_conservadora:.1f} km/h conservadora"))
    for v in inf.validaciones.all():
        detalle = v.motivo or ("Placa corregida a " + v.placa_corregida if v.placa_corregida else "Sin correcciones de placa")
        accion = {"aprobar": "Aprobada", "rechazar": "Rechazada", "escalar": "Escalada"}[v.decision]
        filas.append((v.fecha, "persona", v.validador.get_full_name() or v.validador.username, accion, detalle))
    p = getattr(inf, "papeleta", None)
    if p:
        filas.append((p.emitida, "sistema", "Sistema", "Emitida", p.numero))
        for s in p.revisiones.all():
            filas.append((s.creada, "persona", "Ciudadano", f"Solicitud de revisión {s.codigo}", s.motivo))
        if p.anulada:
            filas.append((p.anulada, "persona", p.anulada_por.get_full_name() or p.anulada_por.username, "Anulada", p.motivo_anulacion))
    return sorted(filas, key=lambda f: f[0])


@requiere()
def infraccion_detalle(request, pk):
    inf = get_object_or_404(infracciones_con_capturas(), pk=pk)
    capturas = capturas_ordenadas(inf)
    a = getattr(inf, "analisis", None)
    ruta = a.ruta if a else []
    aprobacion = next((v for v in inf.validaciones.all() if v.decision == Validacion.Decision.APROBAR), None)
    return render(request, "panel/infraccion_detalle.html", {
        "seccion": "infracciones", "inf": inf, "analisis": a, "capturas": capturas,
        "miniaturas": [(c, imagen(c)) for c in capturas], "aprobacion": aprobacion,
        "papeleta": getattr(inf, "papeleta", None), "auditoria": auditoria(inf),
        "grafo": lienzo(ancho=900, alto=300, ruta=ruta, origen=ruta[0] if ruta else None,
                        destino=ruta[-1] if ruta else None, etiquetas="corta"),
        "puede_anular": request.user.has_perm("validacion.change_papeleta"),
    })


# ---------------------------------------------------------------- Papeletas
@requiere()
def papeletas(request):
    g = request.GET
    base = Papeleta.objects.select_related("infraccion").prefetch_related("revisiones", "infraccion__validaciones__validador")
    qs = base
    if g.get("estado"):
        qs = qs.filter(estado=g["estado"])
    q = g.get("q", "").strip().upper()
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(placa__icontains=q.replace("-", "")))
    if g.get("tipo"):
        qs = qs.filter(infraccion__tipo=g["tipo"])
    if g.get("desde"):
        qs = qs.filter(emitida__date__gte=g["desde"])
    if g.get("hasta"):
        qs = qs.filter(emitida__date__lte=g["hasta"])
    pagina = Paginator(qs, 20).get_page(g.get("p"))
    for p in pagina.object_list:
        p.validador = next((v.validador for v in p.infraccion.validaciones.all() if v.decision == "aprobar"), None)
        p.revision = next(iter(sorted(p.revisiones.all(), key=lambda s: s.creada, reverse=True)), None)
    conteo = Counter(base.values_list("estado", flat=True))
    return render(request, "panel/papeletas.html", {
        "seccion": "papeletas", "pagina": pagina, "f": g, "tipos": NOMBRE_TIPO.items(),
        "pestanas": [("", "Todas", sum(conteo.values()))] + [(k, n, conteo[k]) for k, n in
                                                              (("emitida", "Emitidas"), ("en_revision", "En revisión"), ("anulada", "Anuladas"))],
        "puede_anular": request.user.has_perm("validacion.change_papeleta"),
    })


@require_POST
@requiere("validacion.change_papeleta", "Tu rol no permite anular papeletas")
def anular_papeleta(request, numero):
    p = get_object_or_404(Papeleta, numero=numero)
    try:
        anular(p, request.user, request.POST.get("motivo", ""))
        messages.success(request, f"Papeleta {p.numero} anulada", extra_tags="El motivo quedó registrado en la auditoría.")
    except TransicionInvalida as e:
        messages.error(request, str(e))
    volver = request.POST.get("volver", "")
    return redirect(volver if url_has_allowed_host_and_scheme(volver, {request.get_host()}) else "panel:papeletas")


# ---------------------------------------------------------------- Topbar
@requiere()
def buscar(request):
    """Búsqueda global (Ctrl K): INF-…, FP-…, código de cámara o placa."""
    q = request.GET.get("q", "").strip().upper()
    if not q:
        return redirect("panel:infracciones")
    if m := re.fullmatch(r"INF-?0*(\d+)", q):
        return redirect("panel:infraccion", pk=int(m.group(1)))
    if q.startswith("FP-") and (p := Papeleta.objects.filter(numero=q).first()):
        return redirect("panel:infraccion", pk=p.infraccion_id)
    if Camara.objects.filter(codigo=q).exists():
        return redirect(reverse("panel:camaras") + f"?camara={q}")
    return redirect(reverse("panel:infracciones") + f"?q={q}")


@require_POST
@requiere("infracciones.change_alerta")
def alerta_revisada(request, pk):
    Alerta.objects.filter(pk=pk).update(revisada=True)
    volver = request.POST.get("volver", "")
    return redirect(volver if url_has_allowed_host_and_scheme(volver, {request.get_host()}) else "panel:resumen")


@require_POST
@requiere()
def tutorial_visto(request):
    """El navegador avisa que el usuario terminó o cerró la guía de una pantalla."""
    from .models import TutorialVisto
    for pantalla in filter(None, [request.POST.get("pantalla"), "bienvenida" if request.POST.get("primera") else None]):
        TutorialVisto.objects.get_or_create(usuario=request.user, pantalla=pantalla[:30])
    return HttpResponse(status=204)


@require_POST
@requiere()
def tutorial_reiniciar(request):
    from .models import TutorialVisto
    TutorialVisto.objects.filter(usuario=request.user).delete()
    messages.success(request, "Guías reiniciadas", extra_tags="Se volverán a mostrar al abrir cada pantalla.")
    return redirect("panel:resumen")
