from datetime import datetime, timedelta

from grafo import recta_km, velocidad_por_tramo

T0 = datetime(2026, 10, 15, 8, 42, 0)


def test_p5_exceso_de_velocidad(g, nodos):
    r = velocidad_por_tramo(g, "AV-01", T0, "AV-08", T0 + timedelta(seconds=120), recta_km(nodos))
    assert r.ruta == ["AV-01", "AV-08"] and r.km == 3.0
    assert (r.v_medida, r.v_conservadora, r.limite, r.exceso) == (90.0, 87.1, 60, 27.1)
    assert r.infraccion


def test_p6_sin_infraccion(g):
    r = velocidad_por_tramo(g, "AV-01", T0, "AV-08", T0 + timedelta(seconds=200))
    assert r.v_conservadora == 52.9
    assert not r.infraccion


def test_dentro_de_la_tolerancia_no_es_infraccion(g):
    # 3 km en 166 s + 4 s de margen = 63.5 km/h: supera 60, pero no 60 + 5.
    r = velocidad_por_tramo(g, "AV-01", T0, "AV-08", T0 + timedelta(seconds=166))
    assert 60 < r.v_conservadora < 65
    assert not r.infraccion


def test_tiempo_no_positivo_devuelve_none(g):
    assert velocidad_por_tramo(g, "AV-01", T0, "AV-08", T0) is None
