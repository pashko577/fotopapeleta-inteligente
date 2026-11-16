"""Reproduce P9 y P10 de la Tabla II del paper (tiempos y escalabilidad del módulo de búsqueda).

Uso:  python -m evaluacion.benchmark_grafo
Escribe evaluacion/resultados/benchmark_grafo.json
"""
import json
import platform
import random
import time
from pathlib import Path

import networkx as nx

from grafo import a_estrella, bfs, cargar, construir, dfs, nula, recta_km

RAIZ = Path(__file__).resolve().parents[1]


def tiempo_medio_ms(f, n=20000):
    t = time.perf_counter()
    for _ in range(n):
        f()
    return (time.perf_counter() - t) / n * 1000


def red_rejilla(n=20, paso_km=0.8, semilla=42):
    """Rejilla n×n con tramos >= distancia recta (heurística admisible)."""
    rnd = random.Random(semilla)
    nodos = {f"C{i}_{j}": {"x_km": i * paso_km, "y_km": j * paso_km} for i in range(n) for j in range(n)}
    aristas = []
    for i in range(n):
        for j in range(n):
            for di, dj in ((1, 0), (0, 1)):
                if i + di < n and j + dj < n:
                    km = round(paso_km * rnd.uniform(1.0, 1.6), 2)
                    aristas.append({"de": f"C{i}_{j}", "a": f"C{i+di}_{j+dj}", "km": km, "min": km * 1.5})
    return {"nodos": nodos, "aristas": aristas}, rnd


def main():
    g, nodos = cargar(RAIZ / "data" / "grafo_camaras.json")
    h = recta_km(nodos)
    p9 = {"BFS": tiempo_medio_ms(lambda: bfs(g, "AV-01", 2)),
          "DFS": tiempo_medio_ms(lambda: dfs(g, "AV-01", "PN-04")),
          "A*_h0": tiempo_medio_ms(lambda: a_estrella(g, "AV-01", "PN-04")),
          "A*_recta": tiempo_medio_ms(lambda: a_estrella(g, "AV-01", "PN-04", h))}

    datos, rnd = red_rejilla()
    gg, hh = construir(datos), recta_km(datos["nodos"])
    G = nx.Graph()
    for a in datos["aristas"]:
        G.add_edge(a["de"], a["a"], km=a["km"])
    claves, consultas = list(datos["nodos"]), 300
    exp0 = exph = t0 = th = correctos = 0
    for _ in range(consultas):
        a, b = rnd.sample(claves, 2)
        s = time.perf_counter(); r0 = a_estrella(gg, a, b, nula); t0 += time.perf_counter() - s
        s = time.perf_counter(); rh = a_estrella(gg, a, b, hh); th += time.perf_counter() - s
        ref = nx.dijkstra_path_length(G, a, b, weight="km")
        correctos += abs(r0.costo - ref) < 1e-9 and abs(rh.costo - ref) < 1e-9
        exp0 += r0.explorados; exph += rh.explorados
    p10 = {"camaras": len(datos["nodos"]), "tramos": len(datos["aristas"]), "consultas": consultas,
           "costos_correctos": correctos, "explorados_h0": round(exp0 / consultas, 1),
           "explorados_recta": round(exph / consultas, 1), "reduccion_pct": round(100 * (1 - exph / exp0), 1),
           "ms_h0": round(t0 / consultas * 1000, 3), "ms_recta": round(th / consultas * 1000, 3)}

    salida = {"entorno": {"python": platform.python_version(), "networkx": nx.__version__,
                          "procesador": platform.processor()},
              "P9_ms": {k: round(v, 4) for k, v in p9.items()}, "P10": p10}
    destino = RAIZ / "evaluacion" / "resultados" / "benchmark_grafo.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(salida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
