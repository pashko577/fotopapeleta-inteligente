# FotoPapeleta Inteligente — Pendientes después del avance (APF2)

**Actualizado:** 15/10/2026
**Contexto:** la entrega actual es un **avance**. No se pudo grabar video ni tomar fotos de placas peruanas, así que el módulo de percepción se valida con datos públicos y sintéticos. Este archivo registra qué falta y cómo resolverlo, para que nada quede olvidado y para declararlo como limitación en el paper y la exposición.

---

## 1. Estado actual

| Componente | Estado | Evidencia |
|---|---|---|
| Grafo + BFS/DFS/A\* + velocidad por tramo (Módulos B y C) | **Completo y probado** | `grafo/`, 22 pruebas en `tests/`, Tabla II del paper |
| Metodología CRISP-DM en el paper | **Redactada** | `PAPER FOTOPAPELETA - con metodologia.docx` |
| Prototipo de interfaz (36 pantallas) | **Completo** | `prototipo/prot.pen` |
| Entorno de ML (GPU, YOLOv8, EasyOCR) | **Instalado y verificado** | `percepcion/verificar_entorno.py` |
| Detector de placas (YOLOv8n) | **Entrenado** con *Peru License Plate* y división propia sin fugas: prueba (97 img, 166 placas) P 95.6 %, R 91.3 %, mAP@50 96.5 %, mAP@50-95 75.0 %, 1.9 ms/img | `evaluacion/resultados/detector_yolov8n_peru.json`, `runs/placas/yolov8n_peru/` |
| OCR de placas (EasyOCR + formato + votación) | **Evaluado**: sintético (media) 46 % → 71 % con 9 cuadros; real 1 cuadro 23.3 % (30 placas transcritas a mano) | `docs/pruebas/06_ocr_placas.md` |
| Pipeline de punta a punta (video simulado) | **Funciona**: 3/3 decisiones correctas, 24–32 ms por cuadro; la placa V8D-001 se leyó VBD-001 (la corrige la validación humana) | `docs/pruebas/07_pipeline_extremo_a_extremo.md`, `python -m demo.demo_extremo_a_extremo` |
| Datos reales (video/fotos de Lima) | **Pendiente** | ver sección 3 |

---

## 2. Qué se usa en el avance en lugar de datos propios

| Necesidad | Sustituto para el avance | Limitación que se debe declarar |
|---|---|---|
| Placas peruanas para el ajuste fino del detector | *Peru License Plate* (Billy Soplin, Roboflow Universe), 1 000 imágenes de Lima, CC BY 4.0 | Fotos de terceros, no de nuestras cámaras; anota solo la caja, no el texto |
| Imágenes de placas para el preentrenamiento del detector | *Vehicle Registration Plates* (Augmented Startups, Roboflow Universe), 8 823 imágenes, licencia CC BY 4.0, descargado de Hugging Face (`keremberke/license-plate-object-detection`) | Placas de varios países, **no peruanas**; el formato y la tipografía difieren |
| Texto de las placas para medir el OCR (CER) | Placas peruanas **sintéticas** (formato ABC-123) con desenfoque, rotación, ruido y baja iluminación | Una placa sintética es más limpia que una real; el CER real será mayor |
| Video para probar la votación entre cuadros | Secuencias sintéticas (varias versiones degradadas de la misma placa) | No reproduce el movimiento real de un vehículo |
| Red de cámaras | Red esquemática de 6 cámaras con coordenadas proyectadas | Coordenadas no reales |

**Búsqueda de datos peruanos (15/10/2026):** en Hugging Face no existe ningún dataset público de placas peruanas. En Roboflow Universe se verificó **Peru License Plate** (Billy Soplin, 2024): 1 000 imágenes de calles de Lima, clase única `placa`, detección de objetos, licencia **CC BY 4.0**, 8 versiones. Su modelo publicado (`peru-license-plate/3`) reporta mAP@50 85.6 %, precisión 89.7 % y exhaustividad 75.8 %, que sirve como referencia. Se usó la **versión 9** (640 × 640); la v3 de ese modelo está a 320 × 240. Solo anota la caja de la placa, no el texto: para el OCR se usaron placas sintéticas y 30 placas reales transcritas a mano.

**NumberPlates (modelidentity-kq0nu, CC BY 4.0) — descartado:** sus 489 fotos de origen están todas incluidas en *Peru License Plate* (mismos nombres y misma imagen; solo cambian brillo y contraste por los aumentos). Además etiqueta con polígonos y dos clases equivalentes (`Placa`/`placa`). Combinarlo no aporta datos nuevos y, sin el control de duplicados, habría filtrado imágenes de entrenamiento a la prueba. Vale como ejemplo en el paper del control de calidad de datos de la fase de preparación. Se puede borrar `data/NumberPlates.v1i.yolov9.zip` y `datasets/numberplates/` (3.6 GB) si se necesita espacio.

Cita (BibTeX): `@misc{peru-license-plate_dataset, title={Peru License Plate Dataset}, type={Open Source Dataset}, author={Billy Soplin}, howpublished={\url{https://universe.roboflow.com/billy-soplin/peru-license-plate}}, journal={Roboflow Universe}, publisher={Roboflow}, year={2024}, month={oct}}`

**Frase sugerida para el paper / exposición:** *“En esta etapa, el detector de placas se entrenó y evaluó sobre un conjunto público de placas peruanas (CC BY 4.0) con una división propia sin fugas; el OCR se evaluó sobre placas peruanas sintéticas y sobre una muestra de 30 placas reales del mismo conjunto. La validación con capturas propias en video se realizará en la siguiente fase.”*

---

## 3. Pendientes (después del avance)

### 3.1 Datos reales — prioridad alta
| # | Tarea | Cómo | Responsable sugerido |
|---|---|---|---|
| D1 | Grabar clips con 2 celulares (app IP Webcam) en dos puntos con distancia conocida | Estacionamiento o calle tranquila, de día, celular fijo a 3–8 m de la placa | Yazid / Rodrigo |
| D2 | Tomar ~300 fotos de placas peruanas | Autos propios o de compañeros, con su consentimiento (Ley N.° 29733) | Todos |
| D3 | Etiquetar placas (caja) y transcribir el texto | Roboflow, clase `placa`; guardar el texto en un CSV | Yazid |
| D4 | Dividir 70/20/10 **por clip**, no por cuadro | Evita que cuadros casi iguales queden en entrenamiento y prueba | Juan Diego |
| D5 | Medir la distancia real entre los dos puntos de la demo | Google Maps o cinta métrica; actualizar `data/grafo_camaras.json` | Carlos |

### 3.2 Modelos
| # | Tarea | Depende de |
|---|---|---|
| M0 | Reentrenar el detector con la división regenerada (incluye las 25 imágenes con etiquetas mixtas que se ignoraron; ver `docs/pruebas/05`) | — |
| M1 | Ajuste fino del detector con placas peruanas (partiendo del modelo entrenado con el dataset público) | D2, D3 **o** un dataset peruano de Roboflow Universe |
| M2 | Medir la votación en placas **reales** (requiere video; el dataset solo tiene fotos sueltas) | D1 |
| M5 | **Verificar la transcripción** de las 30 placas reales (`evaluacion/resultados/ocr_real_transcripcion.csv`) por un segundo integrante | — |
| M6 | ✅ En gran parte (16/10): fast-plate-ocr `cct-xs-v2-global` sube la exactitud real de 23.3 % a 86.7 % (`docs/pruebas/12`). Falta: ampliar la prueba a más placas y, si hace falta, ajustarlo con placas peruanas | D2, D3 |
| M7 | Soportar placas de moto (`1738-YB`) y especiales (rojas/turquesa con letra pequeña) en `extraer_placa` | — |
| M11 | Ajustar fast-plate-ocr con placas peruanas (CARID dividido por placa) para corregir la confusión T→Y (54 casos) y 0/O, 5/S; medir con la parte de CARID no usada | Rodrigo |
| M10 | ✅ En parte (16/10): detector v2 con 281 fotos nuevas de peruvian_plates (`docs/pruebas/14`). Más datos para el detector: cualquier dataset nuevo debe pasar `auditar_duplicados` contra `datasets/peru_billy` antes de usarse. Ya se descartaron NumberPlates y ProyectoYOLOUCSP por ser copias (`docs/pruebas/03`). Lo que más aportaría: capturas propias de la zona de la demo y placas pintadas (M9) | Yazid |
| M9 | **Placas pintadas en la carrocería** (combis, buses y taxis llevan la placa pintada a los costados, letras negras sobre la pintura, sin marco). El detector no las reconoce: en un video real de una combi no detectó «B2W 750» en ningún cuadro (sí el número de unidad «1068», que no es placa). Tareas: (1) reunir 100–200 imágenes de combis/taxis con la placa del costado visible y etiquetarlas en Roboflow como `placa`; (2) reentrenar YOLOv8n con el dataset actual + este (misma división por grupos sin fugas); (3) medir aparte la detección de placas pintadas; (4) descartar números de unidad de 4 dígitos («1068») por formato. Aun entrenado, la placa debe verse con ≥ 80 px de ancho: en ese video medía 45 px y el OCR leyó «BAH750» | Yazid / Rodrigo |
| M8 | Asegurar que las cámaras capturen la placa con ≥ 80 px de ancho (la exactitud real sube de 23 % a 38.5 %) | D1 |
| M3 | Reglas de infracción además de velocidad: semáforo en rojo (COCO trae `traffic light`), luego cruce peatonal | D1 |
| M4 | Opcional: uso de celular, giro prohibido, sentido contrario | Tiempo disponible |

### 3.3 Sistema
| # | Tarea | Responsable sugerido |
|---|---|---|
| S1 | `percepcion/worker.py`: conectar el pipeline (`percepcion/pipeline.py`, ya hecho y probado con video simulado) a la cámara del celular o a un clip y enviar los eventos a la API | Rodrigo |
| S6 | ✅ Hecho (16/10): `grafo.evaluar_evento()` lo usan la API y la demo | Tonny / Rodrigo |
| S2 | ✅ Hecho (16/10): proyecto Django + DRF con modelos, admin, `POST /api/eventos/`, validación y papeletas (`docs/pruebas/08`). Falta: subir las imágenes de evidencia desde el worker | Tonny / Rodrigo |
| S3 | ✅ Hecho (16/10): portal y panel en Django + Tailwind v4 + HTMX + Alpine (`docs/pruebas/09`). Usuarios de prueba solo en la BD local | Tonny / Rodrigo |
| S4 | ✅ En parte (16/10): ubicaciones de OpenStreetMap y tramos por calles reales con OSRM (`docs/pruebas/13`). Falta: el GPS real de cada celular en `data/camaras_reales.json` y `calcular_tramos` | Carlos |
| S5 | Sincronización de hora de los celulares y medición del error real de reloj (ε) | Rodrigo |
| T1 | Tránsito en vivo: validar el conteo de vehículos contra un conteo manual de 1 minuto en 3 cámaras y ajustar los umbrales del seguimiento; acumular varios días de mediciones para que «lo normal» sea representativo | Juan Diego |
| T2 | Si se quiere usar la señal más allá del uso académico (fiscalizar, retransmitir), pedir permiso a la Municipalidad de Lima | Tonny |
| S7 | Difuminar placas y rostros de terceros en la evidencia del portal (Ley 29733); hoy el portal no lo promete | Yazid |
| S8 | Que el worker envíe la caja de la detección (x, y, ancho, alto) para dibujarla sobre la evidencia en la validación | Rodrigo |
| S9 | Latido de cada celular-cámara para mostrar «en línea / sin señal» real (hoy: «con capturas en los últimos 5 min») | Rodrigo |
| S10 | Página del celular (`/panel/captura/celular/`): enviar cuadros al worker; requiere HTTPS en la red local | Rodrigo |

### 3.4 Paper
| # | Tarea |
|---|---|
| P1 | Corregir en la introducción: “Abd Ali et al.” → “Ali [6]”, “[[4]”, el correo “U U22209570”, y las dos frases mal construidas del párrafo de problemática |
| P2 | Revisar la cifra del MTC (1,117 casos): periodo y ámbito |
| P3 | Importar las referencias [10]–[20] en Mendeley |
| P4 | ✅ Hecho (16/10): Tabla II con los tiempos finales. Volver a ejecutar `python -m evaluacion.benchmark_grafo` y copiar los tiempos finales a la Tabla II |
| P5 | ✅ Hecho (16/10): Tablas III y IV en el paper. Agregar la tabla de percepción con los resultados del detector y del OCR sintético, declarando la limitación |
| P7 | ✅ Hecho (16/10): sección C del paper. Explicar en la metodología la división propia sin fugas: la división original de *Peru License Plate* repetía 4/53 imágenes de prueba y 17/128 de validación (copias exactas y fotos de la misma cámara fija con el mismo fondo), por lo que su mAP@50 publicado de 85.6 % puede estar sobreestimado; se agruparon 2 626 imágenes en 927 grupos (dHash ≤ 6 bits) y se asignó cada grupo a un solo split |
| P8 | Con solo 97 imágenes de prueba la métrica tiene un margen de variación amplio; reforzar con datos propios (NumberPlates no sirve: duplica a Billy) |
| P10 | Las referencias [21] y [22] (datasets) se agregaron como texto después del bloque de Mendeley; importarlas también en Mendeley |
| P9 | ✅ Hecho (16/10): sección C del paper. Mencionar en la metodología que se descartó NumberPlates por ser un subconjunto duplicado de *Peru License Plate*, detectado con el control de duplicados |
| P6 | Redactar Abstract, Keywords, Resultados y Conclusiones |
| P12 | ✅ Hecho (16/10, paper v4). Actualizar la Tabla IV y el texto de lectura de placas con fast-plate-ocr (86.7 % frente a 23.3 %; 92.3 % con placas ≥ 80 px) y mencionar los filtros de confianza y de repetición del pipeline |
| P13 | Verificar en la fuente e importar en Mendeley las referencias nuevas [23] fast-plate-ocr, [24] OSRM (Luxen y Vetter, 2011), [25] ByteTrack (ECCV 2022) y los datasets [26] UCSP, [27] peruvian_plates y [28] CARID |
| P14 | El paper pasó a 10 páginas: revisar el límite de la convocatoria; candidatos a recortar: Fig. 7 y la subsección Tránsito en vivo |
| P11 | ✅ Hecho (16/10, paper v4). En la sección D del paper, precisar que la velocidad se evalúa entre **capturas consecutivas** de la misma placa (corrección del 16/10: antes un recorrido de 3 cámaras se contaba dos veces) |

### 3.5 Decisiones pendientes
- Fecha real de entrega del APF2.
- ¿El prototipo web cuenta como entregable formal de “despliegue”?
- Confirmar con el docente si datos públicos + sintéticos son aceptables para el avance.
