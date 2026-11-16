# FotoPapeleta Inteligente

Detección de infracciones de tránsito con visión por computadora y búsqueda de evidencia en una red de cámaras modelada como grafo (BFS, DFS, A\*). Proyecto APF2 · UTP · metodología CRISP-DM.

## Estructura

| Carpeta | Contenido | Responsable |
|---|---|---|
| `grafo/` | Módulos B y C: red de cámaras, BFS/DFS/A\*, velocidad por tramo, vínculo de evidencia. Python puro. | Carlos |
| `percepcion/` | Módulo A: YOLOv8, detector de placas, OCR con votación, worker. | Yazid / Rodrigo |
| `web/` | Proyecto Django + DRF: apps `camaras`, `infracciones`, `validacion` (API en `/api/`), `portal` (público, `/`) y `panel` (personal, `/panel/`); admin en `/admin/`. Tailwind v4 + HTMX + Alpine.js + Lucide. | Rodrigo / Tonny |
| `data/` | `grafo_camaras.json` (red de evaluación) y `muestras/` (no se versiona). | Carlos / Yazid |
| `evaluacion/` | Benchmarks y notebooks que generan las tablas del paper. | Juan Diego |
| `tests/` | Pruebas automáticas (comparadas contra NetworkX). | Todos |
| `prototipo/` | Diseño en pencil.dev (`prot.pen`) y su especificación. | Tonny |

Pruebas y experimentos: [`docs/pruebas/`](docs/pruebas/README.md).

Documentos: `plan_fotopapeleta_inteligente.md`, `arquitectura_fotopapeleta_inteligente.md` y el paper (`PAPER FOTOPAPELETA*.docx`).

## Puesta en marcha

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pytest                           # pruebas del grafo
python -m evaluacion.benchmark_grafo   # P9 y P10 de la Tabla II
```

Para el módulo de percepción (ML), además:

```bash
pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements-ml.txt
python -m percepcion.verificar_entorno   # GPU, YOLOv8 y EasyOCR
```

Resultado esperado en la PC del equipo (RTX 5070): CUDA disponible, YOLOv8n detecta `bus`, `person` y `stop sign` en ~8 ms, y EasyOCR lee `ABC-123` en la placa sintética.

Backend web (Django + API):

```bash
pip install -r requirements-web.txt
cd web
python manage.py migrate
python manage.py importar_red                       # cámaras y tramos desde data/grafo_camaras.json
python manage.py crear_roles --worker worker-demo   # grupos y token del worker
python manage.py createsuperuser                    # usuario para /admin/
python manage.py importar_eventos ../demo/salida/eventos.json
python manage.py runserver 8000                     # portal http://127.0.0.1:8000/ · panel /panel/ · /admin/ · /api/
python manage.py test                               # 42 pruebas (API y pantallas)
python manage.py tailwind build                     # solo si cambias clases en las plantillas (descarga Tailwind la primera vez)
python manage.py generar_demo --decidir             # vehículos simulados por el flujo real (quitar: --borrar)
python manage.py calcular_tramos                    # red de fiscalización por calles reales (OSRM) -> data/grafo_camaras_real.json
python manage.py importar_red ../data/grafo_camaras_real.json   # usarla (sin argumento: red de evaluación del paper)
python manage.py importar_red_transito              # cámaras públicas de Lima para «Tránsito en vivo»
python manage.py monitorear_transito                # cuenta vehículos en esas cámaras cada 2 min (requiere requirements-ml.txt)
```

En el panel, **Red → Subir evidencia** procesa una foto o un video con el mismo detector y OCR del worker (requiere `requirements-ml.txt` y los pesos en `runs/placas/yolov8n_peru/weights/best.pt`). La primera vez que alguien entra al panel aparece una guía interactiva; el botón «?» la repite.

Demo de punta a punta (cámaras simuladas → placa → evento → grafo → infracción):

```bash
python -m demo.demo_extremo_a_extremo    # salida en demo/salida/ (reporte.md e imagen de la infracción)
```

## Uso del paquete `grafo`

```python
from datetime import datetime, timedelta
import grafo

g, nodos = grafo.cargar("data/grafo_camaras.json")
grafo.bfs(g, "AV-01", k=2)                                   # cámaras candidatas
grafo.a_estrella(g, "AV-01", "AV-08", grafo.recta_km(nodos)) # ruta, costo, nodos explorados

t = datetime(2026, 10, 15, 8, 42)
grafo.velocidad_por_tramo(g, "AV-01", t, "AV-08", t + timedelta(seconds=120))
# -> v_conservadora=87.1, exceso=27.1, infraccion=True
```

## Convenciones

- Las aristas llevan `"dirigida": true` para vías de un solo sentido.
- Toda arista debe cumplir *distancia en línea recta ≤ km del tramo* (`grafo.validar` lo comprueba); si no, A\* con heurística deja de ser exacto.
- No se versionan imágenes ni videos con placas reales (Ley N.° 29733).
