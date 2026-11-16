"""Módulo C: BFS, DFS acotado y A* sobre el grafo de cámaras."""
import heapq
from collections import deque, namedtuple

from .heuristicas import nula

ResultadoRuta = namedtuple("ResultadoRuta", "ruta costo explorados")


def bfs(grafo, origen, k):
    """Cámaras alcanzables en <= k saltos: {camara: saltos} (incluye el origen con 0)."""
    visitados, cola = {origen: 0}, deque([origen])
    while cola:
        actual = cola.popleft()
        if visitados[actual] == k:
            continue
        for vecino, _ in grafo[actual]:
            if vecino not in visitados:
                visitados[vecino] = visitados[actual] + 1
                cola.append(vecino)
    return visitados


def dfs(grafo, origen, destino, max_prof=6, max_rutas=50):
    """Rutas simples de origen a destino, acotadas por profundidad y cantidad."""
    rutas, camino = [], []

    def visitar(actual):
        camino.append(actual)
        if actual == destino:
            rutas.append(list(camino))
        elif len(camino) <= max_prof and len(rutas) < max_rutas:
            for vecino, _ in grafo[actual]:
                if vecino not in camino:
                    visitar(vecino)
        camino.pop()

    visitar(origen)
    return rutas


def a_estrella(grafo, origen, destino, h=nula, peso="km", traza=None):
    """Ruta de menor costo. Devuelve ResultadoRuta(ruta, costo, explorados); ruta=None si no hay camino.

    Si se pasa una lista en `traza`, se le agregan los nodos en el orden en que se exploran (laboratorio).
    """
    abierto = [(h(origen, destino), origen)]
    g, padre, cerrados, explorados = {origen: 0}, {}, set(), 0
    while abierto:
        _, actual = heapq.heappop(abierto)
        if actual in cerrados:  # entrada obsoleta de la cola
            continue
        cerrados.add(actual)
        explorados += 1
        if traza is not None:
            traza.append(actual)
        if actual == destino:
            ruta = [actual]
            while ruta[-1] in padre:
                ruta.append(padre[ruta[-1]])
            return ResultadoRuta(ruta[::-1], g[destino], explorados)
        for vecino, w in grafo[actual]:
            costo = g[actual] + w[peso]
            if costo < g.get(vecino, float("inf")):
                g[vecino], padre[vecino] = costo, actual
                heapq.heappush(abierto, (costo + h(vecino, destino), vecino))
    return ResultadoRuta(None, float("inf"), explorados)


def costo_ruta(grafo, ruta, peso="km"):
    """Suma del peso de los arcos de una ruta."""
    total = 0
    for a, b in zip(ruta, ruta[1:]):
        total += next(w[peso] for v, w in grafo[a] if v == b)
    return total
