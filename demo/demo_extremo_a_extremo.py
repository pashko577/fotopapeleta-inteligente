"""Demostración de punta a punta: cuadros de cámara -> placa -> evento -> grafo -> infracción.

Como aún no hay video propio, cada "pasada" de un auto por una cámara se SIMULA a partir de
una foto real del conjunto de prueba: 8 cuadros a 5 fps con acercamiento progresivo, temblor,
desenfoque y ruido, y un aspecto distinto por cámara (luz, ángulo). Todo lo demás es el
sistema real: detector entrenado, OCR con votación, paquete grafo/.

Uso:  python -m demo.demo_extremo_a_extremo
Salida: demo/salida/ (eventos.json, resultado.json, reporte.md y evidencias)
"""
import json
import random
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import torch

import grafo
from percepcion.datos.construir_split import normalizar_etiquetas
from percepcion.ocr import LectorPlacas
from percepcion.pipeline import DetectorPlacas, PipelineCamara

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "demo" / "salida"
PESOS = RAIZ / "runs" / "placas" / "yolov8n_peru" / "weights" / "best.pt"  # v1 fijo: resultados de docs/pruebas/07 y del paper
FOTOS = RAIZ / "datasets" / "combinado" / "test" / "images"
FPS, CUADROS = 5, 8

# Aspecto de cada cámara: luz y ángulo distintos
CAMARAS = {"AV-01": dict(luz=1.0, giro=0), "AV-08": dict(luz=0.8, giro=3), "AV-12": dict(luz=0.9, giro=-2)}

# (placa esperada, foto real, pasadas [(cámara, hora)], resultado esperado)
ESCENARIOS = [
    ("V8D-001", "peru_billy_00075.jpg", [("AV-01", "08:42:00"), ("AV-08", "08:44:00")], "infracción: 3.0 km en 120 s"),
    ("D9R-052", "peru_billy_02211.jpg", [("AV-01", "08:43:10"), ("AV-08", "08:46:30")], "sin infracción: 3.0 km en 200 s"),
    ("T3P-298", "peru_billy_00156.jpg", [("AV-01", "08:45:00"), ("AV-12", "08:46:00")], "captura imposible: 1 min cuando el mínimo es 9 min"),
]


def centro_placa(nombre_foto, w, h):
    """Centro de la placa más grande según la ETIQUETA del dataset (no el detector)."""
    texto = (FOTOS.parent / "labels" / (Path(nombre_foto).stem + ".txt")).read_text()
    cajas = [list(map(float, l.split()[1:])) for l in normalizar_etiquetas(texto).splitlines()]  # polígonos -> cajas
    cx, cy, _, _ = max(cajas, key=lambda c: c[2] * c[3])
    return cx * w, cy * h


def simular_pasada(foto, camara, rnd, centro):
    """8 cuadros del auto acercándose a la cámara; el acercamiento sigue a la placa."""
    h, w = foto.shape[:2]
    p = CAMARAS[camara]
    for i in range(CUADROS):
        s = 0.95 - 0.25 * i / (CUADROS - 1)  # recorte cada vez más chico = auto más cerca
        cw, ch = int(w * s), int(h * s)
        a = i / (CUADROS - 1)  # el centro del recorte se desplaza hacia la placa
        cx = int((1 - a) * w / 2 + a * centro[0]) + rnd.randint(-6, 6)
        cy = int((1 - a) * h / 2 + a * centro[1]) + rnd.randint(-6, 6)
        x0, y0 = min(max(cx - cw // 2, 0), w - cw), min(max(cy - ch // 2, 0), h - ch)
        img = cv2.resize(foto[y0:y0 + ch, x0:x0 + cw], (w, h))
        if p["giro"]:
            M = cv2.getRotationMatrix2D((w / 2, h / 2), p["giro"], 1.0)
            img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        sigma = rnd.uniform(0.0, 1.0)
        if sigma > 0.1:
            img = cv2.GaussianBlur(img, (0, 0), sigma)
        ruido = np.random.default_rng(rnd.randint(0, 1 << 30)).normal(0, 4, img.shape)
        yield np.clip(img.astype(np.float32) * p["luz"] + ruido, 0, 255).astype(np.uint8)


def motor(g, nodos, eventos):
    """Lo que hace la API al recibir cada evento (misma función: grafo.evaluar_evento)."""
    capturas, infracciones, alertas, sin_infraccion = [], [], [], []
    for e in sorted(eventos, key=lambda x: x["timestamp"]):
        actual = {"id": e["evento_id"], "placa": e["placa"], "camara": e["camara_id"],
                  "ts": datetime.fromisoformat(e["timestamp"])}
        r = grafo.evaluar_evento(g, nodos, actual, capturas)
        for fila in r["infracciones"] + r["sin_infraccion"] + r["alertas"]:
            fila["eventos"] = [fila["captura_anterior"], fila["captura_actual"]]
        infracciones += r["infracciones"]
        sin_infraccion += r["sin_infraccion"]
        alertas += r["alertas"]
        capturas.append(actual)
    return infracciones, sin_infraccion, alertas


def figura_infraccion(inf, eventos):
    """Panel de evidencia: los dos cuadros de cámara lado a lado y los datos del cálculo."""
    por_id = {e["evento_id"]: e for e in eventos}
    cuadros = []
    for ev_id in inf["eventos"]:
        e = por_id[ev_id]
        im = cv2.resize(cv2.imread(str(SALIDA / "evidencia" / e["evidencia"][0])), (480, 480))
        cuadros.append(im)
    panel = np.hstack(cuadros)
    pie = np.full((120, panel.shape[1], 3), 255, np.uint8)
    lineas = [f"INFRACCION {inf['placa']}  |  ruta {' -> '.join(inf['ruta'])}  |  {inf['km']} km en {inf['segundos']:.0f} s",
              f"velocidad medida {inf['v_medida']} km/h  |  conservadora {inf['v_conservadora']} km/h  |  limite {inf['limite']} km/h  |  exceso +{inf['exceso']} km/h",
              "Pasa a la cola de validacion humana (no se emite automaticamente)"]
    for k, t in enumerate(lineas):
        cv2.putText(pie, t, (12, 32 + 34 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 180) if k == 0 else (40, 40, 40), 2 if k == 0 else 1)
    return np.vstack([panel, pie])


def main():
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    (SALIDA / "evidencia").mkdir(parents=True)
    g, nodos = grafo.cargar(RAIZ / "data" / "grafo_camaras.json")
    disp = 0 if torch.cuda.is_available() else "cpu"
    detector = DetectorPlacas(PESOS, conf=0.5, dispositivo=disp)
    lector = LectorPlacas(gpu=torch.cuda.is_available(), motor="easyocr")  # resultados de docs/pruebas/07 y del paper
    info = {"detector": "yolov8n_peru (época 82)", "ocr": "easyocr 1.7.2 + formato + extracción + votación"}
    pipes = {c: PipelineCamara(detector, lector, c, carpeta_evidencia=SALIDA / "evidencia", modelo_info=info) for c in CAMARAS}
    rnd = random.Random(11)
    eventos, tiempos = [], []
    for placa, foto, pasadas, _ in ESCENARIOS:
        img = cv2.imread(str(FOTOS / foto))
        centro = centro_placa(foto, img.shape[1], img.shape[0])
        for camara, hora in pasadas:
            t0 = datetime.combine(datetime(2026, 10, 15), datetime.strptime(hora, "%H:%M:%S").time())
            for i, cuadro in enumerate(simular_pasada(img, camara, rnd, centro)):
                s = time.perf_counter()
                eventos += pipes[camara].procesar_cuadro(cuadro, t0 + timedelta(seconds=i / FPS))
                tiempos.append(time.perf_counter() - s)
            eventos += pipes[camara].finalizar()  # el auto salió del cuadro
    infracciones, sin_inf, alertas = motor(g, nodos, eventos)

    esperadas = {p for p, *_ in ESCENARIOS}
    leidas = {e["placa"] for e in eventos}
    resultado = {"cuadros_procesados": len(tiempos), "ms_por_cuadro_promedio": round(1000 * float(np.mean(tiempos[1:])), 1),
                 "eventos": len(eventos), "placas_esperadas_leidas": sorted(esperadas & leidas),
                 "placas_esperadas_no_leidas": sorted(esperadas - leidas), "lecturas_distintas_de_la_esperada": sorted(leidas - esperadas),
                 "pistas_descartadas_sin_lectura": sum(p.descartadas for p in pipes.values()),
                 "infracciones": infracciones, "sin_infraccion": sin_inf, "alertas": alertas}
    (SALIDA / "eventos.json").write_text(json.dumps(eventos, ensure_ascii=False, indent=1), encoding="utf-8")
    (SALIDA / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for inf in infracciones:
        cv2.imwrite(str(SALIDA / f"infraccion_{inf['placa']}.jpg"), figura_infraccion(inf, eventos))

    rep = ["# Resultado de la demo de punta a punta", "", f"Cuadros procesados: {len(tiempos)} · "
           f"tiempo medio por cuadro (detector + OCR): {resultado['ms_por_cuadro_promedio']} ms", "",
           "## Eventos emitidos por las cámaras", "", "| Evento | Cámara | Hora | Placa | Lecturas por cuadro | Votadas |", "|---|---|---|---|---|---|"]
    for e in eventos:
        rep.append(f"| {e['evento_id']} | {e['camara_id']} | {e['timestamp'][11:19]} | **{e['placa']}** | {' '.join(e['lecturas'])} | {e['lecturas_votadas']}/{e['lecturas_totales']} |")
    rep += ["", "## Decisiones del motor (grafo)", ""]
    for inf in infracciones:
        rep.append(f"- **INFRACCIÓN {inf['placa']}**: {' → '.join(inf['ruta'])}, {inf['km']} km en {inf['segundos']:.0f} s → "
                   f"{inf['v_conservadora']} km/h conservadora (límite {inf['limite']}), exceso +{inf['exceso']} km/h. Pasa a validación humana.")
    for s in sin_inf:
        rep.append(f"- Sin infracción {s['placa']}: {s['km']} km en {s['segundos']:.0f} s → {s['v_conservadora']} km/h.")
    for a in alertas:
        rep.append(f"- **ALERTA {a['placa']}**: {a['de']} → {a['a']} ({a['km_minimos']} km) en {a['minutos_observados']} min: exigiría {a['velocidad_necesaria_kmh']} km/h (máximo plausible {a['velocidad_maxima_plausible_kmh']}). {a['motivo']}.")
    (SALIDA / "reporte.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
