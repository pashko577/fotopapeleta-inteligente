"""Tramos de la red de fiscalización calculados por calles reales (OSRM sobre OpenStreetMap).

La velocidad por tramo usa la distancia MÍNIMA del grafo entre dos cámaras. Para no perjudicar al conductor,
esa distancia nunca debe superar la distancia real más corta por calles. Reglas:
  1. Dos cámaras se conectan directamente si la ruta real más corta entre ellas no pasa por otra cámara.
  2. Verificación: para CADA par de cámaras, distancia en el grafo <= distancia real (+ 50 m). Si un par no la
     cumple, se agrega el tramo directo con la distancia real.
"""
import json
import math
import time
import urllib.request

OSRM = "https://router.project-osrm.org/route/v1/driving"
HOLGURA_KM = 0.05


def ruta(a, b, pausa=1.1):
    """(km, minutos, geometría [[lat, lon], ...]) de la ruta más corta en auto de a hacia b."""
    url = f"{OSRM}/{a['lon']},{a['lat']};{b['lon']},{b['lat']}?overview=simplified&geometries=geojson"
    req = urllib.request.Request(url, headers={"User-Agent": "FotoPapeleta-UTP-proyecto-academico/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        datos = json.load(r)["routes"][0]
    time.sleep(pausa)  # servidor de demostración de OSRM: no saturarlo
    return datos["distance"] / 1000, datos["duration"] / 60, [[round(la, 5), round(lo, 5)] for lo, la in datos["geometry"]["coordinates"]]


def _km(p, q):
    """Distancia aproximada en km entre dos puntos [lat, lon] cercanos (proyección equirectangular)."""
    lat0 = math.radians((p[0] + q[0]) / 2)
    return math.hypot((q[1] - p[1]) * 111.32 * math.cos(lat0), (q[0] - p[0]) * 110.57)


def distancia_a_linea_km(punto, linea):
    """Distancia mínima en km de un punto [lat, lon] a una polilínea."""
    mejor = float("inf")
    for a, b in zip(linea, linea[1:]):
        lat0 = math.radians(a[0])
        ax, ay = 0.0, 0.0
        bx, by = (b[1] - a[1]) * 111.32 * math.cos(lat0), (b[0] - a[0]) * 110.57
        px, py = (punto[1] - a[1]) * 111.32 * math.cos(lat0), (punto[0] - a[0]) * 110.57
        largo = bx * bx + by * by
        t = 0 if largo == 0 else max(0, min(1, (px * bx + py * by) / largo))
        mejor = min(mejor, math.hypot(px - t * bx, py - t * by))
    return mejor


def calcular_tramos(nodos, radio_km=0.2, consultar=ruta, informar=print):
    """Devuelve las aristas (formato de data/grafo_camaras.json) y el informe de la verificación por par."""
    import grafo

    codigos = sorted(nodos)
    reales = {}
    for i, a in enumerate(codigos):
        for b in codigos[i + 1:]:
            ida, vuelta = consultar(nodos[a], nodos[b]), consultar(nodos[b], nodos[a])
            reales[(a, b)] = min(ida, vuelta, key=lambda r: r[0])  # vía de doble sentido: el sentido más corto
            informar(f"  {a} - {b}: {reales[(a, b)][0]:.2f} km por calles")

    def arista(a, b, motivo):
        km, mins, geo = reales[(a, b)]
        limite = max(nodos[a].get("limite_kmh", 60), nodos[b].get("limite_kmh", 60))  # el más alto: a favor del conductor
        return {"de": a, "a": b, "km": round(km, 2), "min": round(mins, 1), "limite_kmh": limite, "dirigida": False,
                "fuente": f"OSRM ({motivo})", "geometria": geo}

    aristas = []
    for (a, b), (km, mins, geo) in reales.items():
        por = [c for c in codigos if c not in (a, b) and distancia_a_linea_km([nodos[c]["lat"], nodos[c]["lon"]], geo) <= radio_km]
        if not por:
            aristas.append(arista(a, b, "ruta directa"))

    verificacion = []
    for _ in range(len(reales)):  # se repite hasta que todos los pares cumplan
        g = grafo.construir({"nodos": nodos, "aristas": aristas})
        faltantes = []
        for (a, b), (km_real, _, _) in reales.items():
            km_grafo = grafo.a_estrella(g, a, b).costo
            if km_grafo > km_real + HOLGURA_KM:
                faltantes.append((a, b))
        if not faltantes:
            break
        for a, b in faltantes:
            aristas.append(arista(a, b, "agregado para no superar la distancia real"))
    g = grafo.construir({"nodos": nodos, "aristas": aristas})
    for (a, b), (km_real, _, _) in reales.items():
        verificacion.append({"par": f"{a} - {b}", "km_real": round(km_real, 2), "km_grafo": round(grafo.a_estrella(g, a, b).costo, 2)})
    return aristas, verificacion
