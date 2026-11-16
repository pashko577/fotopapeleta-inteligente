"""Análisis continuo de una cámara de tránsito mientras alguien la está mirando en el panel.

Un hilo lector vacía el stream HLS en un búfer corto; otro hilo, con YOLOv8s + ByteTrack cargados, toma 15 cuadros
por segundo de ese búfer al ritmo real del video (con ~3 s de colchón, porque HLS llega en ráfagas de ~2 s) y:
  * publica cada cuadro con los vehículos marcados (el navegador lo ve como video MJPEG),
  * calcula al momento «visibles a la vez» (últimos 5 s) y «veh/min» (últimos 60 s, ventana deslizante),
  * guarda una Medicion cada 2 minutos (no cada cuadro: así «lo normal», la mediana de las últimas 30, sigue
    describiendo ~1 hora de tráfico).
Las ventanas se miden en tiempo DE VIDEO (cuadros / fps), no de reloj: al conectarse, el stream HLS entrega de golpe
los segmentos que tenía en búfer y con tiempo de reloj el veh/min saldría inflado.
Si nadie mira la cámara (ni el video ni los datos) durante 20 s, el hilo se detiene solo. Si dos personas miran la
misma cámara, comparten el mismo hilo.
"""
import statistics
import threading
import time
from collections import deque
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import close_old_connections, connection
from django.utils import timezone

from .models import Medicion
from .servicios import CLASES, CONF_MIN, IMGSZ, MIN_SEGUNDOS, StreamNoDisponible, _anotar

CUADROS_POR_SEGUNDO = 15   # cuadros que se analizan y se muestran por segundo de video (yolov8s a 1280: ~15 ms c/u)
VENTANA_VISIBLES = 5       # s: promedio de vehículos a la vez
VENTANA_FLUJO = 60         # s: vehículos distintos en movimiento -> veh/min
MIN_VENTANA_FLUJO = 10     # s: con menos video, el veh/min aún no es confiable
GUARDAR_CADA = 120         # s entre mediciones guardadas en la base
DEMORA = 3                 # s de colchón: más que un segmento HLS (~2 s), para que el siguiente llegue a tiempo
MAX_ATRASO = 6             # s: si se acumula más video sin mostrar, se salta hacia adelante
BUFER_MAX = 8              # s de video que guarda el lector como máximo (seguro; normalmente no se alcanza)
ANCHO_ANALISIS = 1280      # px: los cuadros se achican al leerlos (se detecta a IMGSZ=1280 igual) y ocupan menos
ANCHO_VIDEO = 960         # px del MJPEG que se envía al navegador (las cámaras llegan en 1080p: ~220 KB por cuadro)
INACTIVO = 20              # s sin nadie mirando -> se detiene
REINTENTOS = 3             # cortes seguidos del stream antes de rendirse
RECORDAR_ERROR = 30        # s que se muestra el error antes de volver a intentar

_activos = {}
_candado = threading.Lock()


def obtener(camara):
    """Analizador de la cámara (lo arranca si no hay uno corriendo) y marca que alguien la está mirando."""
    with _candado:
        a = _activos.get(camara.codigo)
        reciente_con_error = a is not None and a.error and time.monotonic() - a.fin < RECORDAR_ERROR
        if a is None or (not a.is_alive() and not reciente_con_error):
            a = Analizador(camara)
            _activos[camara.codigo] = a
            a.start()
        a.tocar()
        return a


class Analizador(threading.Thread):
    def __init__(self, camara):
        super().__init__(daemon=True, name=f"transito-{camara.codigo}")
        self.camara = camara
        self.estado = "conectando"          # conectando | analizando | detenido
        self.error = None
        self.fin = 0.0
        self.ultimo_acceso = time.monotonic()
        self._cuadro = threading.Condition()
        self._jpg, self._n = None, 0
        self._datos = threading.Lock()
        self._visibles = deque()            # (t, vehículos en el cuadro)
        self._conteos = deque()             # (t, clase) cuando una pista cuenta como vehículo en movimiento
        self._desde = None                  # t (s de video) del primer cuadro analizado
        self._t = 0.0                       # t (s de video) del último cuadro analizado

    # -------------------------------------------------------------- uso desde las vistas
    def tocar(self):
        self.ultimo_acceso = time.monotonic()

    def resumen(self):
        with self._datos:
            ahora = self._t
            vis = [n for t, n in self._visibles if ahora - t <= VENTANA_VISIBLES]
            clases = [c for t, c in self._conteos if ahora - t <= VENTANA_FLUJO]
        ventana = min(VENTANA_FLUJO, ahora - self._desde) if self._desde is not None else 0
        listo = ventana >= MIN_VENTANA_FLUJO
        return {"estado": self.estado, "error": self.error,
                "en_cuadro": round(statistics.mean(vis), 1) if vis else None,
                "por_minuto": round(len(clases) / ventana * 60, 1) if listo else None,
                "ventana": round(ventana),
                "por_clase": {n: clases.count(n) for n in CLASES.values()} if listo else None}

    def cuadros(self):
        """Generador multipart/x-mixed-replace (MJPEG): un JPEG por cada cuadro analizado."""
        visto = -1
        while True:
            with self._cuadro:
                self._cuadro.wait_for(lambda: self._n != visto or not self.is_alive(), timeout=10)
                if not self.is_alive() and self._n == visto:
                    return
                jpg, visto = self._jpg, self._n
            self.tocar()
            if jpg:
                yield (b"--cuadro\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode()
                       + b"\r\n\r\n" + jpg + b"\r\n")

    # -------------------------------------------------------------- hilo
    def run(self):
        try:
            self._bucle()
        except ImportError:
            self.error = "Falta el entorno de ML (requirements-ml.txt) para analizar el video."
        except StreamNoDisponible as e:
            self.error = str(e)
        except Exception as e:  # noqa: BLE001 - que el panel muestre el motivo en vez de quedarse «conectando»
            self.error = f"El análisis en vivo se detuvo: {e}"[:200]
        finally:
            self.estado, self.fin = "detenido", time.monotonic()
            with self._cuadro:
                self._cuadro.notify_all()
            with _candado:
                if _activos.get(self.camara.codigo) is self and not self.error:
                    del _activos[self.camara.codigo]
            connection.close()

    def _abrir(self, cv2):
        cap = cv2.VideoCapture(self.camara.url)
        if not cap.isOpened():
            raise StreamNoDisponible(f"No se pudo abrir el stream de {self.camara.nombre}.")
        return cap

    def _leer(self, cv2, cap, compartido):
        """Hilo lector: vacía el stream sin parar y deja los cuadros en un búfer corto (máx. BUFER_MAX s de video).

        El servidor HLS no entrega un flujo parejo: manda segmentos de ~2 s que se decodifican de golpe y luego nada.
        El búfer absorbe esas ráfagas y el detector reproduce los cuadros a su ritmo real (ver _bucle). Si el búfer
        crece de más (al conectarse llega el video atrasado de una vez), se descartan los cuadros más viejos.
        """
        fps, leidos, fallos, ultimo_t = compartido["fps"], 0, 0, -1.0
        bufer, intervalo = compartido["bufer"], 1 / CUADROS_POR_SEGUNDO
        try:
            while not compartido["fin"]:
                ok, img = cap.read()
                if not ok:
                    fallos += 1
                    if fallos > REINTENTOS:
                        raise StreamNoDisponible(f"El stream de {self.camara.nombre} se cortó.")
                    cap.release()
                    time.sleep(1)
                    cap = self._abrir(cv2)
                    continue
                fallos, leidos = 0, leidos + 1
                t = leidos / fps  # segundos de video
                if t - ultimo_t < intervalo * 0.9:  # tope de CUADROS_POR_SEGUNDO aunque el video tenga más
                    continue
                ultimo_t = t
                if img.shape[1] > ANCHO_ANALISIS:
                    img = cv2.resize(img, (ANCHO_ANALISIS, round(img.shape[0] * ANCHO_ANALISIS / img.shape[1])),
                                     interpolation=cv2.INTER_AREA)
                with compartido["cond"]:
                    bufer.append((t, img))
                    while bufer and t - bufer[0][0] > BUFER_MAX:
                        bufer.popleft()
                    compartido["cond"].notify()
        except Exception as e:  # noqa: BLE001 - lo informa el hilo principal
            compartido["error"] = e
        finally:
            cap.release()
            with compartido["cond"]:
                compartido["fin"] = True
                compartido["cond"].notify()

    def _bucle(self):
        import cv2
        from ultralytics import YOLO

        modelo = YOLO(str(settings.FOTOPAPELETA["PESOS_COCO"]))  # propio: el seguimiento no mezcla cámaras
        cap = self._abrir(cv2)
        fps = cap.get(cv2.CAP_PROP_FPS)
        compartido = {"fps": fps if 1 <= fps <= 60 else 25, "bufer": deque(), "fin": False, "error": None,
                      "cond": threading.Condition()}
        bufer = compartido["bufer"]
        self._compartido = compartido  # para diagnóstico
        threading.Thread(target=self._leer, args=(cv2, cap, compartido), daemon=True,
                         name=f"{self.name}-lector").start()
        pistas = {}  # id -> [clase, cuadros, centro inicial, centro final, ancho, contada, t inicial, t último]
        periodo, reloj = None, None  # reloj: (instante real, segundo de video) con que se sincroniza la reproducción
        try:
            while time.monotonic() - self.ultimo_acceso < INACTIVO:
                with compartido["cond"]:
                    compartido["cond"].wait_for(lambda: compartido["fin"] or bufer, timeout=5)
                    if compartido["fin"]:
                        raise compartido["error"] or StreamNoDisponible(f"El stream de {self.camara.nombre} se cortó.")
                    if not bufer:
                        continue
                    # Al arrancar, o si la reproducción quedó muy atrás de lo último que llegó (el servidor manda el
                    # video atrasado de a pocos al conectarse), se salta hacia adelante dejando DEMORA s de colchón.
                    if reloj is None or bufer[-1][0] - bufer[0][0] > MAX_ATRASO:
                        while len(bufer) > 1 and bufer[-1][0] - bufer[0][0] > DEMORA:
                            bufer.popleft()
                        colchon = bufer[-1][0] - bufer[0][0]
                        reloj = (time.monotonic() + max(DEMORA - colchon, 0), bufer[0][0])
                    ahora, img = bufer.popleft()  # segundos de video, imagen
                # Reproduce al ritmo real del video: cada cuadro sale cuando le toca según el reloj, así el video
                # se ve parejo aunque HLS entregue segmentos de ~2 s de golpe.
                espera = reloj[0] + (ahora - reloj[1]) - time.monotonic()
                if espera > 0:
                    time.sleep(min(espera, DEMORA + 0.5))
                elif espera < -DEMORA:  # el stream se demoró (búfer vacío un rato): se vuelve a sincronizar
                    reloj = (time.monotonic(), ahora)
                periodo = periodo or self._nuevo_periodo(ahora)
                r = modelo.track(img, persist=True, classes=list(CLASES), conf=CONF_MIN, imgsz=IMGSZ,
                                 tracker="bytetrack.yaml", verbose=False)[0]
                nuevos = []
                if r.boxes.id is not None:
                    for i, c, (x, y, w, _) in zip(r.boxes.id.int().tolist(), r.boxes.cls.int().tolist(),
                                                  r.boxes.xywh.tolist()):
                        p = pistas.setdefault(i, [CLASES[c], 0, (x, y), (x, y), w, False, ahora, ahora])
                        p[1], p[3], p[4], p[7] = p[1] + 1, (x, y), max(p[4], w), ahora
                        (x0, y0) = p[2]
                        # misma regla que medir(), en tiempo: seguido >= MIN_SEGUNDOS y se movió >= 1/4 de su ancho
                        if (not p[5] and p[1] >= 3 and ahora - p[6] >= MIN_SEGUNDOS
                                and ((x - x0) ** 2 + (y - y0) ** 2) ** 0.5 >= 0.25 * p[4]):
                            p[5] = True
                            nuevos.append(p[0])
                if len(pistas) > 500:  # olvida pistas que no se ven hace 30 s
                    pistas = {i: p for i, p in pistas.items() if ahora - p[7] < 30}
                with self._datos:
                    self._desde = ahora if self._desde is None else self._desde
                    self._t = ahora
                    self._visibles.append((ahora, len(r.boxes)))
                    self._conteos.extend((ahora, c) for c in nuevos)
                    while self._visibles and ahora - self._visibles[0][0] > VENTANA_VISIBLES:
                        self._visibles.popleft()
                    while self._conteos and ahora - self._conteos[0][0] > VENTANA_FLUJO:
                        self._conteos.popleft()
                periodo["visibles"].append(len(r.boxes))
                for c in nuevos:
                    periodo["ids"][c] += 1
                vista = _anotar(r)
                if vista.shape[1] > ANCHO_VIDEO:
                    vista = cv2.resize(vista, (ANCHO_VIDEO, round(vista.shape[0] * ANCHO_VIDEO / vista.shape[1])),
                                       interpolation=cv2.INTER_AREA)
                ok, jpg = cv2.imencode(".jpg", vista, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ok:
                    with self._cuadro:
                        self._jpg, self._n = jpg.tobytes(), self._n + 1
                        self._cuadro.notify_all()
                self.estado = "analizando"
                if ahora - periodo["t"] >= GUARDAR_CADA:
                    self._guardar(periodo, ahora - periodo["t"], self._jpg)
                    periodo = self._nuevo_periodo(ahora)
        finally:
            with compartido["cond"]:  # el lector cierra el stream (es el único que lo usa)
                compartido["fin"] = True

    @staticmethod
    def _nuevo_periodo(t=0.0):
        return {"t": t, "inicio": timezone.now(), "visibles": [],
                "ids": {nombre: 0 for nombre in CLASES.values()}}

    def _guardar(self, periodo, duracion, jpg):
        if not periodo["visibles"] or duracion <= 0:
            return
        close_old_connections()
        m = Medicion(camara=self.camara, inicio=periodo["inicio"], segundos=round(duracion, 1),
                     cuadros=len(periodo["visibles"]), por_minuto=round(sum(periodo["ids"].values()) / duracion * 60, 1),
                     en_cuadro=round(statistics.mean(periodo["visibles"]), 1), **periodo["ids"])
        if jpg:  # como en medir(): solo se conserva la última imagen de cada cámara
            (Path(settings.MEDIA_ROOT) / "transito" / f"{self.camara.codigo}.jpg").unlink(missing_ok=True)
            m.imagen.save(f"{self.camara.codigo}.jpg", ContentFile(jpg), save=False)
        m.save()
