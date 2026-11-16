"""Genera el notebook de Google Colab con los algoritmos de búsqueda (BFS, DFS, A*).

El notebook es autocontenido: incrusta el paquete `grafo/` y las redes de `data/`
con celdas %%writefile, así que en Colab no hay que subir ningún archivo.
Si cambia el código de `grafo/`, se vuelve a generar:

    python colab/generar_notebook.py
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = Path(__file__).with_name("FotoPapeleta_BFS_DFS_Aestrella.ipynb")

ARCHIVOS_GRAFO = ["__init__.py", "modelo.py", "heuristicas.py", "busqueda.py",
                  "evidencia.py", "velocidad.py", "decision.py"]
REDES = ["grafo_camaras.json", "grafo_camaras_real.json", "red_transito.json"]

celdas = []


def md(texto):
    celdas.append({"cell_type": "markdown", "metadata": {}, "source": texto.strip("\n")})


def code(texto):
    celdas.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                   "outputs": [], "source": texto.strip("\n")})


# ---------------------------------------------------------------- contenido
md("""
# FotoPapeleta Inteligente — Algoritmos de búsqueda BFS, DFS y A*

Universidad Tecnológica del Perú · APF2 · Metodología CRISP-DM

La red de cámaras se modela como un **grafo**: cada cámara es un nodo y cada tramo de vía es una arista con su
distancia (km) y su tiempo típico de viaje (min). Sobre ese grafo:

| Algoritmo | Para qué se usa en el proyecto |
|---|---|
| **BFS** | Cámaras alcanzables en *k* saltos: delimita dónde buscar nuevamente una placa leída |
| **DFS** (acotado) | Enumera las trayectorias posibles entre dos cámaras |
| **A\\*** | Ruta de menor costo con heurística de línea recta (admisible); también la ruta más rápida según el tráfico |

**Cómo usarlo:** `Entorno de ejecución → Ejecutar todas`. El notebook crea solo el paquete `grafo/` y las redes
en `data/`; no hay que subir archivos. Solo usa Python, `networkx` y `matplotlib`, que ya vienen en Colab.

Cada sección reproduce una prueba de la **Tabla II** del paper (P1–P7).
""")

md("## 1. Crear el paquete `grafo` y las redes de cámaras\nEs el mismo código del proyecto (`grafo/`), Python puro.")
code("import os\nos.makedirs('grafo', exist_ok=True)\nos.makedirs('data', exist_ok=True)\nprint('Carpetas listas')")
for nombre in ARCHIVOS_GRAFO:
    code(f"%%writefile grafo/{nombre}\n" + (RAIZ / "grafo" / nombre).read_text(encoding="utf-8"))

md("""
Redes de cámaras:
- `grafo_camaras.json`: red **esquemática** de 6 cámaras (Tabla I del paper), para la evaluación algorítmica.
- `grafo_camaras_real.json`: las mismas 6 cámaras con ubicaciones de OpenStreetMap y tramos por calles reales (OSRM).
- `red_transito.json`: las **15 cámaras públicas** de tránsito de Lima usadas para el conteo vehicular.
""")
for nombre in REDES:
    code(f"%%writefile data/{nombre}\n" + (RAIZ / "data" / nombre).read_text(encoding="utf-8"))

md("## 2. Importar y funciones de apoyo")
code('''
import json, random, time, timeit
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import networkx as nx

import grafo
from grafo import (a_estrella, bfs, cargar, construir, costo_ruta, dfs, misma_placa,
                   nula, recta_km, recta_min)

print("Paquete grafo:", ", ".join(grafo.__all__))
print("NetworkX", nx.__version__)


def a_networkx(g):
    """Convierte nuestra lista de adyacencia en un grafo de NetworkX (referencia independiente)."""
    G = nx.DiGraph()
    for a, vecinos in g.items():
        G.add_node(a)
        for b, w in vecinos:
            G.add_edge(a, b, **{k: v for k, v in w.items() if v is not None})
    return G


def posiciones(nodos):
    if all("x_km" in n for n in nodos.values()):
        return {c: (n["x_km"], n["y_km"]) for c, n in nodos.items()}
    return {c: (n["lon"], n["lat"]) for c, n in nodos.items()}


def dibujar(g, nodos, ruta=None, colores=None, titulo="", peso="km", etiquetas_aristas=True,
            tam=(8, 5), tam_nodo=900, enfoque=None):
    """enfoque: lista de cámaras a encuadrar (acerca la vista a esa zona)."""
    G = a_networkx(g).to_undirected()
    pos = posiciones(nodos)
    plt.figure(figsize=tam)
    nx.draw_networkx_edges(G, pos, edge_color="#bbbbbb", width=1.5)
    if ruta:
        nx.draw_networkx_edges(G, pos, edgelist=list(zip(ruta, ruta[1:])), edge_color="#d62728", width=4)
    color = [colores.get(n, "#dddddd") for n in G.nodes] if colores else "#9ecae1"
    nx.draw_networkx_nodes(G, pos, node_color=color, node_size=tam_nodo, edgecolors="#333333")
    nx.draw_networkx_labels(G, pos, font_size=7)
    if etiquetas_aristas:
        nx.draw_networkx_edge_labels(G, pos, font_size=7,
                                     edge_labels={(a, b): round(d[peso], 1) for a, b, d in G.edges(data=True)})
    if enfoque:
        xs, ys = zip(*(pos[c] for c in enfoque))
        mx, my = (max(xs) - min(xs)) * 0.12, (max(ys) - min(ys)) * 0.12
        plt.xlim(min(xs) - mx, max(xs) + mx)
        plt.ylim(min(ys) - my, max(ys) + my)
    plt.title(titulo)
    plt.axis("off")
    plt.show()
''')

md("## 3. Cargar y validar la red esquemática (Tabla I)\n`cargar` valida que la distancia en línea recta entre cámaras conectadas nunca supere la longitud del tramo: es la condición para que la heurística de A* sea **admisible**.")
code('''
g, nodos = cargar("data/grafo_camaras.json")
for cam, vecinos in g.items():
    print(f"{cam} ({nodos[cam]['nombre']}):", [(v, w["km"]) for v, w in vecinos])
dibujar(g, nodos, titulo="Red de cámaras de evaluación (km por tramo)")
''')

md("## 4. BFS — cámaras a ≤ k saltos (P1)\nCuando una cámara lee una placa, BFS indica en qué cámaras vecinas buscar la misma placa.")
code('''
saltos = bfs(g, "AV-01", k=2)
print("BFS desde AV-01, k = 2:", saltos)

ref = nx.single_source_shortest_path_length(a_networkx(g), "AV-01", cutoff=2)
print("Igual a NetworkX:", saltos == ref)

paleta = {0: "#d62728", 1: "#ff9f40", 2: "#ffe08a"}
dibujar(g, nodos, colores={c: paleta[s] for c, s in saltos.items()},
        titulo="BFS desde AV-01 (rojo = origen, naranja = 1 salto, amarillo = 2 saltos)")
''')

md("## 5. DFS acotado — trayectorias posibles (P2)")
code('''
rutas = dfs(g, "AV-01", "PN-04", max_prof=6)
for r in sorted(rutas, key=lambda r: costo_ruta(g, r)):
    print(" → ".join(r), f"= {costo_ruta(g, r):.1f} km")

ref = nx.all_simple_paths(a_networkx(g), "AV-01", "PN-04", cutoff=6)
print("Igual a NetworkX:", sorted(map(tuple, rutas)) == sorted(map(tuple, ref)))
''')

md("## 6. A* — ruta mínima con y sin heurística (P3, P4)\nCon `h = 0`, A* se comporta como Dijkstra. Con la heurística de línea recta explora menos nodos y obtiene el mismo costo.")
code('''
h = recta_km(nodos)
for nombre, heur in [("h = 0 (Dijkstra)", nula), ("h = línea recta", h)]:
    traza = []
    r = a_estrella(g, "AV-01", "AV-08", heur, traza=traza)
    print(f"{nombre:18} ruta {r.ruta}, {r.costo} km, nodos explorados {r.explorados}, orden {traza}")

# P3: los 30 pares de cámaras frente a NetworkX
G = a_networkx(g)
pares = [(a, b) for a in g for b in g if a != b]
correctos = sum(
    abs(a_estrella(g, a, b).costo - nx.dijkstra_path_length(G, a, b, weight="km")) < 1e-9 and
    abs(a_estrella(g, a, b, h).costo - nx.dijkstra_path_length(G, a, b, weight="km")) < 1e-9
    for a, b in pares)
print(f"\\nCosto correcto en {correctos}/{len(pares)} pares, con h = 0 y con heurística")

r = a_estrella(g, "AV-01", "PN-04", h)
dibujar(g, nodos, ruta=r.ruta, titulo=f"A* de AV-01 a PN-04: {' → '.join(r.ruta)} ({r.costo:.1f} km)")
''')

md("## 7. Coincidencia de placas entre cámaras (P5)\nLas placas que difieren en caracteres que el OCR confunde (B/8, O/0…) o en un solo carácter quedan **a verificar**.")
code('''
for leida in ["ABC-123", "A8C-123", "ABC-128", "D4F-582"]:
    print(f"ABC-123 vs {leida}: {misma_placa('ABC-123', leida)}")
''')

md("## 8. Tiempo por ejecución (P6)\nLos tiempos dependen del procesador; en el paper se midieron en un AMD Ryzen 5 9600X.")
code('''
def us(f, n=20000):
    return timeit.timeit(f, number=n) / n * 1e6

print(f"BFS          {us(lambda: bfs(g, 'AV-01', 2)):.1f} µs")
print(f"DFS          {us(lambda: dfs(g, 'AV-01', 'PN-04')):.1f} µs")
print(f"A* (h = 0)   {us(lambda: a_estrella(g, 'AV-01', 'PN-04')):.1f} µs")
print(f"A* (recta)   {us(lambda: a_estrella(g, 'AV-01', 'PN-04', h)):.1f} µs")
''')

md("## 9. Escalabilidad: 400 cámaras, 760 tramos, 300 consultas (P7)\nRejilla sintética de 20 × 20 cámaras; cada tramo mide entre 1.0 y 1.6 veces la distancia recta, para que la heurística siga siendo admisible. Semilla 42, como en el paper.")
code('''
def red_rejilla(n=20, paso_km=0.8, semilla=42):
    rnd = random.Random(semilla)
    nodos_r = {f"C{i}_{j}": {"x_km": i * paso_km, "y_km": j * paso_km} for i in range(n) for j in range(n)}
    aristas = []
    for i in range(n):
        for j in range(n):
            for di, dj in ((1, 0), (0, 1)):
                if i + di < n and j + dj < n:
                    km = round(paso_km * rnd.uniform(1.0, 1.6), 2)
                    aristas.append({"de": f"C{i}_{j}", "a": f"C{i+di}_{j+dj}", "km": km, "min": km * 1.5})
    return {"nodos": nodos_r, "aristas": aristas}, rnd


datos, rnd = red_rejilla()
gg, hh = construir(datos), recta_km(datos["nodos"])
Gr = nx.Graph()
for a in datos["aristas"]:
    Gr.add_edge(a["de"], a["a"], km=a["km"])

claves, consultas = list(datos["nodos"]), 300
exp0 = exph = t0 = th = correctos = 0
for _ in range(consultas):
    a, b = rnd.sample(claves, 2)
    s = time.perf_counter(); r0 = a_estrella(gg, a, b, nula); t0 += time.perf_counter() - s
    s = time.perf_counter(); rh = a_estrella(gg, a, b, hh); th += time.perf_counter() - s
    ref = nx.dijkstra_path_length(Gr, a, b, weight="km")
    correctos += abs(r0.costo - ref) < 1e-9 and abs(rh.costo - ref) < 1e-9
    exp0 += r0.explorados
    exph += rh.explorados

print(f"Cámaras {len(datos['nodos'])}, tramos {len(datos['aristas'])}, consultas {consultas}")
print(f"Costo correcto: {correctos}/{consultas}")
print(f"Nodos explorados: {exp0/consultas:.1f} (h = 0) → {exph/consultas:.1f} (recta), "
      f"reducción {100*(1-exph/exp0):.1f} %")
print(f"Tiempo por consulta: {t0/consultas*1000:.3f} ms → {th/consultas*1000:.3f} ms")

plt.figure(figsize=(5, 3))
plt.bar(["A* con h = 0", "A* con línea recta"], [exp0 / consultas, exph / consultas], color=["#bbbbbb", "#1f77b4"])
plt.ylabel("Nodos explorados (promedio)")
plt.title("400 cámaras, 300 consultas")
plt.show()
''')

md("## 10. Red real (OpenStreetMap + OSRM)\nLas mismas 6 cámaras con coordenadas reales (lat/lon): la heurística usa la distancia de Haversine. El tramo AV-01–AV-08 mide 0.95 km por calles, frente a 3.0 km en la red esquemática.")
code('''
gr, nr = cargar("data/grafo_camaras_real.json")
r = a_estrella(gr, "AV-01", "AV-08", recta_km(nr))
print(f"A* AV-01 → AV-08 por calles: {' → '.join(r.ruta)}, {r.costo:.2f} km")
dibujar(gr, nr, ruta=r.ruta, titulo="Red real: A* de AV-01 a AV-08 (km por calles)")
''')

md("""
## 11. Cámaras públicas: ruta más rápida según el tráfico
En el sistema, el conteo con YOLOv8n + ByteTrack da un **factor de congestión** por cámara (vehículos visibles ÷ lo
normal en esa cámara, entre 1 y 3). El tiempo de cada tramo se multiplica por el promedio del factor de sus dos
cámaras, y A* busca la ruta más rápida con la heurística *línea recta ÷ velocidad máxima de la red*, que nunca
sobreestima. Aquí los factores son de **ejemplo**; cámbialos para ver cómo cambia la ruta.
""")
code('''
datos_t = json.load(open("data/red_transito.json", encoding="utf-8"))
print("Errores de validación:", grafo.validar(datos_t) or "ninguno")


def ruta_mas_rapida(datos, factores, origen, destino):
    aristas, vmax = [], 1.0
    for a in datos["aristas"]:
        f = (factores.get(a["de"], 1.0) + factores.get(a["a"], 1.0)) / 2
        aristas.append({**a, "min": a["min"] * f})
        vmax = max(vmax, a["km"] / (a["min"] / 60))   # velocidad máxima a flujo libre
    g_t = construir({"nodos": datos["nodos"], "aristas": aristas})
    h_t = recta_min(datos["nodos"], vmax_kmh=vmax)
    return a_estrella(g_t, origen, destino, h=h_t, peso="min"), g_t, h_t


libre, g_t, h_t = ruta_mas_rapida(datos_t, {}, "lamarina", "panamericana")
# Admisibilidad: la heurística no supera el tiempo de ningún arco
arcos = [(a, b, w["min"]) for a, vec in g_t.items() for b, w in vec]
print(f"Heurística admisible en {sum(h_t(a, b) <= m + 1e-9 for a, b, m in arcos)}/{len(arcos)} arcos")

congestion = {"lamarina": 1.4, "ejercito": 1.3, "angamos": 2.2, "republicapanama": 1.8}  # ejemplo
ahora, g_c, _ = ruta_mas_rapida(datos_t, congestion, "lamarina", "panamericana")
print(f"Flujo libre: {' → '.join(libre.ruta)} = {libre.costo:.1f} min")
print(f"Con tráfico: {' → '.join(ahora.ruta)} = {ahora.costo:.1f} min")

paleta = lambda f: "#d62728" if f >= 1.6 else "#ff9f40" if f >= 1.25 else "#7fd17f"
centro = ["lamarina", "avfaustinocarrion", "paseodelarepublica", "ejercito", "republicapanama",
          "angamos", "javierprado", "derby", "panamericana"]
dibujar(g_c, datos_t["nodos"], ruta=ahora.ruta, peso="min", tam=(10, 8), tam_nodo=350, enfoque=centro,
        colores={c: paleta(congestion.get(c, 1.0)) for c in datos_t["nodos"]},
        titulo="Cámaras públicas (zona central): congestión de ejemplo, minutos por tramo y ruta más rápida con A*")
''')

md("""
## Anexo (trabajo futuro): velocidad promedio entre cámaras
Prototipo verificado **solo con capturas simuladas**; su validación con cámaras propias queda para la siguiente fase.
Usa la distancia mínima de A* y el mayor tiempo posible (Δt + 2ε, con ε = 2 s por desfase de reloj):
v = 3600·d_min / (Δt + 2ε), una cota inferior de la velocidad real, a favor del conductor.
""")
code('''
t = datetime(2026, 10, 15, 8, 0, 0)
for segundos in (120, 200):
    v = grafo.velocidad_por_tramo(g, "AV-01", t, "AV-08", t + timedelta(seconds=segundos), h=h)
    print(f"Δt = {segundos} s: medida {v.v_medida} km/h, conservadora {v.v_conservadora} km/h, "
          f"límite {v.limite}, ¿infracción? {v.infraccion}")
''')

# ---------------------------------------------------------------- escribir
nb = {"cells": celdas, "metadata": {"colab": {"provenance": []},
                                    "kernelspec": {"name": "python3", "display_name": "Python 3"},
                                    "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
for c in nb["cells"]:  # formato estándar: lista de líneas
    c["source"] = c["source"].splitlines(keepends=True)
DESTINO.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("Generado:", DESTINO)
