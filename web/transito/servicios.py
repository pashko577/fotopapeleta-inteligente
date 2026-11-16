"""Medición de tráfico con YOLOv8 (COCO) + seguimiento ByteTrack, congestión relativa y rutas con A*."""
import statistics
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

import grafo

from .models import CamaraTransito, Medicion, TramoTransito

CLASES = {2: "autos", 3: "motos", 5: "buses", 7: "camiones"}  # clases de COCO que son vehículos
VIGENCIA = timedelta(minutes=30)     # una medición más antigua ya no describe el tráfico actual
MIN_HISTORIAL = 5                    # mediciones necesarias para saber qué es «lo normal» en una cámara
CONF_MIN = 0.25                      # con yolov8s a 1280 px; con 0.4 se perdían los autos oscuros y en sombra
MIN_CUADROS = 5                      # medio segundo a 10 cuadros por segundo
MIN_SEGUNDOS = 0.5                   # lo mismo en tiempo (el análisis en vivo no tiene cuadros por segundo fijos)
IMGSZ = 1280                         # las cámaras miran la vía desde lejos: a 640 px los autos lejanos se pierden
NOMBRE = {"autos": "auto", "motos": "moto", "buses": "bus", "camiones": "camión"}
NIVELES = [(1.25, "fluido"), (1.6, "moderado"), (99, "congestionado")]


class StreamNoDisponible(Exception):
    pass


@transaction.atomic
def importar_red(datos):
    """Carga data/red_transito.json (validado con el mismo grafo.validar de la red de fiscalización)."""
    errores = grafo.validar({"nodos": datos["nodos"], "aristas": [{k: a[k] for k in ("de", "a", "km", "min")} for a in datos["aristas"]]})
    if errores:
        raise ValueError("; ".join(errores))
    for codigo, n in datos["nodos"].items():
        CamaraTransito.objects.update_or_create(codigo=codigo, defaults={
            "nombre": n["nombre"], "distrito": n["distrito"], "ubicacion": n.get("ubicacion", ""), "lat": n["lat"],
            "lon": n["lon"], "fuente_coordenadas": n.get("fuente_coordenadas", ""), "url": n["url"]})
    for a in datos["aristas"]:
        TramoTransito.objects.update_or_create(origen_id=a["de"], destino_id=a["a"], defaults={
            "km": a["km"], "minutos_libre": a["min"], "corredor": a.get("corredor", ""), "geometria": a.get("geometria", [])})
    return len(datos["nodos"]), len(datos["aristas"])


def medir(camara, segundos=8, cuadros_por_segundo=10):
    """Analiza unos segundos del stream: vehículos distintos EN MOVIMIENTO (por seguimiento) y los visibles a la vez.

    No lee placas (en estas cámaras miden 16-40 px, ilegibles: ver docs/pruebas/11).
    """
    import cv2
    from ultralytics import YOLO

    modelo = YOLO(str(settings.FOTOPAPELETA["PESOS_COCO"]))  # nuevo por medición: el seguimiento no mezcla cámaras
    inicio = timezone.now()
    cap = cv2.VideoCapture(camara.url)
    if not cap.isOpened():
        raise StreamNoDisponible(f"No se pudo abrir el stream de {camara.nombre}.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    paso = max(int(round(fps / cuadros_por_segundo)), 1)
    pistas = {}  # id -> [clase, cuadros, centro inicial, centro final, ancho]
    visibles, leidos, ultimo = [], 0, None
    limite = time.monotonic() + segundos * 4 + 15  # si el stream se corta, no esperar para siempre
    while leidos < segundos * fps and time.monotonic() < limite:
        ok, img = cap.read()
        if not ok:
            break
        if leidos % paso == 0:
            r = modelo.track(img, persist=True, classes=list(CLASES), conf=CONF_MIN, imgsz=IMGSZ, tracker="bytetrack.yaml",
                                 verbose=False)[0]
            visibles.append(len(r.boxes))
            if r.boxes.id is not None:
                for i, c, (x, y, w, _) in zip(r.boxes.id.int().tolist(), r.boxes.cls.int().tolist(), r.boxes.xywh.tolist()):
                    p = pistas.setdefault(i, [CLASES[c], 0, (x, y), (x, y), w])
                    p[1], p[3], p[4] = p[1] + 1, (x, y), max(p[4], w)
            ultimo = r
        leidos += 1
    cap.release()
    if not visibles:
        raise StreamNoDisponible(f"El stream de {camara.nombre} no entregó cuadros.")
    duracion = leidos / fps
    # Solo cuenta un vehículo seguido en >= MIN_CUADROS cuadros que se movió >= 1/4 de su ancho: así no se cuentan los
    # estacionados ni los fragmentos que deja el seguimiento cuando pierde un auto pequeño y le da otro id.
    ids = {nombre: 0 for nombre in CLASES.values()}
    for clase, n, (x0, y0), (x1, y1), w in pistas.values():
        if n >= MIN_CUADROS and ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 >= 0.25 * w:
            ids[clase] += 1
    unicos = sum(ids.values())
    m = Medicion(camara=camara, inicio=inicio, segundos=round(duracion, 1), cuadros=len(visibles),
                 por_minuto=round(unicos / duracion * 60, 1), en_cuadro=round(statistics.mean(visibles), 1),
                 **ids)
    ok, jpg = cv2.imencode(".jpg", _anotar(ultimo), [cv2.IMWRITE_JPEG_QUALITY, 75])
    if ok:  # solo se guarda la última imagen de cada cámara (se reemplaza en cada medición)
        anterior = Path(settings.MEDIA_ROOT) / "transito" / f"{camara.codigo}.jpg"
        anterior.unlink(missing_ok=True)
        m.imagen.save(f"{camara.codigo}.jpg", ContentFile(jpg.tobytes()), save=False)
    m.save()
    return m


def _anotar(r):
    """Última imagen con los vehículos marcados (ámbar del diseño, etiquetas en español)."""
    import cv2
    img = r.orig_img.copy()
    for (x1, y1, x2, y2), c in zip(r.boxes.xyxy.int().tolist(), r.boxes.cls.int().tolist()):
        cv2.rectangle(img, (x1, y1), (x2, y2), (11, 158, 245), 2)
        cv2.putText(img, NOMBRE[CLASES[c]], (x1, max(y1 - 5, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (11, 158, 245), 1, cv2.LINE_AA)
    return img


def congestion(camara, ahora=None):
    """Tráfico actual RELATIVO a lo normal en esa misma cámara (vehículos visibles a la vez).

    factor >= 1 multiplica el tiempo a flujo libre de sus tramos. Sin historial o sin dato reciente: factor 1.
    """
    ahora = ahora or timezone.now()
    ms = list(Medicion.objects.filter(camara=camara, error="").order_by("-inicio")[:30])
    if not ms or ahora - ms[0].inicio > VIGENCIA:
        return {"nivel": "sin datos", "factor": 1.0, "actual": ms[0] if ms else None, "tipico": None}
    if len(ms) < MIN_HISTORIAL:
        return {"nivel": "sin historial", "factor": 1.0, "actual": ms[0], "tipico": None}
    tipico = statistics.median(m.en_cuadro for m in ms)
    factor = min(max(ms[0].en_cuadro / tipico, 1.0), 3.0) if tipico else 1.0
    nivel = next(n for limite, n in NIVELES if factor < limite)
    return {"nivel": nivel, "factor": round(factor, 2), "actual": ms[0], "tipico": round(tipico, 1)}


def red(ahora=None):
    """(grafo con tiempos actuales, nodos, estado por cámara, vmax a flujo libre)."""
    camaras = {c.codigo: c for c in CamaraTransito.objects.filter(activa=True)}
    estado = {codigo: congestion(c, ahora) for codigo, c in camaras.items()}
    nodos = {codigo: {"lat": c.lat, "lon": c.lon, "nombre": c.nombre} for codigo, c in camaras.items()}
    aristas, vmax = [], 1.0
    for t in TramoTransito.objects.filter(origen__in=camaras, destino__in=camaras):
        f = (estado[t.origen_id]["factor"] + estado[t.destino_id]["factor"]) / 2
        aristas.append({"de": t.origen_id, "a": t.destino_id, "km": t.km, "min": round(t.minutos_libre * f, 2), "limite_kmh": None})
        vmax = max(vmax, t.km / (t.minutos_libre / 60))
    return grafo.construir({"nodos": nodos, "aristas": aristas}), nodos, estado, vmax


def ruta(origen, destino, ahora=None):
    """Ruta más rápida AHORA (A* con peso en minutos y heurística admisible) y la de flujo libre para comparar."""
    g, nodos, estado, vmax = red(ahora)
    h = grafo.recta_min(nodos, vmax_kmh=vmax)  # recta / velocidad máxima de la red: nunca sobreestima
    traza = []
    r = grafo.a_estrella(g, origen, destino, h=h, peso="min", traza=traza)
    if r.ruta is None:
        return None
    km = grafo.costo_ruta(g, r.ruta, peso="km")
    libre = sum(TramoTransito.objects.filter(origen_id__in=[a, b], destino_id__in=[a, b]).first().minutos_libre
                for a, b in zip(r.ruta, r.ruta[1:]))
    return {"ruta": r.ruta, "minutos": round(r.costo, 1), "minutos_libre": round(libre, 1), "km": round(km, 1),
            "explorados": r.explorados, "orden": traza, "estado": estado}
