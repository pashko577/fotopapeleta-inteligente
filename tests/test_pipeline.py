"""Lógica del pipeline (seguimiento, votación, emisión) con detector y lector falsos, sin GPU."""
from datetime import datetime, timedelta

import numpy as np
import pytest

from percepcion.pipeline import Deteccion, PipelineCamara, iou

T0 = datetime(2026, 10, 15, 8, 42, 0)
IMG = np.zeros((480, 640, 3), np.uint8)


class DetectorGuion:
    """Devuelve, cuadro a cuadro, las cajas indicadas."""
    def __init__(self, cajas_por_cuadro):
        self.cuadros = iter(cajas_por_cuadro)

    def detectar(self, img):
        return [Deteccion(c, 0.9) for c in next(self.cuadros)]


class LectorGuion:
    def __init__(self, lecturas):
        self.lecturas = iter(lecturas)

    def leer(self, recorte):
        return next(self.lecturas)


def correr(cajas, lecturas, **kw):
    p = PipelineCamara(DetectorGuion(cajas), LectorGuion(lecturas), "AV-01", **kw)
    eventos = []
    for i in range(len(cajas)):
        eventos += p.procesar_cuadro(IMG, T0 + timedelta(seconds=0.2 * i))
    return eventos + p.finalizar(), p


def test_iou():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1)
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0


def test_una_placa_seguida_produce_un_evento_votado():
    cajas = [[(100 + 4 * i, 200, 180 + 4 * i, 240)] for i in range(5)]  # la placa se desplaza
    lecturas = [("V8D001", 0.9), ("VBD001", 0.5), ("V8D001", 0.8), ("", 0.0), ("V8D001", 0.7)]
    eventos, p = correr(cajas, lecturas)
    assert len(eventos) == 1
    e = eventos[0]
    assert e["placa"] == "V8D-001" and e["camara_id"] == "AV-01"
    assert e["lecturas_votadas"] == 4 and e["lecturas_totales"] == 5
    assert e["timestamp"] == (T0 + timedelta(seconds=0.8)).isoformat()


def test_dos_placas_a_la_vez_producen_dos_eventos():
    cajas = [[(50, 50, 120, 80), (400, 300, 470, 330)]] * 3
    lecturas = [("ABC123", 0.9), ("D9R052", 0.9)] * 3
    eventos, _ = correr(cajas, lecturas)
    assert sorted(e["placa"] for e in eventos) == ["ABC-123", "D9R-052"]


def test_placa_que_deja_de_verse_se_emite_antes_del_final():
    cajas = [[(100, 100, 180, 140)]] * 2 + [[]] * 7
    eventos, p = correr(cajas, [("T3P298", 0.9)] * 2, max_perdidos=5)
    assert len(eventos) == 1 and p.pistas == []


def test_sin_lecturas_suficientes_no_emite():
    cajas = [[(100, 100, 180, 140)]] * 3
    eventos, p = correr(cajas, [("", 0.0), ("ABC1", 0.4), ("T3P298", 0.9)], min_lecturas=2)
    assert eventos == [] and p.descartadas == 1


def test_pista_sin_lectura_confiable_no_se_emite():
    """Una pista que mezcla dos objetos vota una placa que ninguna lectura respalda (encontrado con un video real)."""
    cajas = [[(100, 200, 180, 240)]] * 4
    lecturas = [("ACO484", 0.3), ("AZO464", 0.2), ("ACO444", 0.3), ("ADO433", 0.2)]
    eventos, p = correr(cajas, lecturas)
    assert eventos == [] and p.descartadas == 1


def test_misma_placa_retomada_no_se_duplica():
    """Si el seguimiento se corta y la misma placa reaparece enseguida, es el mismo paso del vehículo."""
    cajas = [[(100, 200, 180, 240)]] * 3 + [[]] * 7 + [[(300, 200, 380, 240)]] * 3
    lecturas = [("ACO484", 0.95)] * 6
    eventos, p = correr(cajas, lecturas)
    assert [e["placa"] for e in eventos] == ["ACO-484"] and p.repetidas == 1


def test_placas_no_leidas_se_guardan_para_revision_humana():
    """El detector vio la placa pero el OCR no la leyó: queda el recorte para que una persona la escriba."""
    cajas = [[(100, 200, 180, 240), (10, 10, 20, 15)]] * 3   # una placa de 80 px y otra de 10 px
    eventos, p = correr(cajas, [("", 0.0)] * 6)
    assert eventos == [] and len(p.no_leidas) == 1          # la de 10 px es demasiado pequeña
    n = p.no_leidas[0]
    assert n["ancho"] == 80 and n["lecturas"] == 3 and n["recorte"].shape[:2] == (48, 96)  # con el 10 % de margen


def test_fragmentos_de_una_placa_emitida_no_se_piden_a_mano():
    """Con un video real, el seguimiento dejaba pistas cortas de la misma placa ya emitida: no se muestran."""
    cajas = [[(100, 200, 180, 240)]] * 3 + [[]] * 7 + [[(300, 200, 380, 240)]] + [[]] * 7 + [[(500, 300, 560, 330)]]
    lecturas = [("ACO484", 0.95)] * 3 + [("ACO484", 0.9)] + [("", 0.0)]
    eventos, p = correr(cajas, lecturas)
    assert [e["placa"] for e in eventos] == ["ACO-484"]
    restantes = p.revisar_no_leidas()
    assert [n["ancho"] for n in restantes] == [60]  # solo la placa sin lectura; el fragmento de ACO-484 se quita


def test_pistas_sin_lectura_del_mismo_objeto_se_agrupan():
    """La misma placa ilegible partida en varias pistas cercanas en el tiempo se muestra una sola vez (la más grande)."""
    cajas = ([[(100, 200, 160, 230)]] + [[]] * 7) * 3
    eventos, p = correr(cajas, [("", 0.0)] * 3)
    assert eventos == [] and len(p.no_leidas) == 3
    assert len(p.revisar_no_leidas()) == 1
