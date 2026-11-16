# 01 · Módulo de grafo (Módulos B y C)

## Objetivo
Verificar que la búsqueda de evidencia en la red de cámaras (BFS, DFS, A\*), el cálculo de velocidad por tramo y el vínculo de capturas entre cámaras den resultados correctos, comparándolos con una librería independiente (NetworkX).

## Configuración
| Elemento | Valor |
|---|---|
| Código | paquete [`grafo/`](../../grafo/) (Python puro, sin dependencias) |
| Red de prueba | [`data/grafo_camaras.json`](../../data/grafo_camaras.json): 6 cámaras, 6 tramos de doble sentido, límite 60 km/h (Tabla I del paper) |
| Coordenadas | Proyectadas en km y esquemáticas; cumplen *recta ≤ tramo* (heurística admisible) |
| Referencia | NetworkX 3.7 |
| Entorno | Python 3.12.10, AMD Ryzen 5 9600X |

## Pruebas automáticas (pytest) — 22/22 aprobadas (25 desde el experimento 07)

| Archivo | Prueba | Qué verifica | Resultado |
|---|---|---|---|
| `test_busqueda.py` | `test_p1_bfs_k2_igual_a_networkx` | BFS desde AV-01 con k = 2 | `{AV-01:0, AV-08:1, AV-02:1, AV-15:2, AV-12:2}`, igual a NetworkX |
| | `test_p2_dfs_rutas_y_costos` | DFS de AV-01 a PN-04 | 2 rutas (12.8 km y 13.3 km), iguales a NetworkX |
| | `test_dfs_respeta_max_rutas` | Límite de rutas de DFS | Respeta `max_rutas` |
| | `test_p3_a_estrella_todos_los_pares[km]` y `[min]` | A\* en los 30 pares, por distancia y por tiempo | Costo igual a Dijkstra de NetworkX en todos |
| | `test_p4_heuristica_explora_menos` | A\* AV-01 → AV-08 | Ruta directa de 3.0 km; 3 nodos explorados con h = 0 y 2 con heurística |
| | `test_via_de_un_sentido` | Arista dirigida | Se puede ir A → C pero no volver C → A |
| `test_velocidad.py` | `test_p5_exceso_de_velocidad` | 3.0 km en 120 s | 90.0 km/h medida, 87.1 km/h conservadora, exceso +27.1 km/h → infracción |
| | `test_p6_sin_infraccion` | 3.0 km en 200 s | 52.9 km/h → sin infracción |
| | `test_dentro_de_la_tolerancia_no_es_infraccion` | 3.0 km en 166 s | 63.5 km/h: supera 60 pero no 60 + 5 → sin infracción |
| | `test_tiempo_no_positivo_devuelve_none` | Δt = 0 | No calcula velocidad |
| `test_evidencia.py` | `test_p8_coincidencia_de_placa` (7 casos) | ABC-123 frente a otras lecturas | `ABC-123` y `abc 123` confirmadas; `A8C-123` (confundible) y `ABC-128` (un carácter distinto, agregado en [07](07_pipeline_extremo_a_extremo.md)) a verificar; `AXC-128`, `ABC-1234` y `D4F-582` descartadas |
| | `test_p7_filtro_temporal` | Ruta mínima AV-01 → AV-12 = 6.8 km; se rechaza lo que exija más de 200 km/h | Captura a 1 min (408 km/h) rechazada; a 10 min (40.8 km/h) aceptada |
| | `test_descarta_placas_distintas_y_camaras_lejanas` | Placa distinta, cámara a 3 saltos y placa dudosa | Solo queda la dudosa, marcada "a verificar" |
| `test_modelo.py` | 5 pruebas | Validación del JSON de la red | Detecta cámara inexistente, peso no positivo y tramo más corto que la recta; rechaza redes inválidas |

## Benchmark de rendimiento (P9 y P10)

**P9 · Tiempo medio por ejecución (red de 6 cámaras, 20 000 repeticiones)**

| Algoritmo | Tiempo |
|---|---|
| BFS (k = 2) | 0.8 µs |
| DFS (AV-01 → PN-04) | 2.9 µs |
| A\* sin heurística | 3.6 µs |
| A\* con heurística | 4.7 µs |

En una red tan pequeña la heurística no ahorra tiempo: calcularla cuesta más de lo que ahorra. Su ventaja aparece en redes grandes (P10).

**P10 · Escalabilidad: rejilla de 400 cámaras, 760 tramos, 300 consultas aleatorias (semilla 42)**

| Métrica | A\* sin heurística | A\* con heurística |
|---|---|---|
| Costo correcto (vs. NetworkX) | 300/300 | 300/300 |
| Nodos explorados (promedio) | 196.1 | 81.3 (**−58.5 %**) |
| Tiempo por consulta | 0.212 ms | 0.126 ms |

## Observaciones
- Los resultados deterministas (rutas, costos, nodos explorados) se repiten exactamente en cada ejecución.
- **Los tiempos varían entre ejecuciones** (por ejemplo, A\* dio 3.0 µs en la primera medición y 3.6 µs en la versión final del paquete). Para el paper se deben usar los de la ejecución final de `benchmark_grafo`.
- El conjunto de pruebas incluye casos que no estaban en el paper: vías de un sentido, tolerancia de velocidad y validación del JSON.

## Cómo reproducir
```bash
pytest -v
python -m evaluacion.benchmark_grafo    # escribe evaluacion/resultados/benchmark_grafo.json
```
Datos: [`datos/benchmark_grafo.json`](datos/benchmark_grafo.json)
