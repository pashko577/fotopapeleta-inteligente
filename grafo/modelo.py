"""Módulo B: carga, construcción y validación del grafo de cámaras."""
import json
import math
from pathlib import Path


def cargar(ruta):
    """Lee el JSON de la red y devuelve (grafo, nodos)."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    errores = validar(datos)
    if errores:
        raise ValueError("Grafo inválido:\n- " + "\n- ".join(errores))
    return construir(datos), datos["nodos"]


def construir(datos):
    """Lista de adyacencia dirigida: {camara: [(vecino, {km, min, limite_kmh}), ...]}.

    Una arista con "dirigida": false (vía de doble sentido) genera dos arcos.
    """
    grafo = {n: [] for n in datos["nodos"]}
    for a in datos["aristas"]:
        peso = {"km": a["km"], "min": a["min"], "limite_kmh": a.get("limite_kmh")}
        grafo[a["de"]].append((a["a"], peso))
        if not a.get("dirigida", False):
            grafo[a["a"]].append((a["de"], peso))
    return grafo


def validar(datos):
    """Devuelve la lista de errores; vacía si la red es consistente."""
    errores = []
    nodos = datos.get("nodos", {})
    for a in datos.get("aristas", []):
        tramo = f'{a.get("de")} -> {a.get("a")}'
        for extremo in (a.get("de"), a.get("a")):
            if extremo not in nodos:
                errores.append(f"{tramo}: la cámara {extremo} no existe")
        if a.get("km", 0) <= 0 or a.get("min", 0) <= 0:
            errores.append(f"{tramo}: km y min deben ser positivos")
        if errores:
            continue
        # La heurística de A* solo es admisible si la recta no supera al tramo.
        recta = distancia_recta_km(nodos[a["de"]], nodos[a["a"]])
        if recta is not None and recta > a["km"] + 1e-9:
            errores.append(f"{tramo}: la distancia en línea recta ({recta:.2f} km) supera al tramo ({a['km']} km)")
    return errores


def distancia_recta_km(p, q):
    """Distancia en línea recta entre dos cámaras.

    Usa coordenadas proyectadas (x_km, y_km) si existen; si no, Haversine con lat/lon.
    Devuelve None si la cámara no tiene coordenadas.
    """
    if "x_km" in p and "x_km" in q:
        return math.dist((p["x_km"], p["y_km"]), (q["x_km"], q["y_km"]))
    if "lat" in p and "lat" in q:
        lat1, lon1, lat2, lon2 = map(math.radians, (p["lat"], p["lon"], q["lat"], q["lon"]))
        h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        return 2 * 6371 * math.asin(math.sqrt(h))
    return None
