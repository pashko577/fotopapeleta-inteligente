import json
from pathlib import Path

import networkx as nx
import pytest

import grafo

RED = Path(__file__).resolve().parents[1] / "data" / "grafo_camaras.json"


@pytest.fixture
def datos():
    return json.loads(RED.read_text(encoding="utf-8"))


@pytest.fixture
def red():
    """(grafo, nodos) de la red de evaluación del paper (Tabla I)."""
    return grafo.cargar(RED)


@pytest.fixture
def g(red):
    return red[0]


@pytest.fixture
def nodos(red):
    return red[1]


@pytest.fixture
def ref(datos):
    """Misma red en NetworkX: referencia independiente para comparar resultados."""
    G = nx.DiGraph()
    for a in datos["aristas"]:
        G.add_edge(a["de"], a["a"], km=a["km"], min=a["min"])
        if not a["dirigida"]:
            G.add_edge(a["a"], a["de"], km=a["km"], min=a["min"])
    return G
