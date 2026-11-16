"""Velocidad promedio por tramo (section speed), calculada a favor del conductor."""
from dataclasses import dataclass

from .busqueda import a_estrella
from .heuristicas import nula


@dataclass
class ResultadoVelocidad:
    ruta: list
    km: float
    v_medida: float
    v_conservadora: float
    limite: float
    exceso: float
    infraccion: bool


def velocidad_por_tramo(grafo, cam_a, t_a, cam_b, t_b, h=nula, limite=None,
                        error_reloj_s=2, tolerancia_kmh=5):
    """Velocidad mínima posible entre dos capturas de la misma placa.

    Usa la distancia mínima (A*) y el tiempo máximo (Δt + 2ε). Si no se pasa
    `limite`, toma el límite más alto de la ruta (también a favor del conductor).
    Devuelve None si no hay ruta o si Δt <= 0.
    """
    res = a_estrella(grafo, cam_a, cam_b, h, peso="km")
    dt = (t_b - t_a).total_seconds()
    if res.ruta is None or dt <= 0:
        return None
    if limite is None:
        limite = max(w["limite_kmh"] for a, b in zip(res.ruta, res.ruta[1:])
                     for v, w in grafo[a] if v == b)
    v_medida = res.costo / (dt / 3600)
    v_cons = res.costo / ((dt + 2 * error_reloj_s) / 3600)
    return ResultadoVelocidad(res.ruta, res.costo, round(v_medida, 1), round(v_cons, 1),
                              limite, round(v_cons - limite, 1), v_cons > limite + tolerancia_kmh)
