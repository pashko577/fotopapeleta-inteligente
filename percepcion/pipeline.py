"""Pipeline de percepción: cuadro -> detección de placa -> seguimiento -> OCR -> votación -> evento.

Una cámara produce cuadros; cada placa se sigue entre cuadros (por solapamiento de cajas) y
acumula lecturas. Cuando la placa deja de verse, se votan las lecturas y se emite UN evento
con el formato de la arquitectura (placa, cámara, hora, confianza, evidencia).

El detector y el lector se inyectan para poder probar la lógica sin GPU.
"""
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2

from .ocr import mostrar, votar

_id_evento = itertools.count(1)


@dataclass
class Deteccion:
    caja: tuple  # (x1, y1, x2, y2) en píxeles
    conf: float


@dataclass
class Pista:
    id: int
    caja: tuple
    lecturas: list = field(default_factory=list)  # [(texto, confianza)]
    primer_ts: datetime = None
    ultimo_ts: datetime = None
    perdidos: int = 0
    mejor_area: float = 0
    mejor_recorte: object = None
    mejor_cuadro: object = None
    mejor_caja: tuple = None
    conf_detector: float = 0


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area = lambda c: (c[2] - c[0]) * (c[3] - c[1])
    return inter / (area(a) + area(b) - inter + 1e-9)


class DetectorPlacas:
    """YOLOv8 entrenado para placas (ver docs/pruebas/04)."""

    def __init__(self, pesos, conf=0.5, dispositivo=None):
        from ultralytics import YOLO
        self.modelo, self.conf, self.dispositivo = YOLO(str(pesos)), conf, dispositivo

    def detectar(self, img):
        r = self.modelo(img, conf=self.conf, device=self.dispositivo, verbose=False)[0]
        return [Deteccion(tuple(map(float, c)), float(p)) for c, p in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist())]


class PipelineCamara:
    """Procesa los cuadros de UNA cámara y emite eventos por placa."""

    def __init__(self, detector, lector, camara_id, iou_min=0.3, max_perdidos=5, min_lecturas=2,
                 margen=0.10, carpeta_evidencia=None, modelo_info=None, conf_min=0.5, ventana_repetida_s=5):
        self.detector, self.lector, self.camara_id = detector, lector, camara_id
        self.iou_min, self.max_perdidos, self.min_lecturas, self.margen = iou_min, max_perdidos, min_lecturas, margen
        self.carpeta = Path(carpeta_evidencia) if carpeta_evidencia else None
        self.modelo_info = modelo_info or {}
        self.pistas, self._ids = [], itertools.count(1)
        self.descartadas = 0  # pistas cuyas lecturas no llegaron a una placa válida o confiable
        self.repetidas = 0    # la misma placa ya emitida hace poco (el seguimiento se cortó y retomó)
        # conf_min: una pista que mezcla dos objetos vota una placa que casi ninguna lectura respalda (confianza ~0)
        self.conf_min, self.ventana_repetida_s, self._emitidas = conf_min, ventana_repetida_s, {}
        # Placas que el detector vio pero el OCR no pudo leer: se guardan para que una persona las escriba
        self.no_leidas, self.ancho_min_no_leida, self.max_no_leidas = [], 25, 8
        self._buffer_no_leidas = 40  # se filtran al final (revisar_no_leidas): los fragmentos se conocen al terminar

    def _recortar(self, img, caja):
        x1, y1, x2, y2 = caja
        mx, my = (x2 - x1) * self.margen, (y2 - y1) * self.margen
        h, w = img.shape[:2]
        return img[max(int(y1 - my), 0):min(int(y2 + my), h), max(int(x1 - mx), 0):min(int(x2 + mx), w)]

    def procesar_cuadro(self, img, ts):
        """Procesa un cuadro y devuelve los eventos de las placas que dejaron de verse."""
        dets = self.detector.detectar(img)
        libres = set(range(len(dets)))
        for p in self.pistas:  # asociar cada pista con la detección más solapada
            mejor = max(libres, key=lambda i: iou(p.caja, dets[i].caja), default=None)
            if mejor is not None and iou(p.caja, dets[mejor].caja) >= self.iou_min:
                libres.discard(mejor)
                self._actualizar(p, img, dets[mejor], ts)
            else:
                p.perdidos += 1
        for i in libres:
            p = Pista(next(self._ids), dets[i].caja, primer_ts=ts)
            self.pistas.append(p)
            self._actualizar(p, img, dets[i], ts)
        cerradas = [p for p in self.pistas if p.perdidos > self.max_perdidos]
        self.pistas = [p for p in self.pistas if p.perdidos <= self.max_perdidos]
        return [e for e in (self._emitir(p) for p in cerradas) if e]

    def finalizar(self):
        eventos = [e for e in (self._emitir(p) for p in self.pistas) if e]
        self.pistas = []
        return eventos

    def _actualizar(self, p, img, det, ts):
        recorte = self._recortar(img, det.caja)
        p.lecturas.append(self.lector.leer(recorte))
        p.caja, p.ultimo_ts, p.perdidos = det.caja, ts, 0
        area = (det.caja[2] - det.caja[0]) * (det.caja[3] - det.caja[1])
        if area > p.mejor_area:  # evidencia: el cuadro donde la placa se ve más grande
            p.mejor_area, p.mejor_recorte, p.mejor_cuadro, p.mejor_caja, p.conf_detector = area, recorte, img, det.caja, det.conf

    def _no_leida(self, p, motivo, sugerencia="", clave=""):
        """Guarda la pista descartada (las más grandes, hasta max_no_leidas) para revisión humana."""
        self.descartadas += 1
        if p.mejor_caja is None or p.mejor_caja[2] - p.mejor_caja[0] < self.ancho_min_no_leida:
            return  # demasiado pequeña: ni una persona la leería
        cuadro = p.mejor_cuadro.copy()
        x1, y1, x2, y2 = map(int, p.mejor_caja)
        cv2.rectangle(cuadro, (x1, y1), (x2, y2), (11, 158, 245), 2)
        self.no_leidas.append({"recorte": p.mejor_recorte, "cuadro": cuadro, "ancho": x2 - x1, "ts": p.ultimo_ts,
                               "lecturas": len(p.lecturas), "motivo": motivo, "sugerencia": sugerencia, "clave": clave,
                               "conf_detector": round(p.conf_detector, 3)})
        self.no_leidas.sort(key=lambda d: d["ancho"], reverse=True)
        del self.no_leidas[self._buffer_no_leidas:]

    def revisar_no_leidas(self):
        """Placas no leídas que vale la pena mostrar a una persona.

        Quita los fragmentos de una placa que sí se emitió (el seguimiento se cortó y quedó una pista corta con la
        misma lectura) y las repetidas entre sí; deja las más grandes, hasta max_no_leidas.
        """
        vistas, salida, sin_lectura = set(), [], []
        for n in self.no_leidas:  # ya vienen ordenadas de mayor a menor ancho
            if not n["clave"]:
                # Sin ninguna lectura no se puede comparar el texto: las pistas sin lectura a menos de 2 s de una más
                # grande se toman como el mismo objeto partido por el seguimiento.
                cerca = any(abs((n["ts"] - t).total_seconds()) <= 2 for t in sin_lectura)
                sin_lectura.append(n["ts"])  # también las agrupadas: el objeto puede durar más de 2 s en pantalla
                if cerca:
                    self.repetidas += 1
                    continue
            if n["clave"]:
                previa = self._emitidas.get(n["clave"])
                if (previa and abs((n["ts"] - previa).total_seconds()) <= self.ventana_repetida_s) or n["clave"] in vistas:
                    self.repetidas += 1
                    continue
                vistas.add(n["clave"])
            salida.append(n)
        return salida[:self.max_no_leidas]

    def _emitir(self, p):
        placa, n_validas = votar(p.lecturas)
        if not placa or n_validas < self.min_lecturas:
            self._no_leida(p, "El OCR no obtuvo una lectura válida" if not placa else "Muy pocas lecturas coincidentes",
                           mostrar(placa) if placa else "", placa)
            return None
        conf = sum(c for t, c in p.lecturas if t == placa) / max(sum(1 for t, _ in p.lecturas if t == placa), 1)
        if conf < self.conf_min:
            self._no_leida(p, "Lectura poco confiable", mostrar(placa), placa)
            return None
        previa = self._emitidas.get(placa)
        if previa and abs((p.ultimo_ts - previa).total_seconds()) <= self.ventana_repetida_s:
            self.repetidas += 1
            return None
        self._emitidas[placa] = p.ultimo_ts
        evento_id = f"EV-{p.primer_ts:%Y%m%d}-{next(_id_evento):06d}"
        evidencia = []
        if self.carpeta is not None:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            cuadro = p.mejor_cuadro.copy()
            x1, y1, x2, y2 = map(int, p.mejor_caja)
            cv2.rectangle(cuadro, (x1, y1), (x2, y2), (11, 158, 245), 2)
            cv2.putText(cuadro, f"{mostrar(placa)} {self.camara_id} {p.ultimo_ts:%H:%M:%S}", (x1, max(y1 - 8, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (11, 158, 245), 2)
            for nombre, im in ((f"{evento_id}_cuadro.jpg", cuadro), (f"{evento_id}_placa.jpg", p.mejor_recorte)):
                cv2.imwrite(str(self.carpeta / nombre), im)
                evidencia.append(nombre)
        return {"evento_id": evento_id, "placa": mostrar(placa), "placa_confianza": round(conf, 3),
                "lecturas_votadas": n_validas, "lecturas_totales": len(p.lecturas),
                "lecturas": [t or "-" for t, _ in p.lecturas],
                "camara_id": self.camara_id, "timestamp": p.ultimo_ts.isoformat(),
                "conf_detector": round(p.conf_detector, 3), "evidencia": evidencia, "modelo": self.modelo_info}
