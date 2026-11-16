# Guion de exposición — FotoPapeleta Inteligente

**Duración:** 13–15 min + preguntas · **Reparto sugerido** según el responsable de cada módulo (README); ajústenlo.
**Antes de empezar:** servidor corriendo (`python manage.py runserver 8000`), sesión abierta en el panel, la pestaña del portal lista, tema claro, y en el panel las guías ya vistas (para que no aparezcan durante la demo).

> Las frases entre comillas son para decir en voz alta. Lo que está en *cursiva* es lo que se muestra o se hace.

---

## 1. Problema (Tonny · 1 min)

"En Lima las papeletas por exceso de velocidad dependen de un policía en el punto exacto o de un radar fijo. Un radar mide un instante: basta frenar frente a él. Y cuando una cámara se equivoca leyendo la placa, la multa le llega a otra persona."

"Nuestra propuesta: usar las cámaras que ya existen —incluso celulares— para **leer placas con visión por computadora**, **unir esas lecturas con algoritmos de búsqueda en un grafo** para medir la velocidad promedio entre dos puntos, y que **ninguna papeleta salga sin que una persona la revise**."

## 2. Qué construimos (Tonny · 1 min)

*Mostrar la Fig. 4 del paper (arquitectura) o la diapositiva de capas.*

"El sistema tiene seis capas:
1. **Captura**: cámaras o celulares.
2. **Percepción**: un modelo detecta la placa y otro la lee.
3. **Datos y grafo**: la red de cámaras es un grafo.
4. **Análisis**: BFS, DFS y A* buscan la evidencia y calculan la velocidad.
5. **Validación humana**: un validador aprueba o rechaza.
6. **Consulta**: un portal donde el ciudadano ve su papeleta y su evidencia."

"Seguimos la metodología **CRISP-DM**: comprensión del negocio, de los datos, preparación, modelado, evaluación y despliegue. Todo está implementado y probado: **120 pruebas automáticas** pasan."

## 3. Los datos (Yazid · 1 min)

"Para entrenar usamos un conjunto público de **placas peruanas** (Peru License Plate, Roboflow)."

"Antes de entrenar hicimos algo que cambió el resultado: **revisamos si había fotos repetidas entre entrenamiento y prueba**. Con una huella de imagen (dHash) encontramos que la división original repetía fotos: 4 de las 53 de prueba ya estaban en entrenamiento. Eso infla la métrica, porque el modelo 'ya vio' el examen."

"Por eso armamos nuestra propia división: agrupamos las fotos casi iguales y pusimos **cada grupo en un solo conjunto** (75 % entrenamiento, 15 % validación, 10 % prueba). Otro dataset, NumberPlates, lo descartamos porque resultó ser una copia del primero."

## 4. Machine learning 1 — Detector de placas YOLOv8 (Yazid · 2 min)

"El primer modelo responde: **¿dónde está la placa en la imagen?**"

"Usamos **YOLOv8n** ('You Only Look Once', versión nano). Es una red neuronal convolucional:
- Las **capas convolucionales** aprenden filtros: primero bordes, luego formas, luego objetos completos.
- 'Mira una sola vez': divide la imagen en una cuadrícula y, en una sola pasada, cada zona predice si hay una placa, **el recuadro** (x, y, ancho, alto) y **qué tan seguro** está.
- Luego se eliminan los recuadros repetidos y queda uno por placa."

"No empezamos de cero: usamos **aprendizaje por transferencia**. El modelo ya venía entrenado con COCO, un dataset de objetos comunes, y lo reentrenamos para placas peruanas: **100 épocas**, imágenes de 640 px, en una RTX 5070, en 20 minutos. El mejor modelo fue el de la época 82."

*Mostrar la Tabla III o la curva de entrenamiento.*

"En la prueba —97 imágenes que el modelo nunca vio, con 166 placas—:
- **Precisión 95.6 %**: de lo que marca como placa, casi todo lo es.
- **Exhaustividad 91.3 %**: encuentra 9 de cada 10 placas.
- **mAP@50 de 96.5 %**: la métrica estándar de detección.
- **1.9 ms por imagen**."

"**La detección funciona bien.**"

## 5. Machine learning 2 — Lectura de la placa (Rodrigo · 2 min)

"El segundo modelo responde: **¿qué dice la placa?** Empezamos con **EasyOCR**, un lector de texto genérico. Por dentro tiene tres piezas:
- una **red convolucional** que extrae rasgos del recorte de la placa;
- una **red recurrente (LSTM)** que lee esos rasgos de izquierda a derecha, como una secuencia;
- y **CTC**, una técnica que convierte esa secuencia en texto sin necesitar saber dónde empieza cada letra."

"Encima le pusimos nuestras propias capas:
1. **Preprocesado**: escala de grises, agrandar la placa y mejorar el contraste (CLAHE).
2. **Reglas del formato peruano**: posición 1 y 3 son letras y las últimas tres son dígitos. Si el OCR lee una 'O' donde va un número, se corrige a '0'.
3. **Votación entre cuadros**: un auto aparece en muchos cuadros de video; leemos la placa en cada uno y **votamos carácter por carácter**, pesando cada lectura por su confianza."

"Para saber qué cuadros son del mismo auto hacemos **seguimiento**: si el recuadro de un cuadro se superpone al del siguiente (IoU de 0.3 o más), es la misma placa."

*Mostrar la Tabla IV.*

"Resultados:
- En placas sintéticas de calidad media, la votación sube el acierto de **46 % a 71 %**.
- En **fotos reales**, el OCR genérico acertaba solo el **23 %**: era nuestro cuello de botella."

"Lo resolvimos cambiando a un **OCR entrenado específicamente con placas** (fast-plate-ocr, una red que lee los 6 caracteres de la placa a la vez). En las **mismas 30 placas reales** subió de **23 % a 87 %**. Luego lo medimos con **958 placas de otro dataset (CARID)**: **62 %, frente a 10 % de EasyOCR**, seis veces más. El error más común es confundir la «T» peruana con una «Y»; el siguiente paso es ajustarlo con placas peruanas."

"Aun así, la validación humana se mantiene: ningún OCR es perfecto."

## 6. El grafo y los algoritmos de búsqueda (Carlos · 2.5 min)

*Abrir el panel → Laboratorio del grafo.*

"Cada **cámara es un nodo** y cada **calle entre dos cámaras es una arista**, con su distancia en km, su tiempo típico y su límite de velocidad."

"Usamos tres algoritmos:
- **BFS** (búsqueda en anchura): '¿qué cámaras están a uno o dos saltos?'. Cuando una cámara ve una placa, busca la misma placa solo en las cámaras vecinas. *Ejecutar BFS desde AV-01 con k = 2.*
- **DFS** (búsqueda en profundidad, acotada): enumera las rutas posibles entre dos cámaras.
- **A\***: encuentra la **ruta más corta**. Usa una heurística, la distancia en línea recta, que nunca sobreestima; por eso la respuesta es exacta. *Ejecutar A\* de AV-01 a PN-04 con y sin heurística y mostrar la tabla de comparación.* El costo es el mismo, pero con la heurística **explora menos nodos**. En una red de 400 cámaras exploró **58.5 % menos**. Comparamos contra NetworkX: el costo fue correcto en **300 de 300** consultas."

"**La velocidad por tramo**, que es lo que multa:

  velocidad = distancia mínima ÷ (tiempo observado + 2 × error de reloj)

- Usamos la **distancia mínima** (A\*) y le **sumamos** al tiempo un margen por el reloj de cada cámara. Así calculamos la velocidad **más baja** que el auto pudo tener: si aun así supera el límite más 5 km/h de tolerancia, hay infracción. Todo a favor del conductor.
- Ejemplo: AV-01 → AV-08 son 3.0 km en 120 s. Medida: 90 km/h. Conservadora: **87.1 km/h**. En zona de 60: **exceso de 27.1**."

"**Placa clonada**: si la misma placa aparece en dos cámaras en un tiempo que exigiría **más de 200 km/h**, no puede ser el mismo auto. No se multa: se genera una **alerta**. *Mostrar el cálculo de velocidad por tramo con 1 minuto entre AV-01 y AV-12: 408 km/h, alerta.*"

## 7. Validación humana y sistema web (Rodrigo · 1 min)

"Todo esto corre en una aplicación **Django** con base de datos.
- El programa que lee las cámaras envía cada placa a una **API**.
- El backend decide con el grafo.
- Cada infracción guarda su **análisis**: ruta, tiempos, velocidad y versión del grafo. Así cualquier decisión se puede auditar.
- Hay **roles**: worker, validador y administrador."

## 8. Demostración en vivo (Juan Diego conduce · 3 min)

1. **Resumen**: "Así se ve la operación: indicadores, infracciones por hora, la cola de validación y el estado de las cámaras."
2. **Subir evidencia** (*o usar una infracción que ya esté en la cola*): subir la foto de un auto en AV-01 a las 08:42 y la misma en AV-08 a las 08:44. "El detector encuentra la placa, el OCR la lee y el sistema calcula 87.1 km/h: crea la infracción."
3. **Validación**:
   - "El validador ve las dos cámaras, la lectura del OCR con su confianza y el análisis del grafo."
   - *Si el OCR se equivocó*: "Corrijo la placa."
   - *Presionar **A***: "Aprobada: se emite la papeleta FP-2026-…"
4. **Portal ciudadano**: consultar la placa. "El ciudadano ve su papeleta, las fotos, la trayectoria en el mapa y la velocidad. Si no está de acuerdo, **solicita una revisión**." *Mostrar el formulario.*
5. **Auditoría**: en el panel, abrir el detalle de la infracción. "Queda registrado quién hizo qué y cuándo, con qué modelos y qué versión del grafo."

## 9. Resultados, errores encontrados y limitaciones (Juan Diego · 1.5 min)

"En resumen:
- Detector: mAP@50 de 97.1 % (v2, con 281 fotos nuevas auditadas). Lectura de placas: 62 % en 958 placas, seis veces más que el OCR genérico.
- Grafo: A\* exacto y 58.5 % más eficiente con la heurística.
- Sistema completo: 3 de 3 decisiones correctas en la demo, a 24–32 ms por cuadro.
- 120 pruebas automáticas."

"Las pruebas nos permitieron **encontrar y corregir errores de lógica**:
1. Un auto a **94.7 km/h** se trataba como placa clonada en vez de infracción. El filtro estaba mal planteado; lo cambiamos por el criterio de 200 km/h.
2. Un auto que pasaba por **tres cámaras** recibía tres multas, porque se contaba dos veces el mismo recorrido. Ahora se evalúan tramos consecutivos.
3. **Subir la misma foto dos veces** duplicaba la infracción."

"Limitaciones:
- Un solo dataset público; la prueba tiene 97 imágenes.
- La lectura se probó con 30 placas reales; hay que ampliar la prueba.
- Usamos video simulado.
- Las coordenadas de las cámaras son esquemáticas.
- Solo detectamos exceso de velocidad."

## 10. Cierre (Tonny · 30 s)

"FotoPapeleta une **visión por computadora** para leer placas, **algoritmos de búsqueda en grafos** para medir la velocidad entre cámaras, y **validación humana** para que nadie reciba una papeleta por un error de la máquina. El siguiente paso es entrenar el OCR con placas peruanas y probar con video real de celulares."

---

## Preguntas probables y respuestas cortas

| Pregunta | Respuesta |
|---|---|
| ¿Por qué YOLO y no otro detector? | Es de una sola pasada: rápido (1.9 ms) para video en tiempo real. La versión nano corre incluso sin GPU potente. |
| ¿Qué es mAP@50? | El promedio de la precisión en todos los niveles de exhaustividad, contando como acierto un recuadro que se superpone al real en 50 % o más. |
| ¿Por qué cambiaron de OCR? | EasyOCR es genérico: 23 % en 30 placas reales y 10 % en 958 placas de CARID. fast-plate-ocr está entrenado con placas: 87 % en las 30 y 62 % en las 958 (≈68 % descontando errores de etiqueta), más reglas de formato, votación entre cuadros y validación humana. |
| ¿Por qué la foto se lee peor que el video? | Una foto es una sola lectura. En video el auto se acerca, hay cuadros con la placa más grande y se vota entre todos: 46 % → 71 % en sintéticas. |
| ¿Por qué A\* y no solo Dijkstra? | Dan el mismo costo, pero A\* con heurística explora menos nodos: 58.5 % menos con 400 cámaras. La heurística (línea recta) nunca sobreestima, por eso es exacta. |
| ¿Y si el reloj de una cámara está mal? | Sumamos 2 × ε al tiempo (ε = 2 s): la velocidad que usamos es la mínima posible. |
| ¿Cómo saben que no hay fuga de datos? | Auditamos duplicados con dHash y dividimos por grupos; la división original sí tenía fugas. |
| ¿Qué pasa si leen mal la placa y multan a otro? | No se emite nada automáticamente. Si dos lecturas difieren en un carácter, la coincidencia queda «a verificar», el validador corrige la placa y el ciudadano puede pedir revisión. |
| ¿Placa clonada? | Si la misma placa aparece en dos cámaras y haría falta ir a más de 200 km/h, se genera una alerta, no una multa. |
| ¿Se puede usar con celulares? | Sí. Un celular con la app IP Webcam es una cámara más: un nodo del grafo. |
| ¿Los datos del panel son reales? | Las cifras de los modelos sí. Las infracciones del panel vienen de la demo con fotos públicas y de vehículos simulados que pasan por el mismo flujo de decisión; el panel lo indica con un aviso de «modo demostración». |
