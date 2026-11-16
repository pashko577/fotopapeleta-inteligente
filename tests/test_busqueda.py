import itertools

import networkx as nx
import pytest

from grafo import a_estrella, bfs, construir, costo_ruta, dfs, nula, recta_km


def test_p1_bfs_k2_igual_a_networkx(g, ref):
    obtenido = bfs(g, "AV-01", 2)
    assert obtenido == {"AV-01": 0, "AV-08": 1, "AV-02": 1, "AV-15": 2, "AV-12": 2}
    assert obtenido == dict(nx.single_source_shortest_path_length(ref, "AV-01", cutoff=2))


def test_p2_dfs_rutas_y_costos(g, ref):
    rutas = dfs(g, "AV-01", "PN-04")
    assert sorted(map(tuple, rutas)) == sorted(map(tuple, nx.all_simple_paths(ref, "AV-01", "PN-04")))
    assert sorted(round(costo_ruta(g, r), 1) for r in rutas) == [12.8, 13.3]


def test_dfs_respeta_max_rutas(g):
    assert len(dfs(g, "AV-01", "PN-04", max_rutas=1)) == 1


@pytest.mark.parametrize("peso", ["km", "min"])
def test_p3_a_estrella_todos_los_pares(g, nodos, ref, peso):
    h = recta_km(nodos) if peso == "km" else nula
    for a, b in itertools.permutations(nodos, 2):
        esperado = nx.dijkstra_path_length(ref, a, b, weight=peso)
        assert a_estrella(g, a, b, nula, peso).costo == pytest.approx(esperado)
        assert a_estrella(g, a, b, h, peso).costo == pytest.approx(esperado)


def test_p4_heuristica_explora_menos(g, nodos):
    sin_h = a_estrella(g, "AV-01", "AV-08")
    con_h = a_estrella(g, "AV-01", "AV-08", recta_km(nodos))
    assert sin_h.ruta == con_h.ruta == ["AV-01", "AV-08"]
    assert sin_h.costo == con_h.costo == 3.0
    assert (sin_h.explorados, con_h.explorados) == (3, 2)


def test_via_de_un_sentido():
    datos = {"nodos": {"A": {}, "B": {}, "C": {}},
             "aristas": [{"de": "A", "a": "B", "km": 1, "min": 1, "dirigida": True},
                         {"de": "B", "a": "C", "km": 1, "min": 1, "dirigida": False}]}
    g = construir(datos)
    assert a_estrella(g, "A", "C").ruta == ["A", "B", "C"]
    assert a_estrella(g, "C", "A").ruta is None
    assert bfs(g, "B", 1) == {"B": 0, "C": 1}
