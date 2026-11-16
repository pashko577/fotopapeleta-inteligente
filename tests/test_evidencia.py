from datetime import datetime, timedelta

import pytest

from grafo import capturas_coherentes, misma_placa

T0 = datetime(2026, 10, 15, 8, 42, 0)
EVENTO = {"placa": "ABC-123", "camara": "AV-01", "ts": T0}


@pytest.mark.parametrize("otra, esperado", [("ABC-123", "confirmada"), ("abc 123", "confirmada"),
                                            ("A8C-123", "a_verificar"),   # confundible B/8
                                            ("ABC-128", "a_verificar"),   # un carácter distinto
                                            ("AXC-128", None),            # dos caracteres distintos
                                            ("ABC-1234", None),           # otra longitud
                                            ("D4F-582", None)])
def test_p8_coincidencia_de_placa(otra, esperado):
    assert misma_placa("ABC-123", otra) == esperado


def test_p7_filtro_temporal(g):
    # Ruta mínima AV-01 -> AV-12 = 6.8 km: en 1 min exigiría 408 km/h (> 200, imposible); en 10 min, 40.8 km/h.
    rapida = {"placa": "ABC-123", "camara": "AV-12", "ts": T0 + timedelta(minutes=1)}
    posible = {"placa": "ABC-123", "camara": "AV-12", "ts": T0 + timedelta(minutes=10)}
    assert capturas_coherentes(g, EVENTO, [rapida, posible]) == [(posible, "confirmada")]


def test_descarta_placas_distintas_y_camaras_lejanas(g):
    otra_placa = {"placa": "D4F-582", "camara": "AV-08", "ts": T0 + timedelta(minutes=5)}
    lejana = {"placa": "ABC-123", "camara": "PN-04", "ts": T0 + timedelta(minutes=30)}  # a 3 saltos
    dudosa = {"placa": "A8C-123", "camara": "AV-08", "ts": T0 + timedelta(minutes=5)}
    assert capturas_coherentes(g, EVENTO, [otra_placa, lejana, dudosa]) == [(dudosa, "a_verificar")]
