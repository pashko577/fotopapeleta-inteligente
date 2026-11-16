# Registro de pruebas y experimentos

**Proyecto:** FotoPapeleta Inteligente · APF2 · UTP
**Periodo:** 15/10/2026
**Equipo de cómputo:** AMD Ryzen 5 9600X, 16 GB de RAM, NVIDIA GeForce RTX 5070 (12 GB), Windows 11

**Documento único con todas las pruebas:** [INFORME_COMPLETO.md](INFORME_COMPLETO.md)

## Índice

| # | Documento | Qué se probó | Resultado principal |
|---|---|---|---|
| 01 | [Módulo de grafo](01_modulo_grafo.md) | BFS, DFS, A\*, velocidad por tramo, vínculo de evidencia | 22/22 pruebas automáticas; A\* correcto en 30/30 pares; −58.5 % de nodos explorados con heurística (400 cámaras) |
| 02 | [Entorno de ML](02_entorno_ml.md) | GPU, PyTorch, YOLOv8, EasyOCR | Todo funcional; YOLOv8n en ~8 ms por imagen |
| 03 | [Datos y control de fugas](03_datos_y_control_de_fugas.md) | Búsqueda de datasets, auditoría de duplicados, división propia | División original con fugas (4/53 prueba, 17/128 validación); NumberPlates descartado por duplicar a Billy |
| 04 | [Entrenamiento del detector YOLOv8n](04_entrenamiento_detector_yolov8n.md) | 100 épocas sobre placas peruanas | Prueba: P 95.6 %, R 91.3 %, mAP@50 96.5 %, mAP@50-95 75.0 %, 1.9 ms/img |
| 05 | [Incidencias y lecciones](05_incidencias_y_lecciones.md) | Problemas encontrados y cómo se resolvieron | Incidencias de entrenamiento, datos y OCR |
| 06 | [OCR de placas y votación](06_ocr_placas.md) | EasyOCR + preproceso + formato + votación; placas sintéticas y reales | Sintético (media): 46 % → 71 % con 9 cuadros. Real (1 cuadro, 30 placas): 23.3 % |
| 07 | [Pipeline de punta a punta](07_pipeline_extremo_a_extremo.md) | Cuadros → detección → seguimiento → OCR con votación → evento → grafo → decisión | 3/3 decisiones correctas (infracción, sin infracción, alerta); 24–32 ms por cuadro; una placa mal leída (8↔B) que corrige la validación humana |
| 08 | [Backend Django](08_backend_django.md) | API, base de datos, validación humana y papeletas; prueba en vivo | 16 pruebas de la API; la prueba en vivo encontró y corrigió un error en el filtro de plausibilidad |
| 14 | [Nuevos datasets](14_nuevos_datasets.md) | Auditoría de 3 datasets; OCR con 958 placas de CARID; detector v2 con peruvian_plates | UCSP y CARID son copias; OCR 62.3 % (vs 10.3 % EasyOCR); detector v2 mAP@50 97.1 % y 91.5 % en fotos difíciles |
| 13 | [Red real por calles](13_red_real_osrm.md) | Ubicaciones reales y tramos por calles (OSRM) sin que el grafo supere la distancia real | 13 tramos; en los 15 pares, grafo = distancia real; AV-01–AV-08 era 3.0 km a mano y es 0.95 km |
| 12 | [OCR especializado en placas](12_ocr_fast_plate_ocr.md) | fast-plate-ocr frente a EasyOCR en las mismas 30 placas reales; video real de un taxi | **86.7 % frente a 23.3 %** (92.3 % en placas ≥ 80 px), 3.3 ms por placa; el video pasa de «ninguna placa» a ACO-484 |
| 11 | [Tránsito en vivo](11_transito_en_vivo.md) | Cámaras públicas de Lima: ¿leen placas? Conteo de vehículos y A* con tiempos dinámicos | Placas de 16–40 px: ilegibles (0 lecturas). Vehículos: detectados en las 15 cámaras; red real de 15 nodos y 19 tramos |
| 10 | [Datos de demostración, subir evidencia y guía](10_datos_demo_subida_tutorial.md) | Vehículos simulados por el flujo real; foto o video por el pipeline del worker; recorrido guiado | 95 infracciones simuladas decididas por el sistema; foto real → INF-000288; video: 28/30 lecturas; 2 errores de lógica encontrados y corregidos |
| 09 | [Pantallas web](09_pantallas_web.md) | Portal ciudadano y panel (prototipo de pencil.dev pasado a Django + Tailwind + HTMX + Alpine) | 26 pruebas de pantallas; flujo completo en el navegador: corregir placa → aprobar → papeleta → consulta → revisión |

## Resumen de resultados para el paper

| Módulo | Métrica | Valor | Fuente |
|---|---|---|---|
| Búsqueda (grafo) | Costo de A\* correcto vs. NetworkX | 30/30 pares (red de 6 cámaras), 300/300 consultas (400 cámaras) | [01](01_modulo_grafo.md) |
| Búsqueda (grafo) | Reducción de nodos explorados con heurística | 58.5 % (196.1 → 81.3) | [01](01_modulo_grafo.md) |
| Velocidad por tramo | Caso ABC-123 (3.0 km en 120 s) | 87.1 km/h conservadora, exceso +27.1 km/h | [01](01_modulo_grafo.md) |
| Detector de placas | mAP@50 en prueba sin fugas (97 imágenes, 166 placas) | 96.5 % | [04](04_entrenamiento_detector_yolov8n.md) |
| Detector de placas | Precisión / exhaustividad en prueba | 95.6 % / 91.3 % | [04](04_entrenamiento_detector_yolov8n.md) |
| Detector de placas | Tiempo de inferencia (RTX 5070) | 1.9 ms por imagen | [04](04_entrenamiento_detector_yolov8n.md) |
| OCR (sintético, calidad media) | Placa correcta 1 cuadro → 9 cuadros | 46.4 % → 71.0 % (CER 26.8 % → 5.3 %) | [06](06_ocr_placas.md) |
| OCR (real, 1 cuadro, 30 placas de auto) | Placa correcta / CER | 23.3 % / 56.1 % (38.5 % / 34.6 % con placas ≥ 80 px) | [06](06_ocr_placas.md) |
| Sistema completo (demo, video simulado) | Decisiones correctas / tiempo por cuadro | 3/3 · 24–32 ms (detector + OCR) | [07](07_pipeline_extremo_a_extremo.md) |

## Archivos de soporte
- [`datos/`](datos/): resultados en bruto (CSV de las 100 épocas, JSON de métricas, configuración del entrenamiento, reporte de la división).
- [`img/`](img/): figuras listas para el paper y la exposición.

## Cómo reproducir todo

```bash
.venv\Scripts\activate
pytest                                         # 66 pruebas: grafo, decisión, OCR y pipeline
cd web && python manage.py test               # 16 pruebas de la API (Django)
python -m evaluacion.benchmark_grafo           # 01: P9 y P10
python -m percepcion.verificar_entorno         # 02
python -m percepcion.datos.auditar_duplicados datasets/peru_billy                     # 03
python -m percepcion.datos.construir_split datasets/combinado datasets/peru_billy     # 03
python -m percepcion.entrenar_detector         # 04 (~21 min en RTX 5070)
python -m evaluacion.evaluar_ocr_sintetico --placas 200   # 06 (~4.5 min)
python -m evaluacion.recortar_placas_reales    # 06
python -m evaluacion.evaluar_ocr_real          # 06
python -m demo.demo_extremo_a_extremo          # 07
```
