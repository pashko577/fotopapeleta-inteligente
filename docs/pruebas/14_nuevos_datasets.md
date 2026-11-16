# 14 · Nuevos datasets: auditoría, OCR con CARID y reentrenamiento del detector

## 1. Auditoría de los tres datasets (control de duplicados)
Todo dataset nuevo se compara con Peru License Plate [21] (el usado para entrenar) por nombre de origen y por dHash (≤ 6 bits, también volteado y **sin los bordes negros** que algunos agregan para llevar la foto a 640 × 640).

| Dataset | Imágenes | Fotos de origen | Repetidas de [21] | Nuevas | Licencia | Decisión |
|---|---|---|---|---|---|---|
| ProyectoYOLOUCSP (jdvp) | 2 637 | 985 | 982 | 3 | CC BY 4.0 | Descartado (copia) |
| peruvian_plates v2 (farichula) | 5 515 | 956 | ~700 | **281 grupos (849 imágenes)** | Dominio público | **Entrenar el detector** |
| CARID v3 | 1 633 | 650 | 650 | 0 | MIT | **Evaluar el OCR** (etiquetas por carácter) |

**Incidencia al ampliar la división:** la primera pasada daba 2 502 fotos «nuevas», por dos motivos:
- **Por nombre:** `combinado` había renombrado los archivos y la función de origen recibía el nombre sin extensión, así que nunca encontraba coincidencias.
- **Por imagen:** peruvian_plates rellena con bordes negros y el dHash no reconocía la misma foto.

Con ambas correcciones quedaron 849 imágenes (281 grupos). Script: `python -m percepcion.datos.ampliar_split datasets/combinado datasets/peruvian_plates datasets/combinado_v2`.

## 2. OCR evaluado con CARID (958 placas distintas)
CARID etiqueta cada carácter; el texto real de cada placa se reconstruye ordenando los caracteres dentro de su recuadro. Se obtuvieron **2 669 placas con texto válido, 958 distintas** (una muestra por placa). Además del tamaño original, cada recorte se redujo a 120, 80, 60 y 40 px de ancho para simular la distancia. Script: `python -m evaluacion.evaluar_ocr_carid` → `evaluacion/resultados/ocr_carid.json`.

| Ancho de la placa | fast-plate-ocr | EasyOCR |
|---|---|---|
| Original (fotos de 3000 × 4000 px) | **62.3 %** (CER 10.6 %) | 10.3 % (CER 61.1 %) |
| 120 px | 61.4 % | 6.6 % |
| 80 px | 59.5 % | 5.9 % |
| 60 px | 57.2 % | 5.7 % |
| 40 px | 39.1 % | 0.7 % |
| Tiempo por lectura | 2.5 ms | 19.3 ms |

**Revisión manual de 40 errores al azar:**
| | Casos |
|---|---|
| Error de la etiqueta de CARID; el OCR leyó bien (p. ej. placa «T3F-559», etiqueta «T33559») | ~6 (15 %) |
| Dudosos: placa ilegible, o etiqueta y OCR ambos mal | ~9 |
| Error real del OCR | ~25 |

Descontando los errores de etiqueta, la exactitud real de fast-plate-ocr en CARID ronda el **68 %**.

**Conclusiones:**
- **El 86.7 % medido con 30 placas era optimista.** Con 958 placas de un tercero, el OCR especializado acierta entre 62 % y 68 %. Sigue siendo **6 veces más que EasyOCR** (10 %), y la ventaja se mantiene en todos los tamaños.
- **Las fotos de CARID son más difíciles:** muchas son de noche, movidas o con la placa sucia.
- **Error dominante: «T» leída como «Y» (54 casos).** La T de las placas peruanas tiene adornos en la parte superior. Otros errores frecuentes son 0↔O, 5↔S y B↔D.
- **Hacia dónde ir:** ajustar fast-plate-ocr con placas peruanas (pendiente M6). CARID sirve para ese ajuste si se divide por placa, para no evaluar con placas vistas en el ajuste.

## 3. Reentrenamiento del detector (YOLOv8n v2)
**Datos:** la división sin fugas anterior (train 1 968, valid 137, **test 98 sin cambios**) más las fotos nuevas de peruvian_plates:
- 699 a train y 39 a valid;
- **20 grupos como segunda prueba** (`test_nuevas`), con autos lejanos, motos, mototaxis y camiones.

**Etiquetas:** el detector anterior encontró 907 placas en las fotos nuevas; solo 24 (2.6 %) no tenían recuadro en el dataset.

**Receta:** la misma del modelo anterior (YOLOv8n desde COCO, 100 épocas, 640 px, semilla 42, RTX 5070). El mejor modelo fue el de la época 97.

| Prueba | Modelo | Precisión | Exhaustividad | mAP@50 | mAP@50-95 | ms/img |
|---|---|---|---|---|---|---|
| Original sin fugas (97 imágenes) | v1 (actual del paper) | 95.6 % | 91.3 % | 96.5 % | 75.0 % | 2.4 |
| | **v2** | 95.1 % | **93.8 %** | **97.1 %** | **75.2 %** | 1.9 |
| Fotos nuevas (20) | v1 | 99.2 % | 83.3 % | 86.9 % | 60.6 % | 3.4 |
| | **v2** | 99.7 % | **91.7 %** | **91.5 %** | **65.8 %** | 2.1 |

**Decisión:** v2 mejora en las dos pruebas, sobre todo en exhaustividad (encuentra más placas) y en las fotos difíciles. Pasa a ser el detector del sistema (`PESOS_DETECTOR` en `settings.py`). La demo y las evaluaciones históricas siguen fijadas a v1 para que los resultados de las pruebas 04 y 07 y del paper sean reproducibles.

**Contrapartida con video real:**
| Video | v1 | v2 |
|---|---|---|
| Taxi (número de placa pintado en la puerta) | ACO-484, 3 de 3 | No lo detecta (ni con confianza 0.05) |
| Combi | Emite «ELW-150», una placa falsa | No emite nada (correcto) |

v2 aprendió que un número pintado en la carrocería no es una placa, porque en los datos nuevos solo se marcan placas con marco. En los taxis peruanos ese número coincide con la placa, así que leerlo era un acierto «accidental» de v1. Leer placas pintadas requiere datos propios etiquetados (pendiente M9). Volver a v1 es cambiar una línea en `settings.py`.

**Prueba de la segunda división:** solo 20 imágenes, así que la diferencia en `test_nuevas` es indicativa y no concluyente.
