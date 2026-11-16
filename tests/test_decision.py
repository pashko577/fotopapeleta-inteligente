from datetime import datetime, timedelta

from grafo import evaluar_evento

T0 = datetime(2026, 10, 15, 8, 42, 0)


def cap(i, placa, camara, segundos):
    return {"id": i, "placa": placa, "camara": camara, "ts": T0 + timedelta(seconds=segundos)}


def test_infraccion_entre_dos_camaras(g, nodos):
    r = evaluar_evento(g, nodos, cap(2, "V8D001", "AV-08", 120), [cap(1, "V8D001", "AV-01", 0)])
    assert len(r["infracciones"]) == 1 and not r["alertas"]
    inf = r["infracciones"][0]
    assert (inf["captura_anterior"], inf["captura_actual"]) == (1, 2)
    assert inf["ruta"] == ["AV-01", "AV-08"] and inf["v_conservadora"] == 87.1 and inf["exceso"] == 27.1


def test_sin_infraccion(g, nodos):
    r = evaluar_evento(g, nodos, cap(2, "D9R052", "AV-08", 200), [cap(1, "D9R052", "AV-01", 0)])
    assert r["sin_infraccion"][0]["v_conservadora"] == 52.9 and not r["infracciones"]


def test_vinculo_con_un_caracter_distinto_queda_a_verificar(g, nodos):
    r = evaluar_evento(g, nodos, cap(2, "DOR052", "AV-08", 200), [cap(1, "D9R052", "AV-01", 0)])
    assert r["sin_infraccion"][0]["coincidencia"] == "a_verificar"


def test_alerta_por_captura_imposible(g, nodos):
    r = evaluar_evento(g, nodos, cap(2, "T3P298", "AV-12", 60), [cap(1, "T3P298", "AV-01", 0)])
    assert not r["infracciones"] and not r["sin_infraccion"]
    a = r["alertas"][0]
    # 6.8 km (ruta mínima AV-01 -> AV-08 -> AV-12) en 1 min exigiría 408 km/h
    assert (a["km_minimos"], a["velocidad_necesaria_kmh"], a["minutos_observados"]) == (6.8, 408.0, 1.0)
    assert a["minimo_plausible_min"] == 2.04  # 6.8 km a 200 km/h


def test_regresion_auto_muy_rapido_es_infraccion_no_alerta(g, nodos):
    """Error encontrado en la prueba en vivo de la API (16/10/2026): 3 km en 110 s (94.7 km/h en
    zona de 60) se clasificaba como captura imposible porque superaba el doble de la velocidad
    típica del tramo (45 km/h). Debe ser infracción."""
    r = evaluar_evento(g, nodos, cap(2, "ABC123", "AV-08", 110), [cap(1, "ABC123", "AV-01", 0)])
    assert not r["alertas"] and len(r["infracciones"]) == 1
    assert r["infracciones"][0]["v_conservadora"] == 94.7


def test_por_encima_de_200_kmh_es_alerta(g, nodos):
    r = evaluar_evento(g, nodos, cap(2, "ABC123", "AV-08", 50), [cap(1, "ABC123", "AV-01", 0)])  # 216 km/h
    assert not r["infracciones"] and r["alertas"][0]["velocidad_necesaria_kmh"] == 216.0


def test_placas_distintas_no_se_relacionan(g, nodos):
    r = evaluar_evento(g, nodos, cap(2, "ABC123", "AV-08", 120), [cap(1, "XYZ789", "AV-01", 0)])
    assert r == {"infracciones": [], "sin_infraccion": [], "alertas": []}


def test_misma_camara_no_genera_tramo(g, nodos):
    r = evaluar_evento(g, nodos, cap(2, "ABC123", "AV-01", 30), [cap(1, "ABC123", "AV-01", 0)])
    assert r == {"infracciones": [], "sin_infraccion": [], "alertas": []}


def test_regresion_tres_camaras_no_cuenta_dos_veces_el_mismo_recorrido(g, nodos):
    """Error encontrado al preparar los datos de demostración (16/10/2026): un auto rápido que pasa por
    AV-01 -> AV-08 -> AV-12 generaba también la infracción AV-01 -> AV-12, que repite el recorrido ya
    multado en AV-01 -> AV-08. Cada captura se compara solo con la captura más cercana en el tiempo."""
    previas = [cap(1, "K7P441", "AV-01", 0), cap(2, "K7P441", "AV-08", 120)]
    r = evaluar_evento(g, nodos, cap(3, "K7P441", "AV-12", 240), previas)
    assert len(r["infracciones"]) == 1
    inf = r["infracciones"][0]
    assert (inf["captura_anterior"], inf["captura_actual"], inf["ruta"]) == (2, 3, ["AV-08", "AV-12"])
    assert not r["sin_infraccion"]
