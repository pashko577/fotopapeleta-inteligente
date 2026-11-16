"""Subir evidencia desde el panel: una foto o un video de una cámara pasa por el MISMO pipeline del worker
(detector YOLOv8 + OCR con votación, percepcion/pipeline.py) y cada placa encontrada entra al sistema
con registrar_evento, igual que si llegara por la API.

Requiere el entorno de ML (requirements-ml.txt). Sin él, se puede registrar la placa escrita a mano.
"""
import hashlib
import json
import re
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.utils import timezone

from .models import Evidencia
from .servicios import registrar_evento

EXT_FOTO = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
EXT_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
CUADROS_POR_SEGUNDO = 30   # con menos, un auto rápido se mueve tanto entre cuadros que el seguimiento lo pierde
MAX_SEGUNDOS_VIDEO = 120

_modelos, _candado = None, threading.Lock()


class SinEntornoML(Exception):
    """Faltan PyTorch/Ultralytics/EasyOCR o los pesos del detector."""


def tipo_archivo(nombre):
    ext = Path(nombre).suffix.lower()
    return "foto" if ext in EXT_FOTO else "video" if ext in EXT_VIDEO else None


def modelos():
    """Detector y lector se cargan una sola vez por proceso (la primera subida tarda unos segundos más)."""
    global _modelos
    with _candado:
        if _modelos is None:
            pesos = Path(settings.FOTOPAPELETA["PESOS_DETECTOR"])
            if not pesos.exists():
                raise SinEntornoML(f"No se encontraron los pesos del detector en {pesos}.")
            try:
                from percepcion.ocr import LectorPlacas
                from percepcion.pipeline import DetectorPlacas
                import torch
                gpu = torch.cuda.is_available()
                _modelos = (DetectorPlacas(pesos), LectorPlacas(gpu=gpu), "GPU" if gpu else "CPU")
            except ImportError as e:
                raise SinEntornoML(f"Falta el entorno de ML ({e.name}). Instala requirements-ml.txt.") from e
    return _modelos


def fecha_exif(ruta):
    """Fecha y hora en que se tomó la foto (EXIF DateTimeOriginal), si la trae."""
    try:
        from PIL import Image
        with Image.open(ruta) as im:
            valor = im.getexif().get_ifd(0x8769).get(36867) or im.getexif().get(306)
        if valor:
            return timezone.make_aware(datetime.strptime(valor, "%Y:%m:%d %H:%M:%S"))
    except Exception:  # EXIF ausente o malformado: se usa la hora indicada
        return None
    return None


def analizar(ruta, camara_id, inicio, carpeta):
    """Corre el pipeline del worker sobre una foto o un video. Devuelve (eventos, info)."""
    import cv2
    from percepcion.pipeline import PipelineCamara

    detector, lector, dispositivo = modelos()
    info = {"dispositivo": dispositivo, "cuadros": 0}
    modelo = {"origen": "subida web", "detector": Path(settings.FOTOPAPELETA["PESOS_DETECTOR"]).parent.parent.name, "ocr": f"{lector.motor} + formato + votación"}
    if tipo_archivo(ruta) == "foto":
        img = cv2.imread(str(ruta))
        if img is None:
            raise ValueError("No se pudo leer la imagen.")
        p = PipelineCamara(detector, lector, camara_id, min_lecturas=1, carpeta_evidencia=carpeta, modelo_info=modelo)
        eventos = p.procesar_cuadro(img, inicio) + p.finalizar()
        info["cuadros"], info["no_leidas"] = 1, p.revisar_no_leidas()
        return eventos, info

    video = cv2.VideoCapture(str(ruta))
    if not video.isOpened():
        raise ValueError("No se pudo abrir el video (formato no soportado).")
    fps = video.get(cv2.CAP_PROP_FPS) or 30
    paso = max(int(round(fps / CUADROS_POR_SEGUNDO)), 1)
    p = PipelineCamara(detector, lector, camara_id, min_lecturas=2, carpeta_evidencia=carpeta, modelo_info=modelo)
    eventos, n = [], 0
    while True:
        ok, img = video.read()
        if not ok or n / fps > MAX_SEGUNDOS_VIDEO:
            break
        if n % paso == 0:
            eventos += p.procesar_cuadro(img, inicio + timedelta(seconds=n / fps))
            info["cuadros"] += 1
        n += 1
    video.release()
    info["segundos"] = round(n / fps, 1)
    eventos += p.finalizar()
    info["no_leidas"] = p.revisar_no_leidas()
    info["descartadas"], info["repetidas"] = p.descartadas, p.repetidas
    return eventos, info


def registrar(eventos, carpeta, archivo_original):
    """Pasa cada evento por registrar_evento y adjunta su evidencia. Devuelve una fila por placa."""
    filas = []
    for e in eventos:
        ts = e["timestamp"]  # el pipeline la emite en ISO (formato del JSON de la API)
        e = {**e, "timestamp": datetime.fromisoformat(ts) if isinstance(ts, str) else ts,
             "evento_id": f"WEB-{uuid.uuid4().hex[:12].upper()}",
             "modelo": {**e.get("modelo", {}), "archivo_original": archivo_original}}
        nombres_viejos = e.get("evidencia", [])
        e["evidencia"] = [n.replace(n.split("_")[0], e["evento_id"], 1) for n in nombres_viejos]
        captura, resumen, _ = registrar_evento(e)
        for ev, viejo in zip(Evidencia.objects.filter(captura=captura).order_by("pk"), nombres_viejos):
            img = Path(carpeta) / viejo
            if img.exists():
                datos = img.read_bytes()
                ev.sha256 = hashlib.sha256(datos).hexdigest()
                with open(img, "rb") as f:
                    ev.archivo.save(ev.nombre, File(f), save=True)
        filas.append({"captura": captura, **resumen})
    return filas


def procesar_subida(archivo, camara_id, inicio=None, usar_exif=True):
    """Guarda el archivo subido, lo analiza y registra las placas. Devuelve (filas, info)."""
    destino = Path(settings.MEDIA_ROOT) / "subidas" / timezone.localdate().strftime("%Y/%m")
    destino.mkdir(parents=True, exist_ok=True)
    original = destino / f"{uuid.uuid4().hex[:10]}{Path(archivo.name).suffix.lower()}"
    with open(original, "wb") as f:
        for trozo in archivo.chunks():
            f.write(trozo)
    info = {"exif": False}
    if usar_exif and tipo_archivo(original) == "foto" and (exif := fecha_exif(original)):
        inicio, info["exif"] = exif, True
    inicio = inicio or timezone.now()
    carpeta = Path(tempfile.mkdtemp(prefix="fp_subida_"))
    try:
        eventos, info_pipeline = analizar(original, camara_id, inicio, carpeta)
        relativo = str(original.relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
        filas = registrar(eventos, carpeta, relativo)
        info_pipeline["no_leidas"] = guardar_no_leidas(info_pipeline.get("no_leidas", []), camara_id, relativo)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    return filas, {**info, **info_pipeline, "inicio": inicio}


def registrar_manual(placa, camara_id, ts, archivo=None):
    """Placa escrita por una persona (sin entorno de ML o cuando el OCR no la leyó)."""
    e = {"evento_id": f"WEB-{uuid.uuid4().hex[:12].upper()}", "placa": placa, "camara_id": camara_id, "timestamp": ts,
         "placa_confianza": 1.0, "lecturas_votadas": 1, "lecturas_totales": 1, "conf_detector": None,
         "evidencia": [f"manual_cuadro{Path(archivo.name).suffix.lower()}"] if archivo else [],
         "modelo": {"origen": "manual (subida web): placa escrita por una persona"}}
    captura, resumen, _ = registrar_evento(e)
    if archivo:
        ev = captura.evidencias.get()
        ev.archivo.save(f"{e['evento_id']}_cuadro{Path(archivo.name).suffix.lower()}", archivo, save=True)
    return [{"captura": captura, **resumen}]


# ---------------------------------------------------------------- Placas detectadas que el OCR no leyó
CARPETA_NO_LEIDAS = "subidas/no_leidas"
TOKEN = re.compile(r"^[0-9a-f]{16}$")


def _ruta_no_leida(token):
    if not TOKEN.match(token or ""):
        raise ValueError("Recorte no válido.")
    return Path(settings.MEDIA_ROOT) / CARPETA_NO_LEIDAS / token


def guardar_no_leidas(no_leidas, camara_id, archivo_original):
    """Guarda el recorte y el cuadro de cada placa no leída; devuelve lo que muestra la pantalla."""
    import cv2

    carpeta = Path(settings.MEDIA_ROOT) / CARPETA_NO_LEIDAS
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = []
    for n in no_leidas:
        token = uuid.uuid4().hex[:16]
        base = carpeta / token
        alto = n["recorte"].shape[0]
        recorte = cv2.resize(n["recorte"], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC) if alto < 60 else n["recorte"]
        cv2.imwrite(f"{base}_placa.jpg", n["recorte"])
        cv2.imwrite(f"{base}_vista.jpg", recorte)  # ampliado solo para mostrarlo en pantalla
        cv2.imwrite(f"{base}_cuadro.jpg", n["cuadro"])
        datos = {"camara_id": camara_id, "ts": n["ts"].isoformat(), "ancho": n["ancho"], "motivo": n["motivo"],
                 "sugerencia": n["sugerencia"], "lecturas": n["lecturas"], "conf_detector": n["conf_detector"],
                 "archivo_original": archivo_original, "registrada": None}
        Path(f"{base}.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        salida.append({"token": token, **datos, "url": f"{settings.MEDIA_URL}{CARPETA_NO_LEIDAS}/{token}_vista.jpg",
                       "url_cuadro": f"{settings.MEDIA_URL}{CARPETA_NO_LEIDAS}/{token}_cuadro.jpg"})
    return salida


def registrar_no_leida(token, placa):
    """Una persona escribió la placa de un recorte que el OCR no leyó: entra como captura con esa evidencia."""
    base = _ruta_no_leida(token)
    meta = Path(f"{base}.json")
    if not meta.exists():
        raise ValueError("El recorte ya no está disponible.")
    datos = json.loads(meta.read_text(encoding="utf-8"))
    if datos["registrada"]:
        raise ValueError(f"Este recorte ya se registró como {datos['registrada']}.")
    evento_id = f"WEB-{uuid.uuid4().hex[:12].upper()}"
    e = {"evento_id": evento_id, "placa": placa, "camara_id": datos["camara_id"], "timestamp": datetime.fromisoformat(datos["ts"]),
         "placa_confianza": 1.0, "lecturas_votadas": 1, "lecturas_totales": 1, "conf_detector": datos["conf_detector"],
         "evidencia": [f"{evento_id}_cuadro.jpg", f"{evento_id}_placa.jpg"],
         "modelo": {"origen": "placa escrita por una persona sobre el recorte del detector (subida web)",
                    "ocr": f"no leída: {datos['motivo']}", "archivo_original": datos["archivo_original"]}}
    captura, resumen, _ = registrar_evento(e)
    for ev, sufijo in zip(captura.evidencias.order_by("pk"), ("cuadro", "placa")):
        img = Path(f"{base}_{sufijo}.jpg")
        if img.exists() and not ev.archivo:
            datos_img = img.read_bytes()
            ev.sha256 = hashlib.sha256(datos_img).hexdigest()
            with open(img, "rb") as f:
                ev.archivo.save(ev.nombre, File(f), save=True)
    datos["registrada"] = captura.evento_id
    meta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return {"captura": captura, **resumen}


def datos_no_leida(token):
    """Lo que necesita la tarjeta de un recorte no leído (para volver a mostrarla con un error)."""
    base = _ruta_no_leida(token)
    datos = json.loads(Path(f"{base}.json").read_text(encoding="utf-8"))
    return {"token": token, **datos, "url": f"{settings.MEDIA_URL}{CARPETA_NO_LEIDAS}/{token}_vista.jpg",
            "url_cuadro": f"{settings.MEDIA_URL}{CARPETA_NO_LEIDAS}/{token}_cuadro.jpg"}
