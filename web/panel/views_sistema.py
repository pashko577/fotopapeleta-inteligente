"""Panel administrativo — análisis y sistema: reportes, configuración y usuarios (A6, A7)."""
import json
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.shortcuts import redirect, render
from django.utils import timezone

from infracciones.models import Infraccion
from validacion.models import SolicitudRevision, Validacion

from .formularios import ParametrosForm
from .models import ParametrosSistema, parametros
from .utilidades import es_admin, infracciones_con_capturas, primera_captura, requiere

RESULTADOS = settings.RAIZ_REPO / "evaluacion" / "resultados"
PERIODOS = {"hoy": "Hoy", "7d": "7 días", "mes": "Mes"}
APROBADAS = {"emitida", "aprobada", "en_revision", "anulada"}


def _leer(nombre):
    try:
        return json.loads((RESULTADOS / nombre).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@requiere()
def reportes(request):
    periodo = request.GET.get("periodo", "mes")
    hoy = timezone.localdate()
    desde = {"hoy": hoy, "7d": hoy - timedelta(days=6)}.get(periodo, hoy.replace(day=1))
    infs = list(infracciones_con_capturas().filter(creada__date__gte=desde))
    vals = list(Validacion.objects.filter(fecha__date__gte=desde).select_related("infraccion"))
    dec = Counter(v.decision for v in vals)
    decididas = dec["aprobar"] + dec["rechazar"]
    tiempos = [(v.fecha - v.infraccion.creada).total_seconds() for v in vals if v.decision != "escalar"]
    medio = sum(tiempos) / len(tiempos) if tiempos else None

    # Infracciones por día, apiladas por resultado
    dias = [desde + timedelta(days=i) for i in range((hoy - desde).days + 1)]
    por_dia = Counter((timezone.localdate(i.creada), "aprobada" if i.estado in APROBADAS else i.estado) for i in infs)
    maximo = max([sum(v for (d, _), v in por_dia.items() if d == dia) for dia in dias] + [1])
    barras = [{"dia": d, "partes": [(e, por_dia[(d, e)], por_dia[(d, e)] / maximo * 100)
                                    for e in ("aprobada", "rechazada", "en_validacion") if por_dia[(d, e)]]} for d in dias]

    por_cam = Counter()
    aprob_cam = Counter()
    for i in infs:
        c = primera_captura(i)
        if c:
            por_cam[c.camara] += 1
            aprob_cam[c.camara] += i.estado in APROBADAS
    max_cam = max(por_cam.values(), default=1)

    det, ocr_s, ocr_r, bench = (_leer("detector_yolov8n_peru.json"), _leer("ocr_sintetico.json"),
                                _leer("ocr_real.json"), _leer("benchmark_grafo.json"))
    angulo_aprob = dec["aprobar"] / sum(dec.values()) * 360 if dec else 0
    angulo_rech = dec["rechazar"] / sum(dec.values()) * 360 if dec else 0
    return render(request, "panel/reportes.html", {
        "seccion": "reportes", "periodo": periodo, "periodos": PERIODOS, "desde": desde, "hoy": hoy,
        "total": len(infs), "tasa": dec["aprobar"] / decididas * 100 if decididas else None, "medio": medio,
        "revisiones": SolicitudRevision.objects.filter(creada__date__gte=desde).count(),
        "dec": dec, "n_decisiones": sum(dec.values()), "a1": angulo_aprob, "a2": angulo_aprob + angulo_rech,
        "barras": barras, "por_camara": [(c, n, n / max_cam * 100, aprob_cam[c] / n * 100) for c, n in por_cam.most_common()],
        "detector": det["resultados"]["test"] if det else None,
        "ocr_voto": ocr_s["resultados"]["media"]["extraccion"] if ocr_s else None,
        "ocr_real": ocr_r["resultados"]["autos_todas"]["extraccion"] if ocr_r else None,
        "bench": bench,
    })


@requiere()
def configuracion(request):
    admin = es_admin(request.user)
    actual = ParametrosSistema.objects.first()
    cfg = parametros()
    inicial = {"tolerancia_kmh": cfg["TOLERANCIA_KMH"], "error_reloj_s": cfg["ERROR_RELOJ_S"],
               "k_vecindario": cfg["K_VECINDARIO"], "velocidad_max_plausible_kmh": cfg["VELOCIDAD_MAX_PLAUSIBLE_KMH"]}
    if request.method == "POST":
        if not admin:
            return render(request, "panel/sin_permiso.html", {"mensaje": "Solo un administrador cambia los parámetros"}, status=403)
        if request.POST.get("accion") == "restablecer":
            ParametrosSistema.objects.all().delete()
            messages.success(request, "Parámetros restablecidos", extra_tags="Se usan los valores por defecto del sistema.")
            return redirect("panel:configuracion")
        form = ParametrosForm(request.POST, instance=actual)
        if form.is_valid():
            p = form.save(commit=False)
            p.actualizado_por = request.user
            p.save()
            messages.success(request, "Parámetros guardados", extra_tags="Se aplican a los próximos eventos.")
            return redirect("panel:configuracion")
    else:
        form = ParametrosForm(instance=actual, initial=None if actual else inicial)
    return render(request, "panel/configuracion.html", {
        "seccion": "configuracion", "form": form, "es_admin": admin, "actual": actual,
        "tab": "parametros" if request.method == "POST" else request.GET.get("tab", "preferencias"),
    })


PERMISOS = [  # (capacidad, permiso de Django) — la tabla se arma con los permisos reales de cada grupo
    ("Ver resumen, infracciones y reportes", "infracciones.view_infraccion"),
    ("Validar infracciones", "validacion.add_validacion"),
    ("Revisar alertas de captura imposible", "infracciones.change_alerta"),
    ("Anular papeletas", "validacion.change_papeleta"),
    ("Gestionar cámaras y tramos", "camaras.add_camara"),
    ("Reportar capturas (worker)", "infracciones.add_captura"),
    ("Configurar parámetros", "panel.change_parametrossistema"),
]


@requiere()
def usuarios(request):
    User = get_user_model()
    grupos = {g.name: {f"{p.content_type.app_label}.{p.codename}" for p in g.permissions.select_related("content_type")}
              for g in Group.objects.prefetch_related("permissions")}
    columnas = [g for g in ("administrador", "validador", "worker") if g in grupos]
    matriz = [(nombre, [perm in grupos[g] for g in columnas]) for nombre, perm in PERMISOS]
    lista = User.objects.prefetch_related("groups").order_by("-is_superuser", "username")
    return render(request, "panel/usuarios.html", {
        "seccion": "usuarios", "usuarios": lista, "columnas": columnas, "matriz": matriz,
        "es_admin": es_admin(request.user), "n_roles": len(columnas),
    })
