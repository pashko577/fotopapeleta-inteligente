"""Genera la versión «fase 1» del paper: métricas que faltaban y alcance centrado en placas, conteo y BFS/DFS/A*.

- Tabla III: detector v2 y segunda prueba (20 imágenes difíciles).
- Tabla IV: OCR evaluado con CARID (958 placas, tamaño original y 40 px).
- Figura nueva: exactitud del OCR según el ancho de la placa (CARID).
- Referencias [26] peruvian_plates y [27] CARID.
- Correcciones menores (correo duplicado, «se realizaron» → «se realizarán»).

El original nunca se modifica. Uso (desde la raíz del proyecto):
    .venv/Scripts/python.exe docs/paper/actualizar_metricas.py
"""
import copy
import json
import re
import sys
from pathlib import Path

import docx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx.shared import Emu

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "PAPER FOTOPAPELETA (1).docx"
DESTINO = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "PAPER FOTOPAPELETA - fase 1.docx"
FIGURA = Path(__file__).with_name("fig_ocr_ancho.png")
PCT = " %"


# ---------- figura ----------
def generar_figura():
    datos = json.loads((RAIZ / "evaluacion/resultados/ocr_carid.json").read_text("utf8"))["resultados"]
    escalas = ["orig", "120", "80", "60", "40"]
    etiquetas = ["Original", "120", "80", "60", "40"]
    fig, ax = plt.subplots(figsize=(3.4, 2.2), dpi=300)
    for ocr, marca, estilo in (("fast-plate-ocr", "o", "-"), ("easyocr", "s", "--")):
        y = [100 * datos[f"{ocr}@{e}"]["exactitud"] for e in escalas]
        ax.plot(range(5), y, marker=marca, linestyle=estilo, color="black", markersize=4,
                linewidth=1, label="fast-plate-ocr" if ocr != "easyocr" else "EasyOCR")
        for i, v in enumerate(y):
            ax.annotate(f"{v:.1f}", (i, v), textcoords="offset points", xytext=(0, 5),
                        ha="center", fontsize=6)
    ax.axvspan(3.5, 4.5, color="0.85", zorder=0)
    ax.text(4, 78, "rango de las\ncámaras públicas\n(16–40 px)", ha="center", va="top", fontsize=5.5)
    ax.set_xticks(range(5), etiquetas, fontsize=7)
    ax.set_xlim(-0.4, 4.5)
    ax.set_ylim(0, 80)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlabel("Ancho de la placa (px)", fontsize=7)
    ax.set_ylabel("Placas leídas completas (%)", fontsize=7)
    ax.legend(fontsize=6, frameon=False, loc="center left", bbox_to_anchor=(0.02, 0.5))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGURA)
    plt.close(fig)


# ---------- utilidades docx ----------
def reemplazar(parrafo, viejo, nuevo):
    """Reemplaza dentro de un run (conserva el formato). Falla si no lo encuentra."""
    for r in parrafo.runs:
        if viejo in r.text:
            r.text = r.text.replace(viejo, nuevo)
            return
    raise ValueError(f"No se encontró: {viejo!r}")


def poner_texto_celda(celda, texto):
    runs = [r for p in celda.paragraphs for r in p.runs]
    runs[0].text = texto
    for r in runs[1:]:
        r.text = ""


def insertar_fila(tabla, modelo_idx, despues_idx, valores):
    """Copia la fila modelo_idx (formato) y la inserta después de despues_idx."""
    nueva = copy.deepcopy(tabla.rows[modelo_idx]._tr)
    tabla.rows[despues_idx]._tr.addnext(nueva)
    fila = tabla.rows[despues_idx + 1]
    for celda, v in zip(fila.cells, valores):
        poner_texto_celda(celda, v)


def main():
    generar_figura()
    d = docx.Document(ORIGEN)
    P = d.paragraphs

    # Ubicar párrafos por su texto (no por índice) para que el script sea robusto.
    def buscar(inicio):
        return next(p for p in d.paragraphs if p.text.startswith(inicio))

    # --- correcciones menores ---
    for p in d.paragraphs:
        for r in p.runs:
            if "U U22209570" in r.text:
                r.text = r.text.replace("U U22209570", "U22209570")

    # --- renumerar figuras 3..7 -> 4..8 (de mayor a menor) ---
    for n in range(7, 2, -1):
        for p in d.paragraphs:
            for r in p.runs:
                if f"Fig. {n}" in r.text:
                    r.text = r.text.replace(f"Fig. {n}", f"Fig. {n + 1}")

    # --- Tabla III: detector ---
    t3 = d.tables[2]
    poner_texto_celda(t3.rows[1].cells[0], "Validación, v1 (137 imágenes, 237 placas)")
    poner_texto_celda(t3.rows[2].cells[0], "Prueba sin fugas, v1 (97 imágenes, 166 placas)")
    insertar_fila(t3, 2, 2, ["Prueba sin fugas, v2 (97 imágenes, 166 placas)",
                             "95.1" + PCT, "93.8" + PCT, "97.1" + PCT, "75.2" + PCT])
    insertar_fila(t3, 2, 3, ["Segunda prueba, v1 (20 imágenes difíciles)",
                             "99.2" + PCT, "83.3" + PCT, "86.9" + PCT, "60.6" + PCT])
    insertar_fila(t3, 2, 4, ["Segunda prueba, v2 (20 imágenes difíciles)",
                             "99.7" + PCT, "91.7" + PCT, "91.5" + PCT, "65.8" + PCT])

    det = buscar("Detector de placas.")
    det.runs[-1].text += (
        " Posteriormente se incorporaron 281 grupos de fotografías nuevas (849 imágenes) del conjunto"
        " peruvian_plates [26], que pasaron el mismo control de duplicados: de sus 956 fotografías de origen,"
        " cerca de 700 ya estaban en [21]. Con la misma receta, el modelo resultante (v2) mantuvo la precisión"
        " y elevó la exhaustividad a 93.8" + PCT + " y el mAP@50 a 97.1" + PCT + " en la misma prueba sin fugas;"
        " en una segunda prueba de 20 imágenes difíciles —autos lejanos, motocicletas, mototaxis y camiones—"
        " la exhaustividad pasó de 83.3" + PCT + " a 91.7" + PCT + ", resultado indicativo por el tamaño de la"
        " muestra. v2 es el detector del sistema; la prueba de la cadena de percepción conserva v1 para que sus"
        " resultados sean reproducibles."
    )

    # --- Tabla IV: lectura ---
    t4 = d.tables[3]
    ult = len(t4.rows) - 1
    filas = [
        ["CARID, placas reales (958)", "fast-plate-ocr", "1", "62.3" + PCT, "10.6" + PCT],
        ["CARID, placas reales (958)", "EasyOCR", "1", "10.3" + PCT, "61.1" + PCT],
        ["CARID reducidas a 40 px (958)", "fast-plate-ocr", "1", "39.1" + PCT, "18.9" + PCT],
        ["CARID reducidas a 40 px (958)", "EasyOCR", "1", "0.7" + PCT, "87.3" + PCT],
    ]
    for i, f in enumerate(filas):
        insertar_fila(t4, ult, ult + i, f)

    lec = buscar("Lectura de placas.")
    lec.runs[-1].text += (
        " Para una medida independiente y menos optimista se usó CARID [27], cuyas etiquetas por carácter"
        " permitieron reconstruir el texto de 958 placas peruanas distintas, muchas de noche, movidas o sucias:"
        " fast-plate-ocr leyó completas el 62.3" + PCT + " (CER 10.6" + PCT + "), frente al 10.3" + PCT +
        " de EasyOCR, en 2.5 frente a 19.3 ms por placa. En una revisión manual de 40 errores elegidos al azar,"
        " cerca del 15" + PCT + " eran errores de la etiqueta y no del lector, por lo que la exactitud real ronda"
        " el 68" + PCT + "; el error dominante fue la T leída como Y (54 casos), por los adornos superiores de la"
        " T en las placas peruanas, seguido de 0/O, 5/S y B/D. Al reducir cada recorte a 120, 80, 60 y 40 px de"
        " ancho para simular la distancia, fast-plate-ocr se mantuvo por encima de 57" + PCT + " hasta 60 px y"
        " cayó a 39.1" + PCT + " a 40 px (Fig. «OCR»). Esta curva cuantifica el requisito de captura del sistema y"
        " explica por qué las placas de las cámaras públicas de tránsito, de 16 a 40 px, no son legibles."
    )

    # --- figura nueva después de la Tabla IV ---
    pie_modelo = buscar("Fig. 4. Evidencia generada")  # ya renumerada
    img_modelo = pie_modelo._p.getprevious()
    nueva_img = copy.deepcopy(img_modelo)
    nuevo_pie = copy.deepcopy(pie_modelo._p)
    t4._tbl.addnext(nueva_img)
    nueva_img.addnext(nuevo_pie)
    p_img = docx.text.paragraph.Paragraph(nueva_img, det._parent)
    for r in list(p_img.runs):
        r._r.getparent().remove(r._r)
    p_img.add_run().add_picture(str(FIGURA), width=Emu(3017520))
    p_pie = docx.text.paragraph.Paragraph(nuevo_pie, det._parent)
    p_pie.runs[0].text = ("Fig. 3. Exactitud de la lectura en CARID (958 placas) según el ancho de la placa."
                          " La franja gris marca el tamaño de las placas en las cámaras públicas de tránsito.")
    for r in p_pie.runs[1:]:
        r.text = ""

    # --- limitaciones ---
    lim = buscar("Limitaciones.")
    reemplazar(lim, "Las métricas de percepción provienen de un único conjunto público, con una prueba de 97 imágenes.",
               "Las métricas del detector provienen de fotografías de conjuntos públicos, con una prueba principal"
               " de 97 imágenes y una segunda de solo 20.")
    reemplazar(lim, "Estas validaciones se realizaron", "Estas validaciones se realizarán")

    # --- referencias ---
    ref = next(p for p in d.paragraphs if "ByteTrack: Multi-object tracking" in p.text)
    ref.runs[-1].text += (
        "\n[26]\tfarichula, “peruvian_plates Dataset,” version 2, Roboflow Universe. License: Public Domain."
        " Accessed: Oct. 16, 2026. [Online]. Available: https://universe.roboflow.com/farichula/peruvian_plates"
        "\n[27]\tProyecto de Reconocimiento de Placas Vehiculares Perú, “CARID Dataset,” version 3,"
        " Roboflow Universe, May 2025. License: MIT. Accessed: Oct. 16, 2026. [Online]. Available:"
        " https://universe.roboflow.com/proyecto-de-reconocimiento-de-placas-vehiculares-peru/carid-clt7s"
    )

    reestructurar_alcance(d)
    d.save(DESTINO)
    print("Generado:", DESTINO)


# ---------- reestructuración del alcance (fase 1) ----------
def _quitar(elemento):
    elemento.getparent().remove(elemento)


def escribir(parrafo, cuerpo, lead=None):
    """Reescribe el párrafo conservando el formato de sus runs.

    `lead`: encabezado en cursiva al inicio («Módulo de búsqueda.»).
    En `cuerpo`, el texto entre §signos§ va en cursiva (variables).
    """
    runs = parrafo.runs
    if lead:
        tpl_lead = copy.deepcopy(runs[0]._r)
        tpl_cuerpo = copy.deepcopy(runs[1]._r)
    else:
        tpl_lead = None
        tpl_cuerpo = copy.deepcopy(runs[0]._r)
    for r in runs:
        _quitar(r._r)
    p = parrafo._p

    def agregar(tpl, texto, cursiva=None):
        r_el = copy.deepcopy(tpl)
        p.append(r_el)
        r = docx.text.run.Run(r_el, parrafo)
        r.text = texto
        if cursiva is not None:
            r.italic = cursiva

    if lead:
        agregar(tpl_lead, lead)
    for i, trozo in enumerate(cuerpo.split("§")):
        if trozo:
            agregar(tpl_cuerpo, trozo, cursiva=True if i % 2 else None)


def reestructurar_alcance(d):
    """Centra el paper en la fase 1: placas, conteo vehicular y BFS/DFS/A*.

    La velocidad, la placa clonada, las demás infracciones, la validación humana
    y las papeletas pasan a Trabajo futuro.
    """
    def buscar(inicio):
        return next(p for p in d.paragraphs if p.text.startswith(inicio))

    # Figuras que se mueven o se quitan, ubicadas por su pie (numeración actual).
    pie_evid = buscar("Fig. 4. Evidencia generada")
    pie_arq = buscar("Fig. 5. Arquitectura")
    pie_valid = buscar("Fig. 6. Pantalla de validación")
    pie_jp = buscar("Fig. 7. Vehículos detectados")
    pie_mapa = buscar("Fig. 8. Módulo de tránsito")

    # --- Introducción: objetivos por fases ---
    escribir(buscar("Finalmente, como propuesta"),
             "Finalmente, como propuesta, este trabajo plantea un sistema inteligente de foto-papeletas que, en su"
             " versión completa, integre la detección automática de infracciones, el reconocimiento de placas y el"
             " seguimiento vehicular sobre una red de cámaras representada mediante grafos. El objetivo general es"
             " diseñar un sistema de fiscalización vial inteligente que mejore la automatización y la trazabilidad"
             " del proceso de generación de foto-papeletas. Este artículo presenta la primera fase, cuyos objetivos"
             " específicos son: primero, detectar y leer placas vehiculares peruanas en videos de prueba mediante"
             " visión por computadora; segundo, contar vehículos a partir de las cámaras públicas de tránsito de"
             " Lima; y tercero, modelar la red de cámaras como un grafo y aplicar los algoritmos de búsqueda BFS, DFS"
             " y A* para delimitar dónde buscar un vehículo, enumerar sus trayectorias posibles y obtener la ruta"
             " mínima y la ruta más rápida según el tráfico medido. La detección de infracciones y la emisión de"
             " papeletas se plantean como trabajo futuro.")

    # --- II-A: visión completa + alcance de esta fase ---
    escribir(buscar("Se definió como un problema"),
             "Se definió como problema la limitada cobertura de la fiscalización presencial y la falta de"
             " trazabilidad de la evidencia. El sistema completo contempla tres actores —el validador, que revisa"
             " cada infracción; el administrador, que gestiona cámaras, parámetros y usuarios; y el ciudadano, que"
             " consulta sus papeletas— y siete tipos de infracción: exceso de velocidad, semáforo en rojo, invasión"
             " de cruce peatonal, uso de celular, giro prohibido, sentido contrario y no respetar las señales. Dado"
             " ese alcance, el desarrollo se organizó por fases. Esta primera fase construye la base sobre la que se"
             " apoyarán las infracciones: identificar al vehículo por su placa, medir el flujo vehicular y buscar en"
             " la red de cámaras. Sus criterios de éxito fueron: (i) que el detector de placas iguale o supere las"
             " métricas del modelo publicado con el conjunto de datos usado; (ii) que la lectura de placas se mida"
             " también en un conjunto independiente y se determine el tamaño mínimo de placa legible; (iii) que BFS,"
             " DFS y A* devuelvan los mismos resultados que una librería de referencia y respondan en el orden de"
             " milisegundos; y (iv) que el conteo vehicular funcione de forma continua sobre las cámaras públicas"
             " sin leer ni almacenar placas ni rostros. Como restricción legal se consideró la Ley N.° 29733 de"
             " Protección de Datos Personales.")

    # --- II-B: fuentes de datos ---
    escribir(buscar("Se identificaron tres fuentes"),
             "Se identificaron tres fuentes de datos. La primera son imágenes y videos de prueba de vehículos, para"
             " la detección y lectura de placas. Como aún no se cuenta con capturas propias en cantidad suficiente,"
             " se buscaron conjuntos públicos de placas peruanas: se eligió Peru License Plate [21], con 1.000"
             " fotografías de calles de Lima, una sola clase (placa) y licencia CC BY 4.0, en su versión de"
             " 640 × 640 px; luego se sumó peruvian_plates [26] para ampliar el entrenamiento, y CARID [27], cuyas"
             " etiquetas por carácter permiten evaluar la lectura; otro candidato, NumberPlates [22], se descartó en"
             " la fase de preparación. Los videos de prueba se grabaron con un teléfono móvil. La segunda es la"
             " topología de la red de cámaras, modelada como un grafo cuyos nodos son cámaras y cuyas aristas son"
             " tramos de vía con distancia (km) y tiempo típico de viaje (min); la Tabla I describe la red de"
             " evaluación, de coordenadas esquemáticas. La tercera son 15 cámaras públicas de tránsito de Lima, cuya"
             " señal emite la Municipalidad de Lima y difunde un operador de telecomunicaciones, que se usan para el"
             " conteo vehicular (sección III). Para vincular capturas de un mismo vehículo entre cámaras, la"
             " literatura de reidentificación vehicular advierte sobre la variación de resolución, punto de vista e"
             " iluminación entre cámaras [17], [18], las oclusiones parciales y el costo de etiquetar datos [19], y"
             " las condiciones desfavorables de iluminación y la baja resolución [20]. Por ello, en este trabajo el"
             " vínculo entre cámaras se basa en la placa leída, reforzado con restricciones derivadas del grafo, en"
             " lugar de un modelo de reidentificación por apariencia.")

    # --- II-C: redacción y quitar la dependencia de la velocidad ---
    escribir(buscar("Los videos se probaron"),
             "Los videos se muestrearon a entre 5 y 30 cuadros por segundo según la velocidad del vehículo,"
             " conservando el identificador de la cámara y la marca de tiempo. En cada cuadro se recortó la región"
             " de la placa, se amplió y se normalizó al formato peruano mediante la expresión ^[A-Z0-9]{3}-?\\d{3}$."
             " Para reducir errores de lectura, cada vehículo seguido entre cuadros acumula entre 5 y 10 lecturas y"
             " se conserva la más frecuente. Cada detección se transforma en un evento estructurado con placa,"
             " cámara, fecha, hora, confianza y recorte, que es la única interfaz entre la percepción y la búsqueda"
             " en el grafo. El grafo se almacenó como lista de adyacencia dirigida, en la que las vías de doble"
             " sentido generan dos arcos, y cada cámara recibió coordenadas proyectadas. Como control de calidad, se"
             " verificó que la distancia en línea recta entre cámaras conectadas nunca supere la longitud del tramo,"
             " condición necesaria para que la heurística de A* sea admisible.")
    escribir(buscar("La red de la Tabla I"),
             "La red de la Tabla I sirve para la evaluación algorítmica, pero sus distancias se fijaron a mano, y"
             " toda medida que dependa de ellas hereda ese error: la longitud de las rutas y, en la siguiente fase,"
             " la velocidad entre cámaras. Por ello se construyó una red con ubicaciones de OpenStreetMap y tramos"
             " por calles reales obtenidos con OSRM [24], con dos reglas: dos cámaras se unen solo si la ruta más"
             " corta entre ellas no pasa por otra cámara, y, para cada par de cámaras, la distancia mínima en el"
             " grafo no puede superar la distancia real por calles; si un par la supera, se agrega el tramo directo."
             " Con las 6 cámaras se obtuvieron 13 tramos, y en los 15 pares la distancia del grafo coincidió con la"
             " real. El tramo AV-01–AV-08, de 3.0 km en la red esquemática, mide 0.95 km por calles: la distancia"
             " fijada a mano triplicaba la real. Con el mismo procedimiento se construyó la red de las 15 cámaras"
             " públicas, con 19 tramos por los corredores viales y sus tiempos a flujo libre.")

    # --- II-D: percepción (última frase) y búsqueda sin velocidad ---
    perc = buscar("Módulo de percepción")
    viejo = ("En esta versión se implementó la infracción por exceso de velocidad; las demás requieren reglas"
             " geométricas configuradas por cámara (líneas de detención, zonas peatonales y sentido permitido)"
             " quedando como trabajo futuro.")
    nuevo = ("Para el conteo vehicular en las cámaras públicas se usó YOLOv8n pre entrenado en COCO, que ya"
             " incluye las clases auto, motocicleta, bus y camión, con el seguimiento ByteTrack [25] (sección III).")
    reemplazar(perc, viejo, nuevo)

    escribir(buscar("Módulo de búsqueda. Sobre"),
             " Sobre el grafo se implementaron tres algoritmos, en línea con su uso para analizar rutas en redes"
             " vehiculares [9]: BFS, que devuelve las cámaras alcanzables en §k§ saltos desde la cámara de origen y"
             " delimita dónde buscar nuevamente una placa leída; DFS, acotado en profundidad, que enumera las"
             " trayectorias alternativas entre dos cámaras; y A*, que obtiene la ruta de menor costo usando como"
             " heurística la distancia en línea recta, que nunca sobreestima la distancia por calles y por ello es"
             " admisible. Cuando el costo es el tiempo de viaje, la heurística divide esa distancia entre la"
             " velocidad máxima de la red, por lo que sigue siendo admisible. Para vincular capturas entre cámaras,"
             " las placas idénticas se confirman y las que difieren en caracteres confundibles (por ejemplo, B y 8)"
             " o en un solo carácter se marcan como «a verificar».",
             lead="Módulo de búsqueda.")

    # Velocidad por tramo: el párrafo, la ecuación (1) y su explicación pasan a trabajo futuro.
    vel = buscar("Velocidad por tramo")
    ecuacion = vel._p.getnext()
    explicacion = ecuacion.getnext()
    for el in (vel._p, ecuacion, explicacion):
        _quitar(el)

    # --- II-E: introducción de la evaluación ---
    escribir(buscar("La evaluación se realizó"),
             "La evaluación se realizó en tres partes: el módulo de búsqueda, la detección y lectura de placas, y el"
             " conteo vehicular en las cámaras públicas. Todo se implementó en Python 3.12 y se ejecutó en un equipo"
             " con procesador AMD Ryzen 5 9600X, 16 GB de RAM y GPU NVIDIA GeForce RTX 5070; el código cuenta con 139"
             " pruebas automáticas. Para la detección se usaron la precisión, la exhaustividad y el mAP; para la"
             " lectura, la tasa de error por carácter (CER) y el porcentaje de placas leídas completamente; y para"
             " la búsqueda, la coincidencia con una librería de referencia, los nodos explorados y el tiempo por"
             " consulta.")

    # --- Tabla II: quitar P5–P7 (velocidad y plausibilidad) y renumerar ---
    t2 = d.tables[1]
    for fila in list(t2.rows):
        if fila.cells[0].text.strip() in ("P5", "P6", "P7"):
            _quitar(fila._tr)
    for fila in t2.rows:
        ident = fila.cells[0].text.strip()
        if ident in ("P8", "P9", "P10"):
            poner_texto_celda(fila.cells[0], f"P{int(ident[1:]) - 3}")

    # --- Sistema completo -> cadena de percepción, sin velocidad; quitar Fig. de evidencia ---
    escribir(buscar("Sistema completo."),
             " Se integró la cadena cuadro, detección, seguimiento, lectura con votación y evento estructurado, y"
             " se probó con secuencias de 8 cuadros a 5 fps construidas a partir de fotografías reales de tres"
             " vehículos vistos por dos cámaras: cada cuadro se procesó en 24 a 32 ms y los eventos de cada"
             " vehículo se vincularon entre cámaras por su placa. La placa V8D-001 se leyó VBD-001 en ambas"
             " cámaras; el vínculo se mantuvo porque el error es consistente, pero muestra que la lectura debe"
             " revisarse antes de cualquier uso sancionador. Esta prueba se mantuvo con EasyOCR y el detector v1"
             " para que sus resultados sean reproducibles.",
             lead="Cadena de percepción.")
    _quitar(pie_evid._p.getprevious())
    _quitar(pie_evid._p)

    # --- Cámaras públicas: conclusión + conteo vehicular (antes «Tránsito en vivo», en F) ---
    pub = buscar("Cámaras públicas de tránsito")
    reemplazar(pub, "Por ello no se usaron para fiscalizar, sino para medir el flujo vehicular (sección F).",
               "La Fig. «OCR» explica este resultado: a 40 px el mejor lector ya acierta solo el 39.1" + PCT +
               " de las placas. Por ello estas cámaras se usan para contar vehículos y no para leer placas.")

    transito = buscar("Tránsito en vivo.")
    escribir(transito,
             " Cada pocos minutos se analizan 10 s de video de cada cámara pública a 10 cuadros por segundo con"
             " YOLOv8n pre entrenado en COCO y el seguimiento ByteTrack [25], que cuenta autos, motocicletas, buses"
             " y camiones sin leer ni almacenar placas (Fig. «JP»). Solo se cuenta un vehículo seguido en 5 cuadros"
             " o más que se desplazó al menos un cuarto de su ancho, para no contar vehículos estacionados ni"
             " fragmentos del seguimiento; el monitor midió las 15 cámaras en 5 rondas consecutivas sin errores. El"
             " tráfico de cada cámara se expresa en relación con su propio comportamiento habitual —los vehículos"
             " visibles frente a la mediana de sus últimas 30 mediciones— y ese factor, acotado entre 1 y 3, alarga"
             " el tiempo de los tramos adyacentes, obtenidos por calles reales con OSRM [24]. Sobre esa red, A*"
             " calcula la ruta más rápida en el momento con la heurística de línea recta dividida entre la"
             " velocidad máxima de la red; una prueba automática verificó que es admisible en los 38 arcos. Por"
             " ejemplo, de Av. La Marina a la Panamericana Sur estimó 31.0 min frente a 27.8 min a flujo libre"
             " (Fig. «MAPA»). La tasa de vehículos por minuto depende de los umbrales del seguimiento: en Av."
             " Javier Prado pasó de 360 a 180 vehículos por minuto al exigir movimiento, confianza de 0.4 y 5"
             " cuadros. Por ello la congestión se calcula con la medida más estable, los vehículos visibles a la"
             " vez, y el conteo por minuto se reporta como aproximado.",
             lead="Conteo vehicular y ruta más rápida.")
    # mover: conteo -> imagen JP + pie -> imagen mapa + pie, justo después de «Cámaras públicas»
    bloque = [transito._p, pie_jp._p.getprevious(), pie_jp._p, pie_mapa._p.getprevious(), pie_mapa._p]
    ancla = pub._p
    for el in bloque:
        ancla.addnext(el)
        ancla = el

    # --- Limitaciones ---
    escribir(buscar("Limitaciones."),
             " Las métricas del detector provienen de fotografías de conjuntos públicos, con una prueba principal"
             " de 97 imágenes y una segunda de solo 20. La transcripción de las 30 placas reales la hizo un solo"
             " evaluador y las reglas de extracción se diseñaron a partir de sus errores, por lo que ese resultado"
             " es optimista; CARID aporta una medida independiente. El video real se limitó a dos clips comprimidos"
             " a 848 × 480 px, y no se evaluaron placas de motocicleta, especiales ni pintadas en la carrocería. El"
             " conteo por minuto aún no se ha contrastado con un conteo manual, la congestión habitual requiere"
             " varios días de mediciones y los tiempos de OSRM corresponden a flujo libre. Estas validaciones se"
             " realizarán con capturas propias en la siguiente fase.",
             lead="Limitaciones.")

    # --- F. Despliegue: reducido al alcance de la fase ---
    escribir(buscar("El despliegue sigue"),
             "El despliegue sigue la arquitectura por capas de la Fig. «ARQ». Un proceso independiente en Python"
             " ejecuta la percepción y envía los eventos por HTTP a una aplicación Django con Django REST Framework,"
             " que almacena las detecciones y ejecuta el módulo de búsqueda, implementado como paquete independiente"
             " y reutilizado por la web y por la evaluación. Separar la inferencia del servidor web evita bloquear"
             " las peticiones, y registrar la versión de los modelos y del grafo en cada resultado responde a la"
             " recomendación de monitoreo continuo de CRISP-ML(Q) [12]. El conteo vehicular corre en un segundo"
             " proceso que mide las cámaras públicas en ciclos de 2 minutos.")
    reemplazar(pie_arq, "Arquitectura por capas del sistema y procesos que la implementan.",
               "Arquitectura por capas del sistema completo y procesos que la implementan; esta fase cubre la"
               " captura, la percepción, los datos y el grafo, y el análisis.")
    _quitar(buscar("El backend se")._p)
    escribir(buscar("La interfaz se"),
             "La interfaz se diseñó primero como prototipo de alta fidelidad en pencil.dev y se implementó con"
             " plantillas de Django, Tailwind CSS, HTMX y Alpine.js. Para esta fase destacan tres pantallas: la carga"
             " de evidencia, que procesa una foto o un video con el mismo detector y lector y presenta las placas no"
             " leídas con su recorte para registrarlas a mano; el laboratorio del grafo, que ejecuta BFS, DFS y A*"
             " sobre la red y compara sus métricas (Fig. «AEST»); y el tránsito en vivo, con las cámaras públicas"
             " coloreadas según su congestión y la ruta más rápida dibujada sobre las vías reales (Fig. «MAPA»).")
    # quitar pantalla de validación (Fig.) y Tabla V
    _quitar(pie_valid._p.getprevious())
    _quitar(pie_valid._p)
    titulo_t5 = buscar("TABLA V")
    sub_t5 = buscar("Pruebas funcionales")
    tabla_t5 = sub_t5._p.getnext()
    assert tabla_t5.tag.endswith("tbl")
    for el in (titulo_t5._p, sub_t5._p, tabla_t5):
        _quitar(el)

    resultados_discusion_conclusiones(d, buscar)

    # --- renumerar figuras por orden de aparición y resolver las marcas «...» ---
    claves = {"Ejecución de A*": "AEST", "Exactitud de la lectura": "OCR", "Vehículos detectados": "JP",
              "Módulo de tránsito": "MAPA", "Arquitectura por capas": "ARQ"}
    numero = {}
    n = 0
    for p in d.paragraphs:
        if p.text.startswith("Fig. ") and p.text[5:6].isdigit():
            n += 1
            for r in p.runs:
                if re.match(r"Fig\. \d+\. ", r.text):
                    r.text = re.sub(r"^Fig\. \d+\. ", f"Fig. {n}. ", r.text)
                    break
            else:
                raise ValueError(f"Pie de figura con formato inesperado: {p.text[:40]!r}")
            for frase, clave in claves.items():
                if frase in p.text:
                    numero[clave] = n
    for p in d.paragraphs:
        for r in p.runs:
            for clave, k in numero.items():
                if f"Fig. «{clave}»" in r.text:
                    r.text = r.text.replace(f"Fig. «{clave}»", f"Fig. {k}")
    restos = [p.text[:60] for p in d.paragraphs if re.search(r"Fig\. «", p.text)]
    assert not restos, restos


def resultados_discusion_conclusiones(d, buscar):
    """III. Resultados y discusión (A. Resultados, B. Discusión) y IV. Conclusiones.

    II-E queda como protocolo de evaluación; las tablas, figuras y cifras pasan a III-A;
    Limitaciones pasa a III-B; el trabajo futuro cierra las conclusiones.
    """
    def parrafo(el):
        return docx.text.paragraph.Paragraph(el, d._body)

    tpl_seccion = buscar("II. M")._p          # «II. METODOLOGÍA»
    tpl_sub = buscar("E. Evaluación")._p      # «E. Evaluación»
    tpl_texto = buscar("La evaluación se realizó")._p
    tpl_lead = buscar("Video real.")._p       # párrafo con encabezado en cursiva

    def seccion(texto_a, texto_b):
        el = copy.deepcopy(tpl_seccion)
        p = parrafo(el)
        p.runs[0].text, p.runs[1].text = texto_a, texto_b
        return el

    def subseccion(texto):
        el = copy.deepcopy(tpl_sub)
        p = parrafo(el)
        p.runs[0].text = texto
        for r in p.runs[1:]:
            r.text = ""
        return el

    def texto(cuerpo, lead=None):
        el = copy.deepcopy(tpl_lead if lead else tpl_texto)
        escribir(parrafo(el), cuerpo, lead=lead)
        return el

    # --- II-E: protocolo de evaluación (sin resultados) ---
    protocolo = texto(
        "En el módulo de búsqueda, BFS, DFS y A* se compararon con la librería"
        " NetworkX 3.7, usada como referencia independiente, en la red de la Tabla I (6 cámaras y sus 30 pares"
        " ordenados) y en una rejilla sintética de 400 cámaras y 760 tramos con 300 consultas aleatorias, midiendo"
        " el costo de la ruta, los nodos explorados y el tiempo por consulta, con y sin heurística. El detector de"
        " placas, YOLOv8n pre entrenado en COCO, se ajustó durante 100 épocas a 640 × 640 px sobre la división sin"
        " fugas de la sección C y se evaluó en la prueba de 97 imágenes y en una segunda prueba de 20 imágenes"
        " difíciles. La lectura se evaluó con EasyOCR y fast-plate-ocr sobre 600 placas sintéticas, 30 placas"
        " reales transcritas a mano y 958 placas de CARID, que además se redujeron a 120, 80, 60 y 40 px de ancho"
        " para simular la distancia. Por último, se midió el tamaño de las placas en las cámaras públicas y se puso"
        " en marcha el conteo vehicular continuo en las 15 cámaras.")
    tpl_texto.addnext(protocolo)

    # --- mover los resultados de II-E a III-A ---
    inicio = buscar("Módulo de búsqueda. Se verificó")
    escribir(inicio, " La Tabla II resume los casos de prueba y sus resultados frente a NetworkX.",
             lead="Módulo de búsqueda.")
    reemplazar(buscar("Los resultados confirman"), "La Fig. 2 muestra", "La Fig. «AEST» muestra")
    reemplazar(buscar("Detector de placas."),
               " Se ajustó YOLOv8n, pre entrenado en COCO, durante 100 épocas a 640 × 640 px sobre la división sin"
               " fugas descrita en la sección C; el entrenamiento tomó",
               " El entrenamiento tomó")
    limitaciones = buscar("Limitaciones.")._p
    fin_e = buscar("F. Despliegue")._p
    movidos = []
    el = inicio._p
    while el is not fin_e:
        movidos.append(el)
        el = el.getnext()
    movidos.remove(limitaciones)

    refs = buscar("REFERENCIAS")._p
    nuevos = [seccion("III. R", "ESULTADOS Y DISCUSIÓN"), subseccion("A. Resultados")]
    nuevos += movidos
    nuevos.append(subseccion("B. Discusión"))
    nuevos += [texto(t) for t in [
        "En el módulo de búsqueda, la coincidencia total con NetworkX (30/30 y 300/300) confirma que la"
        " heurística de línea recta es admisible: reduce el trabajo sin alterar el costo de la ruta. Su beneficio"
        " depende del tamaño de la red: con 6 cámaras, calcular la heurística hace a A* algo más lento que sin"
        " ella (4.7 frente a 3.6 µs), mientras que con 400 cámaras reduce los nodos explorados en 58.5" + PCT +
        " y el tiempo por consulta de 0.212 a 0.126 ms. Como la red de una ciudad tendría cientos de cámaras, la"
        " heurística está justificada. Este uso complementa el de [9], que aplica BFS, DFS y A* a la selección"
        " de rutas en redes vehiculares: aquí los mismos algoritmos operan sobre una red de cámaras, BFS para"
        " acotar dónde buscar una placa, DFS para enumerar trayectorias y A* para obtener la ruta mínima o la más"
        " rápida según el tráfico medido. La red construida con OSRM mostró además que la calidad del grafo"
        " importa tanto como el algoritmo: una distancia fijada a mano triplicaba la real.",

        "En detección, el YOLOv8n ajustado superó al modelo publicado con el mismo conjunto [21] (mAP@50 de"
        " 97.1" + PCT + " frente a 85.6" + PCT + "), aunque la comparación no es directa por la resolución y la"
        " división usadas. La auditoría de duplicados fue decisiva: la división original filtraba imágenes de"
        " entrenamiento a la prueba, y NumberPlates [22] resultó ser una copia del conjunto base, por lo que"
        " combinarlos habría inflado las métricas sin aportar datos. El modelo v2 mejoró sobre todo la"
        " exhaustividad en imágenes difíciles, pero dejó de detectar el número pintado en la puerta de los taxis,"
        " que v1 leía por coincidencia: un detector solo reconoce los tipos de placa presentes en sus datos.",

        "En lectura, el factor determinante fue usar un lector especializado: fast-plate-ocr superó a EasyOCR en"
        " todos los conjuntos y tamaños, y en CARID leyó seis veces más placas completas (62.3" + PCT + " frente"
        " a 10.3" + PCT + "). La precisión de reconocimiento de 98.22" + PCT + " reportada en [6] se obtuvo con"
        " otros datos y condiciones, por lo que no es comparable directamente; la diferencia con nuestra medida"
        " se explica por fotografías nocturnas, movidas o sucias, por errores de etiqueta y por la ausencia de"
        " placas peruanas en el entrenamiento del lector, reflejada en la confusión de T con Y. El 86.7" + PCT +
        " obtenido con 30 placas fue optimista, y la evaluación con un conjunto independiente lo corrigió, lo que"
        " muestra la importancia de evaluar con datos que no se usaron para diseñar el sistema.",

        "El hallazgo con mayor consecuencia práctica es la relación entre el tamaño de la placa y la lectura"
        " (Fig. «OCR»): la exactitud se mantiene estable hasta 60 px y cae a 39.1" + PCT + " a 40 px. Las"
        " cámaras públicas de tránsito muestran las placas entre 16 y 40 px, por debajo de ese umbral, lo que"
        " coincide con la baja resolución que [4] señala como uno de los desafíos del reconocimiento de placas."
        " En consecuencia, leer placas requiere cámaras dedicadas, cercanas a la vía, con la placa a 80 px o más,"
        " mientras que la infraestructura pública existente ya es útil para medir el flujo vehicular sin"
        " entrenamiento adicional y sin tratar datos personales. El conteo funcionó de forma continua, pero su"
        " tasa por minuto depende de los umbrales del seguimiento, porque los vehículos lejanos ocupan pocos"
        " píxeles; por eso la congestión se basó en los vehículos visibles relativos a cada cámara, y la ruta"
        " más rápida de A* depende de un factor estimado y no de velocidades medidas.",
    ]]
    nuevos.append(limitaciones)
    nuevos.append(seccion("IV. C", "ONCLUSIONES"))
    nuevos += [texto(t) for t in [
        "Este trabajo presentó la primera fase de un sistema de fiscalización vial inteligente, centrada en"
        " identificar vehículos por su placa, medir el flujo vehicular y buscar en una red de cámaras con"
        " algoritmos de búsqueda. Respecto del primer objetivo, el detector YOLOv8n ajustado con placas peruanas"
        " alcanzó un mAP@50 de 97.1" + PCT + " y una exhaustividad de 93.8" + PCT + " en una prueba sin fugas, y"
        " el lector especializado leyó completas el 62.3" + PCT + " de 958 placas de un conjunto independiente,"
        " seis veces más que un OCR genérico; la exactitud cae a 39.1" + PCT + " cuando la placa mide 40 px, lo"
        " que fija el requisito de captura del sistema.",

        "Respecto del segundo objetivo, las cámaras públicas de tránsito evaluadas no permiten leer placas, pero"
        " las 15 permiten contar vehículos de forma continua con un modelo pre entrenado, sin almacenar placas"
        " ni rostros. Respecto del tercero, BFS, DFS y A* coincidieron con la librería de referencia en todos los"
        " casos; la heurística de línea recta redujo en 58.5" + PCT + " los nodos explorados en una red de 400"
        " cámaras sin alterar el costo, con consultas por debajo de un milisegundo, y permitió calcular la ruta"
        " más rápida según el tráfico medido. En conjunto, los resultados muestran que los algoritmos de"
        " búsqueda en grafos son una base eficiente para relacionar las capturas de una red de cámaras, y que el"
        " factor limitante del sistema no es la búsqueda sino la percepción: la calidad de la captura y la"
        " diversidad de los datos de entrenamiento.",

        "Como trabajo futuro, el sistema completo se desarrollará por fases sobre la base presentada. La"
        " siguiente fase incorporará la velocidad promedio entre cámaras: como base, se desarrolló un prototipo"
        " que la calcula con la distancia mínima obtenida con A* y el tiempo entre dos capturas de la misma"
        " placa, sumando un margen por el posible desfase de reloj de cada cámara, de modo que el resultado sea"
        " una cota inferior de la velocidad real, a favor del conductor; por ahora solo se verificó con capturas"
        " simuladas. Su validación requiere cámaras propias cerca de la vía, a una distancia conocida y con la"
        " placa a 80 px o más de ancho. Con la misma búsqueda en el grafo se detectarán placas posiblemente"
        " clonadas: si recorrer la distancia mínima entre dos capturas exige una velocidad físicamente"
        " imposible, se generará una alerta en lugar de una infracción.",

        "Las demás infracciones —semáforo en rojo, invasión de cruce peatonal, uso de celular, giro prohibido,"
        " sentido contrario y no respetar las señales— requieren reglas geométricas configuradas por cámara,"
        " como líneas de detención, zonas peatonales y sentido permitido. Ninguna papeleta se emitirá sin"
        " validación humana: el validador revisará la evidencia y podrá corregir la placa leída, y el ciudadano"
        " podrá consultar sus papeletas y solicitar una revisión. En percepción, se reunirán imágenes de placas"
        " pintadas en la carrocería de combis y taxis para reentrenar el detector, se ajustará el lector con"
        " placas peruanas para corregir la confusión entre T e Y, y se contrastará el conteo vehicular con"
        " conteos manuales. Por último, la consulta de los datos del vehículo requerirá un convenio con la SUNARP"
        " a través de la Plataforma de Interoperabilidad del Estado, y el difuminado automático de placas y"
        " rostros de terceros, para cumplir la Ley N.° 29733.",
    ]]
    for el in nuevos:
        refs.addprevious(el)


if __name__ == "__main__":
    main()
