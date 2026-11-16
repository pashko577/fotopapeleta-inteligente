# 05 · Incidencias y lecciones

Registro de los problemas que aparecieron durante las pruebas, su causa y cómo se resolvieron. Sirve para que otro integrante no repita los mismos errores.

## Entrenamiento y datos

| # | Incidencia | Causa | Solución |
|---|---|---|---|
| I1 | El primer entrenamiento falló al instante: *"images not found, missing path ...\valid\images"* | El `data.yaml` decía `path: .`, y Ultralytics lo interpreta relativo a la carpeta desde donde se ejecuta, no a la del dataset | `construir_split` escribe ahora la ruta absoluta |
| I2 | **El segundo entrenamiento se colgó sin avisar**: la GPU tenía memoria ocupada pero no avanzaba ninguna época | En Windows, cada proceso de carga de datos vuelve a cargar PyTorch completo (2–3 GB de memoria virtual). Con 4 procesos y 16 GB de RAM se agotó el archivo de paginación (*WinError 1455*); los procesos auxiliares murieron y el principal quedó esperando | 2 procesos de carga (`--workers 2`), detención manual de los procesos colgados y un **monitor** que avisa por época y ante cualquier error |
| I3 | Error al copiar imágenes: *"El sistema no puede encontrar la ruta especificada"* | Los nombres de Roboflow (`Foto-Placa-368-_jpg.rf.0ffbf1d9cc24957e9e835d59925f6e0d.jpg`) más la ruta del proyecto superan el límite de 260 caracteres de Windows | Nombres cortos (`peru_billy_00063.jpg`) y un archivo `mapa_archivos.json` con el nombre original |
| I4 | 24 imágenes de entrenamiento y 1 de prueba ignoradas (*"labels mix segment and detection rows"*) | En *Peru License Plate* algunas etiquetas mezclan cajas y polígonos en el mismo archivo | Detectado al revisar el log **después** de entrenar. `construir_split` ahora convierte todo a cajas; el próximo entrenamiento las incluirá |
| I5 | La división original del dataset tenía fugas | Copias de la misma foto y fotos de la misma cámara fija repartidas entre entrenamiento, validación y prueba | División propia por grupos ([03](03_datos_y_control_de_fugas.md)) |
| I6 | NumberPlates parecía un dataset distinto | Las miniaturas de Roboflow se ven oscuras | El control de duplicados mostró que sus 489 fotos están en Billy; se descartó |

## Errores de análisis que se corrigieron

Se dejan registrados porque muestran por qué hay que verificar con los datos antes de concluir.

| # | Afirmación inicial | Qué estaba mal | Corrección |
|---|---|---|---|
| E1 | "629 imágenes de NumberPlates no tienen placas" | `wc -l` cuenta saltos de línea: un archivo con una sola etiqueta y sin salto final cuenta como 0 | Recontando las líneas no vacías, todas las imágenes tienen entre 1 y 8 placas |
| E2 | "Los pares casi idénticos son cuadros consecutivos de una ráfaga" | Al mirar las imágenes, son **autos distintos** desde la **misma cámara fija** | Se describen como "misma cámara y mismo fondo"; agruparlas sigue siendo correcto |
| E3 | "NumberPlates y Billy son distintos" (según las miniaturas) | Las miniaturas engañan | Comparación con imágenes completas: son las mismas fotos |
| E4 | "La prueba tiene 98 imágenes" | Ultralytics descartó una por etiquetas mixtas (I4) | La prueba efectiva es de **97 imágenes y 166 placas** |

## OCR

| # | Incidencia | Causa | Solución |
|---|---|---|---|
| O1 | En las placas sintéticas se cortaban el primer y el último carácter | Tamaño de letra fijo; con algunas fuentes el texto no cabía | El tamaño se reduce hasta que el texto cabe con margen |
| O2 | El nivel "difícil" era ilegible incluso para una persona | Placa de 40–60 px, muy oscura y con movimiento fuerte | Recalibrado a 55–80 px y algo más de luz |
| O3 | "PERÚ" con tilde quedaba como "PER" | La Ú se eliminaba antes de quitar la palabra | Se quitan las tildes antes de filtrar (detectado por una prueba automática) |
| O4 | En el nivel fácil la exactitud no pasaba de 74 % y la votación no ayudaba | Errores sistemáticos del OCR (5→S, 0→O) que se repiten en todos los cuadros | Ajuste de formato extendido a las posiciones 1 y 3 (78 %); la posición 2 sigue ambigua |
| O5 | El recorte de la zona de texto empeoró la lectura real (23.3 % → 6.7 %) | Al quitar la franja se cortaba también la parte superior de los caracteres | Se descartó; la función queda marcada como experimental |
| O6 | Las mejoras de extracción se diseñaron mirando los mismos 30 errores reales | Riesgo de ajustar a la prueba | Se verificaron en el sintético (independiente) y se declara el sesgo optimista |

## Pipeline de punta a punta

| # | Incidencia | Causa | Solución |
|---|---|---|---|
| D1 | En la primera demo no se detectó la infracción de V8D-001 | La simulación acercaba la imagen al centro y la placa salía del cuadro | El acercamiento sigue a la placa (posición tomada de la etiqueta, no del detector) |
| D2 | D9R-052 y DOR-052 no se vinculaban entre cámaras | `misma_placa` solo aceptaba caracteres confundibles, no un carácter cualquiera como decía la arquitectura | Un carácter distinto → "a verificar" (siempre con filtro de plausibilidad y validación humana) |
| D4 | **Un auto a 94.7 km/h en zona de 60 generaba una alerta de placa clonada en lugar de una infracción** (detectado en la prueba en vivo de la API, [08](08_backend_django.md)) | El filtro temporal rechazaba todo lo que superara el doble de la velocidad típica del tramo (45 → 90 km/h): justo los autos más rápidos nunca se multaban | Criterio de **velocidad máxima plausible (200 km/h)** por la ruta más corta; pruebas de regresión con el caso exacto |
| D3 | El resultado listaba las lecturas erróneas como "otras placas en las fotos" | Nombre engañoso | Renombrado a "lecturas distintas de la esperada" |

## Entorno y herramientas

| # | Incidencia | Solución |
|---|---|---|
| H1 | La primera medición de la GPU (220 ms) incluía la inicialización de CUDA | Operación de calentamiento antes de medir (7.6 ms real) |
| H2 | La versión de PyTorch de PyPI no reconoce la RTX 5070 | Instalar desde el índice de CUDA 12.8 (`--index-url .../whl/cu128`) |
| H3 | El entorno trajo NetworkX 3.6.1; el paper cita 3.7 | Fijado `networkx==3.7` |
| H4 | Los tiempos del benchmark del grafo varían entre ejecuciones | Usar en el paper los de la ejecución final; los resultados deterministas no cambian |
| H5 | El primer script de pruebas del grafo trataba todas las vías como de doble sentido | El paquete `grafo/` respeta `"dirigida"`; prueba `test_via_de_un_sentido` |

## Lecciones
1. **Revisar el log completo después de entrenar**, no solo las métricas finales: ahí aparecieron las 25 imágenes ignoradas.
2. **Nunca usar la división de un dataset público sin auditarla.**
3. **Verificar visualmente** las conclusiones automáticas (duplicados, "imágenes vacías") con algunos ejemplos.
4. **En Windows, empezar con pocos procesos de carga** y vigilar que avancen las épocas.
5. **Fijar semillas y versiones** para que los resultados del paper sean reproducibles.
