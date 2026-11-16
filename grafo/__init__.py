"""Paquete grafo: red de cámaras y búsqueda de evidencia (Módulos B y C).

Python puro, sin dependencias de Django ni de la BD: lo usan igual la web y el notebook.
"""
from .busqueda import a_estrella, bfs, costo_ruta, dfs
from .decision import evaluar_evento
from .evidencia import V_MAX_PLAUSIBLE_KMH, capturas_coherentes, clave, misma_placa, velocidad_implicita
from .heuristicas import nula, recta_km, recta_min
from .modelo import cargar, construir, validar
from .velocidad import velocidad_por_tramo

__all__ = ["a_estrella", "bfs", "costo_ruta", "dfs", "capturas_coherentes", "clave",
           "misma_placa", "nula", "recta_km", "recta_min", "cargar", "construir",
           "validar", "velocidad_por_tramo", "evaluar_evento", "velocidad_implicita",
           "V_MAX_PLAUSIBLE_KMH"]
