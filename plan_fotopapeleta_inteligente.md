# FotoPapeleta Inteligente — Documento maestro del proyecto

**Paper:** *Hacia una Fiscalización Vial Inteligente: Detección de Infracciones y Seguimiento Vehicular mediante Algoritmos de Búsqueda*
**Curso / entrega:** APF2 — Paper científico (rúbrica sobre 20 puntos)
**Universidad:** Universidad Tecnológica del Perú (UTP)
**Metodología:** CRISP-DM

**Equipo (5 integrantes):**

| Integrante | Rol propuesto |
|---|---|
| Tonny Gabriel Hinostroza Palaco | Metodología, arquitectura e integración (líder) |
| Carlos Andrés Mayta Orozco | Algoritmo de grafos (BFS/DFS/A*) |
| Yazid Juana Acosta Ticona | Detección (YOLO) y dataset |
| Rodrigo Yoel Sequeiros Borda | OCR y pipeline / backend |
| Juan Diego Chumpitaz Quispe | Evaluación, métricas y formato del paper |

> Este documento es la referencia única del equipo: de qué trata el proyecto, cómo se implementa, cómo se prueba y cómo se defiende ante el docente.
> El detalle técnico (capas, componentes, modelo de datos, API, stack) está en **`arquitectura_fotopapeleta_inteligente.md`**.

---

## 1. La idea en una frase

Un sistema que **detecta automáticamente infracciones** con visión por computadora, **lee la placa** del vehículo y —cuando una sola cámara no basta— **reconstruye la trayectoria del vehículo a través de una red de cámaras modelada como grafo**, recorrida con **BFS, DFS y A\***, para recuperar evidencia adicional. Siempre con **validación humana** antes de emitir la foto-papeleta.

---

## 2. Objetivos

**Objetivo general.** Diseñar un sistema de fiscalización vial inteligente que mejore la automatización y la trazabilidad del proceso de generación de foto-papeletas.

**Objetivos específicos.**
1. Desarrollar un mecanismo para **detectar y registrar infracciones** con: placa, tipo de infracción, fecha, hora, ubicación y evidencia visual.
2. Aplicar algoritmos de búsqueda **BFS, DFS y A\*** para **localizar evidencia relacionada** y **analizar posibles trayectorias** vehiculares dentro de la red.

---

## 3. Alcance realista para APF2 (decisión clave)

Un proyecto universitario no despliega cámaras reales ni entrena un detector desde cero. El trabajo se separa en tres niveles para cumplir la rúbrica sin sobreprometer:

- **Núcleo demostrable y medible (lo que se evalúa como “algoritmo”):** el módulo **grafo + búsqueda (BFS/DFS/A\*)** completamente funcional sobre una red de cámaras de Lima construida por el equipo. Es 100 % implementable, da resultados verificables y es exactamente el objetivo específico #2.
- **Pipeline de percepción demostrado con celulares y muestras:** detección con **YOLO preentrenado** + **modelo de placas** + **OCR** sobre la cámara de **celulares** (app IP Webcam) y sobre clips grabados, para probar que la entrada del grafo `(placa, cámara, hora)` se genera de forma realista. Cada celular representa una cámara (un nodo del grafo). No se entrena un modelo grande; se demuestra el flujo.
- **Capa de despliegue / consulta:** aplicación web en **Django**, construida a partir del prototipo HTML básico actual (portal ciudadano + panel administrativo + pantalla de validación).

---

## 4. Conceptos base

### 4.1 La red de cámaras como grafo

Un **grafo** es un conjunto de puntos (nodos) unidos por líneas (aristas).

- **Nodos = cámaras.** Cada cámara en una intersección es un nodo (AV-01 en Av. Javier Prado, AV-08 en Av. Arequipa, AV-12 en Av. Brasil, etc.).
- **Aristas = tramos de vía.** Si un vehículo puede ir conduciendo directamente de una cámara a otra, hay una arista entre ellas.
- **Peso de la arista = costo del tramo.** Se guardan **ambos**: distancia (km) y tiempo de viaje (min). La velocidad por tramo usa siempre km.
- **Grafo dirigido.** Las vías de doble sentido generan dos arcos y las de un solo sentido, uno. Así se modelan calles reales y la infracción “sentido contrario”.
- **Coordenadas.** Cada cámara guarda latitud y longitud; son necesarias para la heurística de A\* y para el mapa del panel.

Representación interna (lista de adyacencia, ya expandida en ambos sentidos), ejemplo:

```json
{
  "AV-01": [["AV-08", {"km": 3.0, "min": 4}], ["AV-02", {"km": 2.1, "min": 3}]],
  "AV-08": [["AV-01", {"km": 3.0, "min": 4}], ["AV-15", {"km": 4.5, "min": 6}], ["AV-12", {"km": 3.8, "min": 5}]],
  "AV-02": [["AV-01", {"km": 2.1, "min": 3}], ["AV-12", {"km": 5.2, "min": 7}]],
  "AV-12": [["AV-08", {"km": 3.8, "min": 5}], ["AV-02", {"km": 5.2, "min": 7}], ["PN-04", {"km": 6.0, "min": 8}]],
  "AV-15": [["AV-08", {"km": 4.5, "min": 6}]],
  "PN-04": [["AV-12", {"km": 6.0, "min": 8}]]
}
```

Esquema visual:

```
   AV-01 ──4 min / 3.0 km── AV-08 ──6 min / 4.5 km── AV-15
     │                        │
  3 min / 2.1 km          5 min / 3.8 km
     │                        │
   AV-02 ──7 min / 5.2 km── AV-12 ──8 min / 6.0 km── PN-04
```

### 4.2 Qué hace cada algoritmo

Escenario: una cámara detectó la placa **ABC-123** en **AV-01 a las 08:42**. Pregunta del sistema: *“¿por dónde más pasó el vehículo, para recuperar evidencia adicional?”*.

- **BFS (anchura):** cámaras alcanzables en pocos saltos → **vecindario** donde conviene buscar la siguiente evidencia.
- **DFS (profundidad):** enumera **rutas completas** posibles desde el origen hacia un destino.
- **A\* (A-estrella):** **ruta más probable/eficiente** usando los pesos y una heurística. Reconstruye por qué cámaras intermedias **debió** pasar el vehículo.
  - La heurística debe estar **en las mismas unidades que el peso** y no sobreestimar: con peso en km se usa la **distancia en línea recta (Haversine)**; con peso en minutos, esa distancia dividida entre la velocidad máxima de la red. Sin coordenadas, `h = 0` y A\* equivale a Dijkstra.

**Idea central:** el grafo **no detecta** la infracción; **vincula, rastrea y recupera** evidencia entre cámaras.

---

## 5. Estrategia de pruebas (lo que el docente preguntará)

Las pruebas van en **dos niveles claramente separados**. Saber separarlos es parte de la defensa.

### 5.1 Nivel percepción (clips / imágenes) → YOLO + OCR

Se prueban viendo la escena. Entrada: imagen, clip o transmisión de un celular. Métricas: precisión/exhaustividad de detección y acierto de lectura de placa.

**Importante:** el YOLO preentrenado (COCO) detecta autos pero **no tiene la clase “placa”**. Se usa un **modelo de placas** aparte (pesos públicos de Roboflow/Hugging Face, ajustados con unas 200–300 fotos de placas peruanas). EasyOCR lee solo el recorte de la placa, se valida el formato con `^[A-Z0-9]{3}-?\d{3}$` y se elige la lectura más repetida en 5–10 frames del mismo vehículo (votación).

| Infracción | Cómo se prueba |
|---|---|
| Semáforo en rojo | Clip: estado del semáforo + vehículo cruzando |
| Invasión de cruce peatonal | Imagen/clip con zona del cruce |
| Uso de celular | Imagen/clip (objeto en mano del conductor) |
| Giro prohibido | Clip (maniobra) |
| Sentido contrario | Clip (dirección de avance) |
| No respetar señales | Imagen/clip |

En todas, el grafo entra **después**: detectada la infracción en la cámara X, BFS/DFS/A\* buscan en qué otras cámaras reapareció la placa para **recuperar evidencia de respaldo**.

### 5.2 Nivel grafo (eventos) → BFS / DFS / A\*

Entrada: un **evento** `(placa, cámara, hora)`. Métricas: nodos explorados, costo de ruta, evidencia recuperada, tiempo de ejecución.

Dos salvaguardas al vincular capturas entre cámaras:
- **Filtro de plausibilidad:** una captura en otra cámara solo se acepta si recorrer la distancia mínima (A\* en km) en el tiempo observado no exige más de 200 km/h. Lo que lo supera se marca como alerta (posible placa clonada o error de lectura).
- **Coincidencia difusa de placa:** si el OCR confunde un carácter (`O/0`, `B/8`, `I/1`, `S/5`), la coincidencia se marca **“a verificar”** y nunca se emite sin revisión humana.

Las implementaciones propias de BFS, DFS y A\* se comparan contra **NetworkX** en los tests: si los resultados coinciden, queda demostrado que son correctas.

### 5.3 Caso especial — VELOCIDAD (dos formas)

**Forma 1 — por clip (una sola cámara).** YOLO sigue el vehículo cuadro a cuadro y se estima la velocidad con distancia en pantalla y FPS. Requiere **calibrar la cámara** (metros reales por píxel). Sirve para demostrar el pipeline, pero es sensible a error.

**Forma 2 — por grafo (velocidad promedio por tramo).** Es el método de los peajes de “velocidad promedio por tramo” (*section speed*). Si la misma placa se captura en dos cámaras:

```
velocidad = distancia_entre_cámaras / tiempo_transcurrido
```

La distancia es el **peso de la arista** del grafo. 100 % reproducible, sin calibrar nada.

Ejemplo:

```
ABC-123 en AV-01 → 08:42:00
ABC-123 en AV-08 → 08:44:00     (Δt = 2 min = 0.0333 h)
Peso de la arista AV-01–AV-08 = 3 km

velocidad medida       = 3 km / (120 s / 3600) = 90.0 km/h
velocidad conservadora = 3 km / (124 s / 3600) = 87.1 km/h   (+2 s de error de reloj por cámara)
Límite de la vía = 60 km/h, tolerancia = 5 km/h
Exceso = 87.1 − 60 = +27.1 km/h > 5  →  INFRACCIÓN
```

**Detalle que impresiona (doble garantía a favor del conductor):**
1. Se usa **A\*** para confirmar que 3 km es la **ruta más corta** entre ambas cámaras: cualquier otro camino daría una velocidad mayor.
2. Al tiempo medido se le **suma el posible error de reloj** de ambas cámaras: se usa el tiempo más largo posible.

Con distancia mínima y tiempo máximo, 87.1 km/h es la velocidad promedio **más baja** que pudo tener el vehículo. Si aun así supera el límite más la tolerancia, la infracción queda demostrada sin ambigüedad. Aquí el grafo deja de ser decorativo y se vuelve parte de la prueba.

**Por qué importa el reloj:** con Δt = 2 min, un error de solo 10 s cambia el resultado en 7–8 km/h. Los celulares sincronizan la hora por red; las cámaras reales usarían NTP.

### 5.4 Respuesta corta para el docente

> “Las pruebas van en dos niveles. El módulo de percepción se evalúa con **clips/imágenes de muestra y celulares usados como cámaras**, midiendo precisión de detección y acierto de lectura de placa (YOLO + modelo de placas + OCR). El módulo de grafo se evalúa con **eventos** `(placa, cámara, hora)`, midiendo nodos explorados, costo de ruta y evidencia recuperada con BFS, DFS y A\*, y validando nuestras implementaciones contra NetworkX. El caso de **velocidad** se prueba por **velocidad promedio por tramo**: la distancia mínima entre dos cámaras (garantizada por A\*) dividida entre el tiempo transcurrido más el margen de error de reloj, con una tolerancia. Así obtenemos la velocidad más baja posible, siempre a favor del conductor.”

---

## 6. El algoritmo (núcleo del APF2 — 5 pts)

Tres módulos encadenados.

**Módulo A — Percepción (worker Python aparte).** Entrada: frame de un celular o clip. YOLO detecta vehículo + tipo de infracción; el modelo de placas recorta la placa; EasyOCR la lee y se vota entre frames. Salida: evento `{placa, tipo, cámara, fecha, hora, confianza}`, enviado a la API de Django.

**Módulo B — Grafo de cámaras.** Nodos = cámaras (con coordenadas); aristas dirigidas = tramos de vía; pesos = km y min. Se guarda en la BD de Django (editable desde el admin) y se exporta a JSON para el notebook (sección 4.1).

**Módulo C — Búsqueda de evidencia / trayectoria (paquete Python puro).** Dado un evento en una cámara origen: BFS (vecindario) + filtro temporal, DFS acotado (rutas candidatas), A\* (ruta más probable + reconstrucción de trayectoria) y velocidad por tramo. No depende de Django: lo usan igual el notebook y la web.

### 6.1 Pseudocódigo de referencia

```
# BFS — vecindario alcanzable en <= k saltos
funcion BFS(grafo, origen, k):
    visitados = {origen: 0}
    cola = [origen]
    mientras cola no vacía:
        actual = cola.pop_front()
        si visitados[actual] == k: continuar
        para cada (vecino, peso) en grafo[actual]:
            si vecino no en visitados:
                visitados[vecino] = visitados[actual] + 1
                cola.push_back(vecino)
    retornar visitados      # incluye el origen (0) + cámaras candidatas con nº de saltos

# DFS — enumerar rutas origen -> destino (acotado para no explotar)
funcion DFS(grafo, actual, destino, camino, rutas, max_prof, max_rutas):
    camino.append(actual)
    si actual == destino:
        rutas.append(copia(camino))
    sino si len(camino) <= max_prof y len(rutas) < max_rutas:
        para cada (vecino, peso) en grafo[actual]:
            si vecino no en camino:
                DFS(grafo, vecino, destino, camino, rutas, max_prof, max_rutas)
    camino.pop()
    retornar rutas

# A* — ruta de menor costo; h en las mismas unidades que el peso (Haversine si es km)
funcion A_estrella(grafo, origen, destino, h):
    abierto = cola_prioridad()           # ordena por f = g + h
    g = {origen: 0}
    abierto.push(origen, h(origen, destino))
    padre = {}
    cerrados = {}
    nodos_explorados = 0
    mientras abierto no vacía:
        actual = abierto.pop_min()
        si actual en cerrados: continuar  # entrada obsoleta de la cola
        cerrados.add(actual)
        nodos_explorados += 1
        si actual == destino:
            retornar reconstruir(padre, destino), g[destino], nodos_explorados
        para cada (vecino, peso) en grafo[actual]:
            g_tentativo = g[actual] + peso
            si vecino no en g o g_tentativo < g[vecino]:
                g[vecino] = g_tentativo
                padre[vecino] = actual
                abierto.push(vecino, g_tentativo + h(vecino, destino))
    retornar None
```

### 6.2 Cálculo de velocidad por tramo

```
funcion velocidad_por_tramo(grafo, cam_a, t_a, cam_b, t_b, limite,
                            error_reloj_s = 2, tolerancia = 5):
    ruta, dist_km, _ = A_estrella(grafo, cam_a, cam_b, h_haversine)   # ruta mínima
    segundos = (t_b - t_a) en segundos
    si segundos <= 0: retornar None
    v_conservadora = dist_km / ((segundos + 2 * error_reloj_s) / 3600)   # a favor del conductor
    exceso = v_conservadora - limite
    retornar v_conservadora, exceso, (exceso > tolerancia)
```

La implementación en Python de todas estas funciones está en `arquitectura_fotopapeleta_inteligente.md`, secciones 5.3–5.6.

### 6.3 Qué presentar como “avance del algoritmo”

Un script/notebook que, dado un evento, corre los tres algoritmos y el cálculo de velocidad, e imprime las métricas en una tabla reproducible. Incluir:
- Comparación de A\* con `h = 0` (Dijkstra) frente a Haversine: mismo costo, menos nodos explorados.
- Tests que comparan los resultados propios con NetworkX.
- Una pantalla “laboratorio del grafo” en la web para ejecutar los algoritmos en vivo durante la exposición.

---

## 7. Métricas a reportar (para la tabla de resultados)

| Módulo | Métrica | Qué mide |
|---|---|---|
| Percepción | Precisión / exhaustividad / mAP | Calidad de detección |
| Percepción | CER (tasa error por carácter) / placa completa, con y sin votación | Calidad del OCR |
| Grafo | Nodos explorados (incluye A\* con h=0 vs Haversine) | Eficiencia de búsqueda (BFS vs DFS vs A\*) |
| Grafo | Costo de ruta (km / min) | Calidad de la trayectoria |
| Grafo | Evidencia recuperada | Nº de cámaras con captura de la misma placa |
| Grafo | Tiempo de ejecución | Rendimiento |
| Velocidad | km/h medida, conservadora y exceso | Resultado de la infracción |

Comparar con los resultados reportados en la literatura de referencia del paper ([4], [5]).

---

## 8. Mapeo CRISP-DM (alimenta “Metodología”, 5 pts)

| Fase | Actividades | Entregable verificable |
|---|---|---|
| 1. Comprensión del negocio | Tipos de infracción, restricciones legales, criterios de éxito | Objetivos + criterios (cobertura, trazabilidad, tiempo) |
| 2. Comprensión de los datos | Datasets públicos; topología de la red de cámaras | Inventario de datos + grafo preliminar |
| 3. Preparación de los datos | Preprocesar muestras; construir grafo ponderado | Grafo ponderado (JSON/adyacencia) + muestras |
| 4. Modelado | YOLO + OCR sobre muestras; implementar BFS/DFS/A\* | Notebook/script del algoritmo |
| 5. Evaluación | Medir detección, OCR y búsqueda | Tabla de resultados vs [4], [5] |
| 6. Despliegue | Registro trazable + validación humana + captura con celulares | Worker de percepción + aplicación Django (demo de despliegue) |

---

## 9. Arquitectura (conceptual — 6 capas)

1. **Captura** — celulares como cámaras (app IP Webcam) y clips grabados → frames.
2. **Percepción** — worker Python: YOLO (detección) + modelo de placas + EasyOCR con votación.
3. **Datos y grafo** — Django + BD (SQLite/PostgreSQL): infracciones, evidencias y grafo de cámaras.
4. **Análisis** — paquete Python puro: BFS/DFS/A\* (evidencia y trayectorias) + velocidad por tramo.
5. **Validación y emisión** — cola de validación humana en Django → foto-papeleta.
6. **Consulta ciudadana** — portal y panel en plantillas Django (Tailwind CSS + HTMX + Alpine.js + Lucide + Leaflet). Diseño en pencil.dev según `diseno_prototipo_pencil.md`.

Flujo de datos: `Captura → Percepción → (evento) → Grafo/Análisis → Validación → Emisión → Consulta`.

**Stack decidido:** todo en **Python**. Backend y web con **Django + Django REST Framework** en lugar de FastAPI, porque el proyecto necesita portal, panel, login con roles y administración, que Django trae incluidos. El ML corre en un proceso aparte, así que la velocidad de FastAPI no aporta. La justificación completa está en `arquitectura_fotopapeleta_inteligente.md`, sección 9.

---

## 10. Diseño y funcionalidades

**Diagramas para el paper / exposición:** ciclo CRISP-DM (Fig. 2), arquitectura por capas, grafo de cámaras, flujo de datos, casos de uso.

**Prototipo web (estado actual: HTML básico, por mejorar):** se migrará a plantillas de Django reutilizando el HTML existente como base. Pantallas objetivo:
- **Portal ciudadano:** consulta por placa, detalle con evidencia (placas de terceros difuminadas), solicitar revisión.
- **Panel administrativo:** resumen/KPIs (Chart.js), cámaras con mapa del grafo (Leaflet), infracciones con filtros, validación en 3 columnas, reportes.
- **Laboratorio del grafo:** elegir origen/destino y ejecutar BFS/DFS/A\* y velocidad en vivo (para la exposición).
- **Captura:** página para usar la cámara del celular desde el navegador (opcional).
- **Admin de Django:** gestión de cámaras, tramos y usuarios.

**Funcionalidades ↔ objetivos:**
- Detección + registro de infracción con placa/tipo/fecha/hora/ubicación/evidencia → **objetivo 1**.
- Búsqueda BFS/DFS/A\* de evidencia y trayectorias → **objetivo 2**.

---

## 11. Cobertura de la rúbrica (20 pts)

| Criterio (máx) | Cómo se cubre |
|---|---|
| Puntualidad (2) | Entrega anticipada |
| Exposición (3) | Diagramas + demo del prototipo + guion de defensa (sección 5.4) |
| Conocimiento del tema (3) | Dominio de BFS/DFS/A\*, YOLO/OCR y velocidad por tramo |
| Envío del trabajo (2) | Checklist de formato IEEE |
| Metodología (5) | Tabla CRISP-DM (sección 8) + redacción de metodología |
| Avance del algoritmo (5) | Notebook del Módulo C con métricas reproducibles (secciones 6 y 7) |

---

## 12. Cronograma y reparto (hacia APF2 — ajustar a fecha real)

| Semana | Foco | Responsable(s) |
|---|---|---|
| 1 | Cerrar alcance + grafo preliminar con coordenadas + proyecto Django base | Tonny / Carlos |
| 2 | Paquete `grafo/` + tests vs NetworkX; fotos de placas y modelo de placas | Carlos / Yazid |
| 3 | Worker YOLO + placas + OCR (clips y celulares) → API Django; migrar prototipo HTML | Rodrigo / Yazid / Tonny |
| 4 | Evaluación + tabla de resultados; demo con dos celulares | Juan Diego / Todos |
| 5 | Integrar en el paper + ensayar exposición (con video de respaldo) | Todos |

---

## 13. Caso de ejemplo integrado (para la demo)

```
Evento detectado:
  placa   = ABC-123
  tipo    = exceso de velocidad
  cámara  = AV-01
  hora    = 08:42:00

Reaparición:
  cámara  = AV-08
  hora    = 08:44:00

Resultados esperados del algoritmo:
  BFS(origen=AV-01, k=2)  -> {AV-01:0, AV-08:1, AV-02:1, AV-15:2, AV-12:2}
  DFS(AV-01 -> PN-04)     -> [AV-01, AV-08, AV-12, PN-04]  (12.8 km)
                             [AV-01, AV-02, AV-12, PN-04]  (13.3 km)
  A*(AV-01 -> AV-08)      -> ruta mínima = [AV-01, AV-08], costo = 3.0 km
                             nodos explorados = 3 con h=0 (Dijkstra);
                             con Haversine, el valor se obtiene al ejecutar
  velocidad_por_tramo     -> medida 90.0 km/h, conservadora 87.1 km/h,
                             exceso +27.1 km/h > tolerancia 5 → INFRACCIÓN
  evidencia recuperada    -> 2 cámaras con captura confirmada de ABC-123
```

> Los nodos explorados por A\* **no se fijan a mano**: dependen de la heurística y deben salir de la ejecución del notebook.

En la demo en vivo, AV-01 y AV-08 son **dos celulares** colocados en dos puntos con distancia conocida. Las cifras serán distintas (por ejemplo, 150 m en un estacionamiento), pero el flujo completo es el mismo.

---

## 14. Riesgos y decisiones abiertas

**Decisiones ya tomadas:**
- **Lenguaje y stack:** Python en todo el sistema. Django + Django REST Framework para backend y web; worker de percepción aparte con OpenCV, YOLOv8, modelo de placas y EasyOCR; NetworkX como oráculo de pruebas.
- **Peso de las aristas:** ambos (km y min); km obligatorio para la velocidad por tramo.
- **Captura:** celulares como cámaras (app IP Webcam), con videos grabados como respaldo.
- **Prototipo web:** el HTML básico actual se migra a plantillas de Django.

**Pendientes:**
1. **Fecha real de entrega del APF2** (para calzar el cronograma).
2. **Para el “avance del algoritmo”:** ¿grafo + BFS/DFS/A\* como pieza principal (seguro y medible) y YOLO/OCR solo demostrado con celulares y muestras, o también detección evaluada sobre un dataset?
3. **Coordenadas de las cámaras:** quién las levanta (Google Maps / OpenStreetMap).
4. **Lugar de la demo con celulares** y distancia real entre los dos puntos.
5. **¿La aplicación web entra formalmente como entregable de “despliegue”** en el paper o solo como apoyo de exposición?

**Riesgos principales:** OCR poco preciso en placas peruanas (mitigado con modelo de placas, votación y validación humana); Wi-Fi inestable en la exposición (respaldo con videos); PC sin GPU (YOLOv8n a 2–5 fps).

---

## 15. Notas de referencias

El paper continúa la numeración existente (hasta [8]) con las referencias de la sección de metodología ([9]–[22]). Confirmar cuartiles en Scimago (SJR) o JCR para el año de cada publicación y reemplazar cualquier fuente que no sea Q1 ni Q2 (ver apéndice interno de verificación).
