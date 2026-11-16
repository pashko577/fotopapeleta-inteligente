"""Panel → Red → Tránsito en vivo: mapa real, video en vivo, conteo de vehículos y ruta más rápida con A*."""
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from panel.utilidades import requiere

from . import en_vivo
from .models import CamaraTransito, Medicion, TramoTransito
from .servicios import NIVELES, StreamNoDisponible, congestion, medir, ruta


def _camaras():
    lista = list(CamaraTransito.objects.filter(activa=True).order_by("lat"))  # de norte a sur
    for c in lista:
        c.estado = congestion(c)
    return lista


def _mapa(camaras):
    return {"camaras": [{"codigo": c.codigo, "nombre": c.nombre, "distrito": c.distrito, "lat": c.lat, "lon": c.lon,
                         "nivel": c.estado["nivel"],
                         "por_minuto": c.estado["actual"].por_minuto if c.estado["actual"] else None} for c in camaras],
            "tramos": [{"de": t.origen_id, "a": t.destino_id, "km": t.km, "min": t.minutos_libre, "corredor": t.corredor,
                        "geo": t.geometria} for t in TramoTransito.objects.all()]}


def _detalle(codigo):
    c = get_object_or_404(CamaraTransito, codigo=codigo)
    c.estado = congestion(c)
    historial = list(Medicion.objects.filter(camara=c, error="").order_by("-inicio")[:12])[::-1]
    maximo = max([m.en_cuadro for m in historial] + [1])
    return {"cam": c, "historial": [(m, m.en_cuadro / maximo * 100) for m in historial],
            "ultima": Medicion.objects.filter(camara=c).order_by("-inicio").first()}


@requiere()
def inicio(request):
    camaras = _camaras()
    sel = request.GET.get("camara")
    contexto = {"seccion": "transito", "camaras": camaras, "mapa": _mapa(camaras),
                "medidas": sum(1 for c in camaras if c.estado["actual"]),
                "detalle": _detalle(sel) if sel else None}
    return render(request, "transito/inicio.html", contexto)


@require_POST
@requiere()
def medir_ahora(request, codigo):
    c = get_object_or_404(CamaraTransito, codigo=codigo)
    error = None
    try:
        medir(c, segundos=10)
    except StreamNoDisponible as e:
        error = str(e)
    except ImportError:
        error = "Falta el entorno de ML (requirements-ml.txt) para analizar el video."
    return render(request, "transito/parciales/detalle.html", {**_detalle(codigo), "error": error})


@requiere()
def video(request, codigo):
    """Video MJPEG con los vehículos marcados, cuadro por cuadro (análisis continuo)."""
    a = en_vivo.obtener(get_object_or_404(CamaraTransito, codigo=codigo))
    r = StreamingHttpResponse(a.cuadros(), content_type="multipart/x-mixed-replace; boundary=cuadro")
    r["Cache-Control"] = "no-store"
    return r


@requiere()
def datos_en_vivo(request, codigo):
    """Cifras del análisis continuo; el panel las pide cada 5 s."""
    c = get_object_or_404(CamaraTransito, codigo=codigo)
    vivo = en_vivo.obtener(c).resumen()
    c.estado = congestion(c)
    nivel = c.estado["nivel"]
    if vivo["en_cuadro"] is not None and c.estado["tipico"]:  # mismo criterio que congestion(), con la cifra de ahora
        factor = min(max(vivo["en_cuadro"] / c.estado["tipico"], 1.0), 3.0)
        nivel = next(n for limite, n in NIVELES if factor < limite)
    historial = list(Medicion.objects.filter(camara=c, error="").order_by("-inicio")[:12])[::-1]
    maximo = max([m.en_cuadro for m in historial] + [1])
    return render(request, "transito/parciales/en_vivo.html", {
        "cam": c, "vivo": vivo, "nivel": nivel, "historial": [(m, m.en_cuadro / maximo * 100) for m in historial]})


@require_POST
@requiere()
def calcular_ruta(request):
    origen, destino = request.POST.get("origen"), request.POST.get("destino")
    r = ruta(origen, destino) if origen and destino and origen != destino else None
    nombres = dict(CamaraTransito.objects.values_list("codigo", "nombre"))
    return render(request, "transito/parciales/ruta.html", {"r": r, "nombres": nombres, "origen": origen, "destino": destino,
                                                             "pasos": [(c, nombres.get(c, c)) for c in (r["ruta"] if r else [])]})
