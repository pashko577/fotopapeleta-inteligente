"""Heurísticas para A*. Deben estar en las mismas unidades que el peso y no sobreestimar."""
from .modelo import distancia_recta_km


def nula(a, b):
    """h = 0: A* se comporta como Dijkstra."""
    return 0


def recta_km(nodos):
    """Distancia en línea recta (km). Admisible para peso="km"."""
    def h(a, b):
        d = distancia_recta_km(nodos[a], nodos[b])
        return 0 if d is None else d
    return h


def recta_min(nodos, vmax_kmh=80):
    """Tiempo mínimo (min) recorriendo la recta a la velocidad máxima de la red. Admisible para peso="min"."""
    km = recta_km(nodos)
    return lambda a, b: km(a, b) / vmax_kmh * 60
