# Contexto del proyecto — FotoPapeleta Inteligente

> Documento para dar contexto a Claude (web o app) sobre el proyecto, su estado y las decisiones tomadas. Resume el trabajo hecho con Claude Code hasta el 17/10/2026. Para el detalle de cada prueba, ver `docs/pruebas/` (01 a 14) e `INFORME_COMPLETO.md`.

## 1. Qué es
Proyecto universitario **APF2 · Universidad Tecnológica del Perú (UTP)**, metodología **CRISP-DM**. Título del paper: *Hacia una Fiscalización Vial Inteligente: Detección de Infracciones y Seguimiento Vehicular mediante Algoritmos de Búsqueda*.

Sistema que detecta **exceso de velocidad sin radar**:
- lee la placa de un vehículo en varias cámaras (visión por computadora);
- modela la red de cámaras como un **grafo** y calcula la velocidad promedio entre dos cámaras con la distancia mínima (BFS, DFS, A*);
- **ninguna papeleta se emite sin validación humana**;
- el ciudadano consulta su papeleta y puede pedir revisión.

**Equipo (5):** Tonny Hinostroza (líder, arquitectura), Carlos (grafo), Yazid (percepción y datos), Rodrigo (backend y worker), Juan Diego (evaluación). Idioma de trabajo: español; entregables orientados a defender el proyecto ante el docente.

## 2. Decisiones ya tomadas (no reabrir sin motivo)
| Tema | Decisión |
|---|---|
| Backend | Django 5.2 + Django REST Framework, SQLite en desarrollo |
| Frontend | Plantillas Django + Tailwind CSS v4 (sin Node, `django-tailwind-cli`) + HTMX + Alpine.js + íconos Lucide. No React/Angular |
| Diseño | Prototipo en pencil.dev (`prototipo/prot.pen`, 36 pantallas) según `prototipo/diseno_prototipo_pencil.md` |
| Cámaras | Celulares con IP Webcam como nodos del grafo (fiscalización); cámaras públicas solo para conteo de tráfico |
| Detector | YOLOv8n ajustado con placas peruanas (v2 activo; v1 fijo para reproducir resultados del paper) |
| OCR | fast-plate-ocr `cct-xs-v2-global` (antes EasyOCR) + reglas del formato peruano + votación entre cuadros |
| Velocidad | Conservadora, a favor del conductor: v_c = 3600·d_min/(Δt + 2ε), ε = 2 s, tolerancia 5 km/h |
| Placa clonada | Si recorrer la distancia mínima exige > 200 km/h → alerta, no infracción |
| Datos personales | Ley N.° 29733; el difuminado de terceros está pendiente (no prometerlo como hecho) |
| SUNARP | No integrar la consulta pública (captcha, datos personales). Opción futura: convenio vía PIDE |

## 3. Arquitectura y código
Seis capas: captura → percepción → datos y grafo → análisis → validación humana → consulta.

| Carpeta | Contenido |
|---|---|
| `grafo/` | **Algoritmo principal**, Python puro: `modelo.py` (construir, validar), `busqueda.py` (bfs, dfs, a_estrella), `heuristicas.py`, `velocidad.py`, `evidencia.py` (misma_placa, plausibilidad), `decision.py` (evaluar_evento) |
| `percepcion/` | `pipeline.py` (detector, seguimiento por IoU ≥ 0.3, votación, eventos; filtros de confianza ≥ 0.5 y repetición ≤ 5 s; placas no leídas para registro manual), `ocr.py`, `datos/` (auditoría de duplicados, divisiones) |
| `web/` | Apps `camaras`, `infracciones`, `validacion` (API), `portal` (ciudadano), `panel` (personal), `transito` (tráfico en vivo) |
| `evaluacion/` | Benchmarks y evaluaciones; resultados en `evaluacion/resultados/*.json` |
| `data/` | `grafo_camaras.json` (red esquemática del paper), `grafo_camaras_real.json` (calles reales, OSRM), `camaras_reales.json` (ubicaciones), `red_transito.json` |
| `docs/` | `pruebas/01–14`, `INFORME_COMPLETO.md`, `guion_exposicion.md` |

**Algoritmos:**
- **BFS:** cámaras a ≤ k = 2 saltos; ahí se busca la misma placa.
- **DFS** acotado: enumera rutas posibles (laboratorio).
- **A*** con heurística de línea recta (admisible): distancia mínima. Con peso en minutos se usa línea recta ÷ velocidad máxima de la red.
- **Decisión:** cada captura nueva se compara solo con la captura más cercana en el tiempo (tramos consecutivos A–B, B–C; nunca A–C). Una placa con 1 carácter distinto queda «a verificar».

**Red real:** ubicaciones de OpenStreetMap y tramos por calles con OSRM. Regla: para todo par de cámaras, la distancia del grafo ≤ la real; si no, se agrega el tramo directo. Resultado: 13 tramos, igual a la real en los 15 pares. Ejemplo: AV-01–AV-08 medía 3.0 km a mano y 0.95 km por calles.

## 4. Sistema web (funcionando)
- **Portal ciudadano:** consulta por placa, detalle con evidencia y trayectoria, solicitud de revisión, impresión, Cómo funciona, Ayuda.
- **Panel:** Resumen, Validación (aprobar/rechazar/escalar con atajos A/R/E, corregir placa), Infracciones (filtros HTMX, CSV), Papeletas (anular con motivo), Cámaras (mapa real OpenStreetMap), Captura en vivo, **Subir evidencia** (foto o video por el mismo pipeline; placas no leídas con recorte para escribirlas a mano), **Tránsito en vivo**, Laboratorio del grafo, Reportes, Configuración (parámetros editables), Usuarios.
- **Roles:** worker (token), validador, administrador. Auditoría completa de cada infracción.
- **Guía interactiva** (driver.js) en el primer ingreso; tema claro y oscuro; versión móvil.
- **Datos de demostración:** `python manage.py generar_demo --decidir` simula 250 vehículos por el flujo real (95 infracciones, 4 alertas); se borra con `--borrar`.
- **Ejecutar:** `cd web` → `python manage.py runserver 8000` → portal `http://127.0.0.1:8000/`, panel `/panel/`.

**Tránsito en vivo (extensión):** 15 cámaras públicas de Lima (señal de la Municipalidad vía Claro, uso académico). YOLOv8n COCO + ByteTrack cuentan vehículos (no leen placas: miden 16–40 px). La congestión es relativa a lo normal de cada cámara y A* calcula la ruta más rápida. Monitor: `python manage.py monitorear_transito`.

## 5. Resultados (números vigentes)
| Componente | Resultado |
|---|---|
| A* vs NetworkX | Costo correcto 30/30 (6 cámaras) y 300/300 (400 cámaras); heurística −58.5 % de nodos explorados |
| Velocidad | 3.0 km en 120 s → 87.1 km/h conservadora (+27.1 en zona de 60) |
| Detector v1 (paper) | Prueba sin fugas 97 imágenes: P 95.6 %, R 91.3 %, mAP@50 96.5 %, mAP@50-95 75.0 % |
| Detector v2 (activo) | P 95.1 %, R 93.8 %, mAP@50 97.1 %; segunda prueba (20 difíciles) R 83.3 → 91.7 % |
| OCR, 30 placas reales | EasyOCR 23.3 % → fast-plate-ocr 86.7 % (optimista por la muestra pequeña) |
| OCR, CARID 958 placas | fast-plate-ocr 62.3 % (≈68 % sin errores de etiqueta) vs EasyOCR 10.3 %; 39.1 % a 40 px; error dominante T→Y |
| Sistema completo (demo) | 3/3 decisiones correctas; 24–32 ms por cuadro |
| Pruebas automáticas | 139 (72 de módulos + 67 de la web), todas aprobadas |

**Errores de lógica encontrados y corregidos (con prueba de regresión):**
1. Un auto a 94.7 km/h se trataba como placa clonada (criterio de plausibilidad mal planteado).
2. Un recorrido de 3 cámaras se multaba dos veces.
3. Subir dos veces la misma captura duplicaba la infracción.

**Datasets:**
- Peru License Plate (Billy Soplin, CC BY 4.0): base del entrenamiento.
- Descartados por ser copias de esa base: NumberPlates y ProyectoYOLOUCSP.
- peruvian_plates (dominio público): 281 fotos nuevas usadas en v2.
- CARID (MIT): solo para evaluar el OCR.
- Todo dataset nuevo pasa por `auditar_duplicados` (dHash ≤ 6 bits, sin bordes negros).

**Limitaciones honestas:**
- un solo dataset base;
- videos reales pocos y comprimidos (WhatsApp 848 × 480);
- placas pintadas en combis y taxis no detectadas por v2 (v1 leía ACO-484 en la puerta de un taxi);
- coordenadas aproximadas;
- solo se implementó exceso de velocidad;
- el conteo de tráfico no está validado manualmente.

## 6. Paper
- **Archivo:** `PAPER FOTOPAPELETA - con metodologia.docx` (versión 5, **10 páginas**, formato IEEE / LACCEI). Se genera con un script desde el original `PAPER FOTOPAPELETA.docx`, que nunca se modifica.
- **Contenido de la sección II Metodología (CRISP-DM, A–F):**
  - Tablas: I (red), II (pruebas del grafo, P1–P10), III (detector v1 y v2), IV (lectura: sintético, 30 reales, CARID), V (pruebas funcionales F1–F9).
  - Figuras: 1 CRISP-DM, 2 laboratorio A*, 3 evidencia de infracción, 4 arquitectura, 5 validación real, 6 detección en cámara pública, 7 tránsito en vivo.
  - Referencias [1]–[28]; [10]–[28] agregadas como texto después del bloque Mendeley.
- **Pendientes del paper:**
  - P6: redactar Resumen, Palabras clave, Resultados y Conclusiones.
  - P13: verificar e importar en Mendeley [23]–[28].
  - P14: revisar el límite de páginas; candidatos a recortar: Fig. 7 y la subsección Tránsito en vivo.
  - P1, P2: correcciones de la introducción y la cifra del MTC.

## 7. Entregables ya preparados
- `Entregable_FotoPapeleta_Inteligente.zip` (32 MB): código, modelos, documentación y `LEEME_ENTREGA.md`. Probado: 139 pruebas pasan desde el .zip.
- `Algoritmo_FotoPapeleta_Inteligente.pdf` (4 páginas): flujo, ML, BFS/DFS/A* en pseudocódigo, fórmula, resultados y dónde está cada algoritmo.
- `docs/guion_exposicion.md`: guion de 13–15 min con reparto por integrante y preguntas probables.

**Guion de 30 s (algoritmos):** «Cada cámara es un nodo y cada calle una arista con su distancia real. BFS busca la misma placa en las cámaras vecinas; DFS recorre las rutas posibles; A* encuentra la más corta guiándose por la línea recta y explora 58 % menos nodos. Con esa distancia mínima calculamos la velocidad.»

**Código a mostrar en video:**
- `grafo/busqueda.py`: bfs (líneas 10–21), dfs (24–39), a_estrella (42–67);
- `grafo/heuristicas.py:10`;
- `grafo/velocidad.py:27` y `:35`;
- luego Panel → Laboratorio del grafo.

## 8. Pendientes principales (ver `PENDIENTES.md`)
- **M2:** probar con video real propio, grabado a 1080p, con la placa a ≥ 80 px y el archivo sin comprimir.
- **M9:** dataset de placas pintadas en combis y taxis para reentrenar el detector.
- **M11:** ajustar el OCR con placas peruanas (CARID dividido por placa) para la confusión T→Y.
- **S1:** conectar el worker a las cámaras y a la API.
- **S4:** GPS real de cada celular en `data/camaras_reales.json`, luego `calcular_tramos` e `importar_red`.
- **S7:** difuminar terceros. **S8:** recuadro de detección. **S9:** latido de cámaras. **S10:** envío de cuadros desde la página del celular.
- **T1:** validar el conteo de tráfico manualmente. **T2:** permiso de la Municipalidad si se usa la señal más allá de lo académico.
- **Despliegue:** la web cabe gratis en PythonAnywhere; el ML no (necesita GPU o mucha RAM). Para la exposición se recomienda correr en la laptop y, si hace falta un enlace, un túnel (Cloudflare o ngrok).

## 9. Entorno
Windows 11, AMD Ryzen 5 9600X, 16 GB RAM, **RTX 5070**. Python 3.12.10, PyTorch 2.11 (cu128), Ultralytics 8.4, EasyOCR 1.7.2, fast-plate-ocr 1.1.0 (instalado `--no-deps`), OpenCV 5.0, Django 5.2.18. Entorno virtual: `.venv`. El puerto 8765 está ocupado por otro programa; usar 8000.
