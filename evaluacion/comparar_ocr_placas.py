"""Compara el OCR actual (EasyOCR + preproceso + extracción) con fast-plate-ocr (modelos entrenados con placas).

Mismas 30 placas reales de autos transcritas a mano que docs/pruebas/06 (evaluacion/resultados/ocr_real_transcripcion.csv).
Uso: python -m evaluacion.comparar_ocr_placas   (requiere requirements-ml.txt y fast-plate-ocr)
"""
import csv
import json
import time
from pathlib import Path

import cv2
import torch

from percepcion.ocr import LectorPlacas, cer, extraer_placa, normalizar

RAIZ = Path(__file__).resolve().parent.parent
RECORTES = RAIZ / "datasets" / "ocr_real" / "recortes"
MODELOS_FPO = ["cct-s-v2-global-model", "cct-xs-v2-global-model", "global-plates-mobile-vit-v2-model"]


def metricas(pares):
    n = len(pares)
    return {"n": n, "exactitud": round(sum(p == r for p, r in pares) / n, 4),
            "cer": round(sum(cer(p, r) for p, r in pares) / n, 4),
            "sin_lectura": round(sum(p == "" for p, _ in pares) / n, 4)}


def main():
    from fast_plate_ocr import LicensePlateRecognizer

    filas = [f for f in csv.DictReader(open(RAIZ / "evaluacion" / "resultados" / "ocr_real_transcripcion.csv", encoding="utf-8"))
             if f["categoria"] == "auto"]
    easy = LectorPlacas(gpu=torch.cuda.is_available(), motor="easyocr")
    fpo = {m: LicensePlateRecognizer(m, device="cpu") for m in MODELOS_FPO}
    detalle, tiempos = [], {k: 0.0 for k in ["easyocr", *MODELOS_FPO]}
    for f in filas:
        ruta = RECORTES / f["recorte"]
        img = cv2.imread(str(ruta))
        fila = {"id": f["id"], "real": f["texto_real"], "ancho_px": int(f["ancho_px"]), "certeza": f["certeza"]}
        t = time.perf_counter()
        fila["easyocr"] = easy.leer(img)[0]
        tiempos["easyocr"] += time.perf_counter() - t
        for m, r in fpo.items():
            t = time.perf_counter()
            pred = r.run_one(str(ruta))
            tiempos[m] += time.perf_counter() - t
            texto = getattr(pred, "plate", pred if isinstance(pred, str) else "")
            fila[m + "_crudo"] = normalizar(texto)
            fila[m] = extraer_placa(texto)  # mismas reglas del formato peruano que el OCR actual
        detalle.append(fila)

    grupos = {"autos_todas": detalle, "autos_80px_o_mas": [d for d in detalle if d["ancho_px"] >= 80]}
    claves = ["easyocr"] + [c for m in MODELOS_FPO for c in (m + "_crudo", m)]
    resultados = {g: {k: metricas([(d[k], d["real"]) for d in filas_g]) for k in claves} for g, filas_g in grupos.items()}
    salida = {"modelos": MODELOS_FPO, "ms_por_placa": {k: round(v / len(detalle) * 1000, 1) for k, v in tiempos.items()},
              "resultados": resultados, "detalle": detalle}
    (RAIZ / "evaluacion" / "resultados" / "ocr_comparacion.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    for g, r in resultados.items():
        print(g)
        for k, m in r.items():
            print(f"  {k:<42} exactitud {100 * m['exactitud']:5.1f} %  CER {100 * m['cer']:5.1f} %  sin lectura {100 * m['sin_lectura']:4.0f} %  (n={m['n']})")
    print("ms por placa:", salida["ms_por_placa"])
    for d in detalle:
        print(f"{d['id']:>3} {d['ancho_px']:>4}px real={d['real']:<7} easy={d['easyocr']:<7} " +
              " ".join(f"{m.split('-')[0]}{m.split('-')[2] if 'cct' in m else ''}={d[m + '_crudo']:<8}" for m in MODELOS_FPO))


if __name__ == "__main__":
    main()
