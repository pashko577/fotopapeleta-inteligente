"""Evalúa los lectores de placas con CARID: el texto real sale de las etiquetas por carácter (no de una transcripción propia).

- Una muestra por placa distinta (las fotos de CARID repiten placas en varias versiones aumentadas).
- Se lee el recorte de la caja «Car-Plate» con un margen del 10 %, como el recorte del detector.
- Además del tamaño original, cada placa se reduce a 120, 80, 60 y 40 px de ancho para medir cómo cae la lectura
  con la distancia a la cámara (las fotos de CARID son de 3000 × 4000 px y sus placas, grandes).

Uso: python -m evaluacion.evaluar_ocr_carid  -> evaluacion/resultados/ocr_carid.json
"""
import json
import pathlib
import re
import time

import cv2
import torch
import yaml

from percepcion.datos.auditar_duplicados import origen
from percepcion.ocr import LectorPlacas, cer

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CARID = RAIZ / "datasets" / "carid"
ANCHOS = [None, 120, 80, 60, 40]  # None = tamaño original
FORMATO = re.compile(r"^[A-Z0-9]{3}[0-9]{3}$")


def muestras():
    """[(texto, imagen, caja)] con una muestra por placa distinta."""
    names = yaml.safe_load(open(CARID / "data.yaml"))["names"]
    vistas, salida = set(), []
    for lab in sorted(CARID.rglob("labels/*.txt")):
        cajas = [list(map(float, l.split())) for l in lab.read_text().splitlines() if l.strip()]
        placas = [c for c in cajas if names[int(c[0])] == "Car-Plate"]
        chars = [c for c in cajas if names[int(c[0])] != "Car-Plate"]
        for _, px, py, pw, ph in placas:
            dentro = sorted([c for c in chars if abs(c[1] - px) < pw / 2 and abs(c[2] - py) < ph / 2], key=lambda c: c[1])
            texto = "".join(names[int(c[0])] for c in dentro)
            if not FORMATO.match(texto) or texto in vistas:
                continue
            img = next((p for p in lab.parent.parent.glob(f"images/{lab.stem}.*")), None)
            if img is None:
                continue
            vistas.add(texto)
            salida.append((texto, img, (px, py, pw, ph), origen(lab.stem)))
    return salida


def recortar(img, caja, margen=0.10):
    h, w = img.shape[:2]
    px, py, pw, ph = caja
    x1, x2 = (px - pw / 2 * (1 + 2 * margen)) * w, (px + pw / 2 * (1 + 2 * margen)) * w
    y1, y2 = (py - ph / 2 * (1 + 2 * margen)) * h, (py + ph / 2 * (1 + 2 * margen)) * h
    return img[max(int(y1), 0):min(int(y2), h), max(int(x1), 0):min(int(x2), w)]


def metricas(pares):
    n = len(pares)
    return {"n": n, "exactitud": round(sum(p == r for p, r in pares) / n, 4),
            "cer": round(sum(cer(p, r) for p, r in pares) / n, 4), "sin_lectura": round(sum(p == "" for p, _ in pares) / n, 4)}


def main():
    datos = muestras()
    print(f"{len(datos)} placas distintas con texto válido")
    lectores = {"fast-plate-ocr": LectorPlacas(motor="fast-plate-ocr"),
                "easyocr": LectorPlacas(gpu=torch.cuda.is_available(), motor="easyocr")}
    detalle, tiempos = [], {k: 0.0 for k in lectores}
    for i, (texto, ruta, caja, org) in enumerate(datos):
        rec = recortar(cv2.imread(str(ruta)), caja)
        fila = {"real": texto, "origen": org, "ancho_original": rec.shape[1]}
        for ancho in ANCHOS:
            r = rec if ancho is None or rec.shape[1] <= ancho else cv2.resize(rec, (ancho, max(int(rec.shape[0] * ancho / rec.shape[1]), 1)), interpolation=cv2.INTER_AREA)
            for nombre, lector in lectores.items():
                t0 = time.perf_counter()
                fila[f"{nombre}@{ancho or 'orig'}"] = lector.leer(r)[0]
                tiempos[nombre] += time.perf_counter() - t0
        detalle.append(fila)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(datos)}")
    resultados = {f"{n}@{a or 'orig'}": metricas([(d[f'{n}@{a or 'orig'}'], d["real"]) for d in detalle]) for n in lectores for a in ANCHOS}
    salida = {"placas": len(detalle), "ms_por_lectura": {k: round(v / (len(detalle) * len(ANCHOS)) * 1000, 1) for k, v in tiempos.items()},
              "resultados": resultados, "detalle": detalle}
    (RAIZ / "evaluacion" / "resultados" / "ocr_carid.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, m in resultados.items():
        print(f"{k:<24} exactitud {100 * m['exactitud']:5.1f} %  CER {100 * m['cer']:5.1f} %  sin lectura {100 * m['sin_lectura']:4.0f} %")
    print("ms por lectura:", salida["ms_por_lectura"])


if __name__ == "__main__":
    main()
