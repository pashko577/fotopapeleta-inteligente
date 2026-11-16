"""Panel administrativo — red: cámaras, captura en vivo y laboratorio del grafo (A2, A5, A8)."""
import csv
import time
from datetime import datetime, timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Max
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

import grafo
from camaras.models import Camara, Tramo
from camaras.servicios import construir_grafo
from infracciones.models import Captura

from .contexto import WORKER_EN_LINEA
from .formularios import CamaraForm, SubidaForm
from .grafo_svg import lienzo
from .models import parametros
from .utilidades import imagen, requiere


def _estado_camaras():
    """{codigo: (estado, ultima_captura)}. Sin un latido del celular, «en línea» = capturó hace < 5 min."""
    ultimas = dict(Captura.objects.values("camara_id").annotate(m=Max("timestamp")).values_list("camara_id", "m"))
    ahora, res = timezone.now(), {}
    for c in Camara.objects.all():
        u = ultimas.get(c.codigo)
        reciente = u is not None and timedelta(0) <= ahora - u < WORKER_EN_LINEA  # una hora futura no cuenta
        estado = "offline" if not c.activa else "online" if reciente else None
        res[c.codigo] = (estado, u)
    return res


def _ultima_con_imagen(cam):
    return (Captura.objects.filter(camara=cam, evidencias__archivo__gt="").prefetch_related("evidencias")
            .order_by("-timestamp").first())


def _mapa_real(lista, seleccion):
    """Datos para el mapa de OpenStreetMap, solo si TODAS las cámaras activas tienen lat/lon reales."""
    activas = [c for c in lista if c.activa]
    if not activas or any(c.lat is None or c.lon is None or c.x_km is not None for c in activas):
        return None
    return {"seleccion": seleccion,
            "camaras": [{"codigo": c.codigo, "nombre": c.nombre, "lat": c.lat, "lon": c.lon, "estado": c.estado} for c in activas],
            "tramos": [{"de": t.origen_id, "a": t.destino_id, "km": t.km, "min": t.minutos, "limite": t.limite_kmh,
                        "fuente": t.fuente, "geo": t.geometria or [[t.origen.lat, t.origen.lon], [t.destino.lat, t.destino.lon]]}
                       for t in Tramo.objects.filter(origen__activa=True, destino__activa=True).select_related("origen", "destino")]}


@requiere()
def camaras(request):
    estados = _estado_camaras()
    sel = request.GET.get("camara")
    lista = list(Camara.objects.annotate(n=Count("capturas")))
    for c in lista:
        c.estado, c.ultima = estados[c.codigo]
    detalle = None
    if sel and (cam := next((c for c in lista if c.codigo == sel), None)):
        hoy = timezone.localdate()
        ultima = Captura.objects.filter(camara=cam).order_by("-timestamp").first()
        con_imagen = _ultima_con_imagen(cam)
        tramos = [(t.destino if t.origen_id == cam.codigo else t.origen, t)
                  for t in Tramo.objects.filter(origen=cam).select_related("destino")] + \
                 [(t.origen, t) for t in Tramo.objects.filter(destino=cam).select_related("origen")]
        detalle = {"cam": cam, "ultima": ultima, "imagen": imagen(con_imagen), "con_imagen": con_imagen,
                   "hoy": Captura.objects.filter(camara=cam, timestamp__date=hoy).count(),
                   "placas": Captura.objects.filter(camara=cam).values("placa").distinct().count(),
                   "tramos": tramos}
    form = CamaraForm(request.POST or None) if request.method == "POST" else CamaraForm()
    if request.method == "POST":
        if not request.user.has_perm("camaras.add_camara"):
            return render(request, "panel/sin_permiso.html", {"mensaje": "Tu rol no permite agregar cámaras"}, status=403)
        if form.is_valid():
            d = form.cleaned_data
            with transaction.atomic():
                cam = Camara.objects.create(codigo=d["codigo"], nombre=d["nombre"], x_km=d["x_km"], y_km=d["y_km"],
                                            url_stream=d["url_stream"])
                Tramo.objects.create(origen=cam, destino=d["vecino"], km=d["km"], minutos=d["minutos"],
                                     limite_kmh=d["limite_kmh"])
            messages.success(request, f"Cámara {cam.codigo} agregada", extra_tags="El grafo cambió de versión.")
            return redirect(reverse("panel:camaras") + f"?camara={cam.codigo}")
    return render(request, "panel/camaras.html", {
        "seccion": "camaras", "camaras": lista, "detalle": detalle, "form": form,
        "en_linea": sum(1 for c in lista if c.estado == "online"), "inactivas": sum(1 for c in lista if not c.activa),
        "mapa_real": _mapa_real(lista, sel),
        "mapa": lienzo(ancho=760, alto=460, estados={k: v[0] for k, v in estados.items()}, seleccion=sel,
                       etiquetas="corta", margen=70),
        "puede_agregar": request.user.has_perm("camaras.add_camara"),
    })


@requiere()
def captura(request):
    estados = _estado_camaras()
    tarjetas = []
    for c in Camara.objects.all():
        # La foto y la placa de la tarjeta salen de la misma captura (la última que tiene imagen)
        mostrada = _ultima_con_imagen(c) or Captura.objects.filter(camara=c).order_by("-timestamp").first()
        tarjetas.append({"cam": c, "estado": estados[c.codigo][0], "ultima": mostrada, "imagen": imagen(mostrada)})
    ultima = Captura.objects.order_by("-recibido").first()
    return render(request, "panel/captura.html", {
        "seccion": "captura", "tarjetas": tarjetas, "ultima": ultima,
        "activas": sum(1 for t in tarjetas if t["estado"] == "online"),
        "hoy": Captura.objects.filter(recibido__date=timezone.localdate()).count(),
        "lecturas": Captura.objects.select_related("camara")[:8],
    })


@requiere()
def lecturas(request):
    """Parcial HTMX: lecturas recientes (se refresca cada 5 s)."""
    return render(request, "panel/parciales/lecturas.html", {"lecturas": Captura.objects.select_related("camara")[:8]})


@requiere()
def captura_celular(request):
    """A8 · Página para el celular que actúa como cámara (vista previa con la cámara del navegador)."""
    return render(request, "panel/captura_celular.html", {"seccion": "captura", "camaras": Camara.objects.filter(activa=True)})


# ---------------------------------------------------------------- A5 · Laboratorio del grafo
def _ejecutar(g, nodos, p):
    alg, origen, destino, peso = p["algoritmo"], p["origen"], p["destino"], p["peso"]
    unidad = "km" if peso == "km" else "min"
    t0 = time.perf_counter()
    if alg == "bfs":
        k = p["k"]
        vis = grafo.bfs(g, origen, k)
        ms = (time.perf_counter() - t0) * 1000
        orden = {c: i + 1 for i, c in enumerate(vis)}
        niveles = {}
        for c, n in vis.items():
            if n:
                niveles.setdefault(n, []).append(c)
        texto = " · ".join(f"{', '.join(cs)} ({n})" for n, cs in sorted(niveles.items())) or "Sin vecinos"
        return {"ok": True, "titulo": f"BFS desde {origen} (k = {k})", "consulta": f"{origen}, k = {k}",
                "resultado": texto, "costo": None, "explorados": len(vis), "ms": ms, "config": f"k = {k}",
                "lienzo": {"origen": origen, "visitados": list(vis), "orden": orden},
                "resumen": f"{len(vis) - 1} cámaras candidatas a ≤ {k} saltos"}
    if alg == "dfs":
        rutas = grafo.dfs(g, origen, destino, max_prof=p["max_prof"], max_rutas=50)
        ms = (time.perf_counter() - t0) * 1000
        if not rutas:
            return {"ok": False, "error": f"No existe ruta entre {origen} y {destino}",
                    "detalle": f"Con max_prof = {p['max_prof']}, DFS no alcanza el destino. Aumenta la profundidad o elige otro par de cámaras."}
        costos = sorted((grafo.costo_ruta(g, r, peso), r) for r in rutas)
        mejor = costos[0][1]
        return {"ok": True, "titulo": f"DFS de {origen} a {destino}", "consulta": f"{origen} → {destino}",
                "resultado": f"{len(rutas)} rutas: " + " · ".join(f"{c:.1f} {unidad}" for c, _ in costos[:3]) + (" …" if len(costos) > 3 else ""),
                "costo": costos[0][0], "unidad": unidad, "explorados": len({n for r in rutas for n in r}), "ms": ms,
                "config": f"max_prof = {p['max_prof']}",
                "lienzo": {"origen": origen, "destino": destino, "ruta": mejor, "visitados": list({n for r in rutas for n in r})},
                "resumen": f"{len(rutas)} rutas simples · la más corta: {' → '.join(mejor)}"}
    h = grafo.nula
    if p["heuristica"]:
        h = grafo.recta_km(nodos) if peso == "km" else grafo.recta_min(nodos)
    traza = []
    r = grafo.a_estrella(g, origen, destino, h=h, peso=peso, traza=traza)
    ms = (time.perf_counter() - t0) * 1000
    config = ("recta (km)" if peso == "km" else "recta a 80 km/h") if p["heuristica"] else "h = 0 (Dijkstra)"
    if r.ruta is None:
        return {"ok": False, "error": f"No existe ruta entre {origen} y {destino}",
                "detalle": "El grafo no conecta ambas cámaras (revisa los tramos de un solo sentido)."}
    return {"ok": True, "titulo": f"A* de {origen} a {destino}", "consulta": f"{origen} → {destino}",
            "resultado": " → ".join(r.ruta), "costo": r.costo, "unidad": unidad, "explorados": r.explorados, "ms": ms,
            "config": config, "lienzo": {"origen": origen, "destino": destino, "ruta": r.ruta, "visitados": traza,
                                         "orden": {c: i + 1 for i, c in enumerate(traza)}},
            "resumen": f"Ruta mínima {r.costo:.1f} {unidad} · {r.explorados} nodos explorados"}


def _parametros_lab(datos, codigos):
    def entero(clave, defecto, minimo, maximo):
        try:
            return min(max(int(datos.get(clave, defecto)), minimo), maximo)
        except ValueError:
            return defecto
    origen = datos.get("origen") if datos.get("origen") in codigos else codigos[0]
    destino = datos.get("destino") if datos.get("destino") in codigos else codigos[min(1, len(codigos) - 1)]
    return {"algoritmo": datos.get("algoritmo") if datos.get("algoritmo") in ("astar", "bfs", "dfs") else "astar",
            "origen": origen, "destino": destino, "peso": "min" if datos.get("peso") == "min" else "km",
            "heuristica": datos.get("heuristica", "on" if not datos else "") == "on",
            "k": entero("k", 2, 1, 6), "max_prof": entero("max_prof", 6, 1, 12)}


def _contexto_lab(request, p, resultado=None):
    g, nodos, version = construir_grafo()
    lz = (resultado or {}).get("lienzo", {})
    n_tramos = Tramo.objects.filter(origen__activa=True, destino__activa=True).count()
    return {"seccion": "laboratorio", "p": p, "r": resultado, "version": version, "nodos": nodos,
            "n_camaras": len(nodos), "n_tramos": n_tramos,
            "corridas": request.session.get("lab_corridas", []),
            "lienzo": lienzo(ancho=760, alto=440, etiquetas="km" if n_tramos <= 8 else "corta", margen=80, **lz)}


@requiere()
def laboratorio(request):
    codigos = list(Camara.objects.filter(activa=True).values_list("codigo", flat=True))
    p = _parametros_lab({}, codigos) if codigos else None
    return render(request, "panel/laboratorio.html", _contexto_lab(request, p))


@require_POST
@requiere()
def laboratorio_ejecutar(request):
    g, nodos, _ = construir_grafo()
    codigos = list(nodos)
    p = _parametros_lab(request.POST, codigos)
    r = _ejecutar(g, nodos, p)
    if r["ok"]:
        nombre = {"astar": "A*", "bfs": "BFS", "dfs": "DFS"}[p["algoritmo"]]
        corridas = request.session.get("lab_corridas", [])
        corridas.insert(0, {"algoritmo": nombre, "consulta": r["consulta"], "resultado": r["resultado"],
                            "costo": f"{r['costo']:.1f} {r['unidad']}" if r["costo"] is not None else "—",
                            "explorados": r["explorados"], "ms": f"{r['ms']:.3f}", "config": r["config"]})
        request.session["lab_corridas"] = corridas[:12]
    return render(request, "panel/parciales/laboratorio_resultado.html", _contexto_lab(request, p, r))


@require_POST
@requiere()
def laboratorio_limpiar(request):
    request.session["lab_corridas"] = []
    return redirect("panel:laboratorio")


@requiere()
def laboratorio_csv(request):
    r = HttpResponse(content_type="text/csv; charset=utf-8")
    r["Content-Disposition"] = 'attachment; filename="laboratorio_grafo.csv"'
    r.write("﻿")
    w = csv.writer(r)
    w.writerow(["algoritmo", "consulta", "resultado", "costo", "nodos_explorados", "tiempo_ms", "configuracion"])
    for c in request.session.get("lab_corridas", []):
        w.writerow([c["algoritmo"], c["consulta"], c["resultado"], c["costo"], c["explorados"], c["ms"], c["config"]])
    return r


@require_POST
@requiere()
def laboratorio_velocidad(request):
    """Velocidad por tramo entre dos capturas (misma fórmula que usa la decisión)."""
    g, nodos, _ = construir_grafo()
    cfg = parametros()
    d = request.POST
    try:
        hoy = timezone.localdate()
        ta = datetime.combine(hoy, datetime.strptime(d["hora_a"], "%H:%M:%S").time())
        tb = datetime.combine(hoy, datetime.strptime(d["hora_b"], "%H:%M:%S").time())
        if tb < ta:
            tb += timedelta(days=1)
        v = grafo.velocidad_por_tramo(g, d["cam_a"], ta, d["cam_b"], tb, h=grafo.recta_km(nodos),
                                      error_reloj_s=cfg["ERROR_RELOJ_S"], tolerancia_kmh=cfg["TOLERANCIA_KMH"])
        km, kmh = grafo.velocidad_implicita(g, d["cam_a"], ta, d["cam_b"], tb)
        error = None if v else "No hay ruta entre esas cámaras o el tiempo no es positivo."
    except (KeyError, ValueError):
        v, kmh, error = None, None, "Escribe las horas como HH:MM:SS."
    return render(request, "panel/parciales/laboratorio_velocidad.html", {
        "v": v, "error": error, "segundos": (tb - ta).total_seconds() if v else None, "cfg": cfg,
        "imposible": v is not None and kmh is not None and kmh > cfg["VELOCIDAD_MAX_PLAUSIBLE_KMH"], "kmh_min": kmh})


# ---------------------------------------------------------------- Subir evidencia (foto o video)
@requiere("infracciones.add_captura", "Tu rol no permite registrar capturas")
def subir(request):
    from infracciones import subida

    contexto = {"seccion": "subir", "camaras": Camara.objects.filter(activa=True), "max_mb": SubidaForm.MAX_MB,
                "max_video": subida.MAX_SEGUNDOS_VIDEO}
    form = SubidaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            if d["placa_manual"]:
                foto = d["archivo"] if d["archivo"] and subida.tipo_archivo(d["archivo"].name) == "foto" else None
                filas = subida.registrar_manual(d["placa_manual"], d["camara"].codigo, d["fecha_hora"] or timezone.now(), foto)
                info = {"manual": True}
            else:
                filas, info = subida.procesar_subida(d["archivo"], d["camara"].codigo, d["fecha_hora"], d["usar_exif"])
        except subida.SinEntornoML as e:
            form.add_error(None, f"{e} Mientras tanto puedes escribir la placa a mano.")
        except ValueError as e:
            form.add_error("archivo", str(e))
        else:
            contexto.update(filas=filas, info=info, camara=d["camara"])
    contexto["form"] = form
    return render(request, "panel/subir.html", contexto)


@require_POST
@requiere("infracciones.add_captura", "Tu rol no permite registrar capturas")
def escribir_no_leida(request, token):
    """Parcial HTMX: una persona escribe la placa de un recorte que el OCR no leyó."""
    import re

    from infracciones import subida

    placa = request.POST.get("placa", "").strip().upper()
    try:
        n = subida.datos_no_leida(token)
    except (ValueError, OSError):
        return HttpResponse('<p class="text-[13px] text-danger">El recorte ya no está disponible.</p>')
    if not re.fullmatch(r"[A-Z0-9]{3}-?[0-9]{3}", placa):
        return render(request, "panel/parciales/no_leida.html", {"n": n, "error": "Usa el formato ABC-123.", "valor": placa})
    try:
        f = subida.registrar_no_leida(token, placa)
    except ValueError as e:
        return render(request, "panel/parciales/no_leida.html", {"n": n, "error": str(e), "valor": placa})
    return render(request, "panel/parciales/fila_subida.html", {"f": f})
