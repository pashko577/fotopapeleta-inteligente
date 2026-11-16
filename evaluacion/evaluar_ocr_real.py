"""Experimento 06b: OCR sobre placas reales recortadas por el detector (un solo cuadro).

Usa la transcripción manual de evaluacion/resultados/ocr_real_transcripcion.csv. Solo se
evalúan las placas de auto legibles (categoría 'auto'); motos y placas especiales se reportan
aparte porque tienen otro formato.

Uso:  python -m evaluacion.evaluar_ocr_real
"""
import csv
import json
from pathlib import Path

import cv2
import torch

from percepcion.ocr import LectorPlacas, ajustar_formato, cer, extraer_placa, normalizar, preprocesar, zona_texto

RAIZ = Path(__file__).resolve().parents[1]
RECORTES = RAIZ / "datasets" / "ocr_real" / "recortes"


def leer(lector, img):
    res = lector.lector.readtext(img, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-", detail=1)
    if not res:
        return "", 0.0
    res.sort(key=lambda r: min(p[0] for p in r[0]))
    return "".join(r[1] for r in res), sum(r[2] for r in res) / len(res)


def metricas(pares):
    n = len(pares)
    return {"n": n, "cer": round(sum(cer(p, r) for p, r in pares) / n, 4),
            "exactitud": round(sum(p == r for p, r in pares) / n, 4),
            "sin_lectura": round(sum(p == "" for p, _ in pares) / n, 4)}


def main():
    filas = list(csv.DictReader(open(RAIZ / "evaluacion" / "resultados" / "ocr_real_transcripcion.csv", encoding="utf-8")))
    lector = LectorPlacas(gpu=torch.cuda.is_available(), motor="easyocr")
    detalle = []
    for f in filas:
        if f["categoria"] not in ("auto", "moto"):
            continue
        img = cv2.imread(str(RECORTES / f["recorte"]))
        t_crudo, _ = leer(lector, img)
        t_pre, conf = leer(lector, preprocesar(img))
        t_zona, conf_zona = leer(lector, preprocesar(zona_texto(img)))
        detalle.append({"id": f["id"], "categoria": f["categoria"], "certeza": f["certeza"], "ancho_px": int(f["ancho_px"]),
                        "real": f["texto_real"], "crudo": normalizar(t_crudo), "preproceso": normalizar(t_pre),
                        "formato": ajustar_formato(t_pre), "extraccion": extraer_placa(t_pre),
                        "completo": extraer_placa(t_zona), "lectura_bruta": t_pre, "lectura_bruta_zona": t_zona,
                        "conf": round(conf_zona, 3)})

    autos = [d for d in detalle if d["categoria"] == "auto"]
    resultados = {}
    for nombre, grupo in (("autos_todas", autos), ("autos_certeza_alta", [d for d in autos if d["certeza"] == "alta"]),
                          ("autos_ancho_80px_o_mas", [d for d in autos if d["ancho_px"] >= 80])):
        resultados[nombre] = {v: metricas([(d[v], d["real"]) for d in grupo]) for v in ("crudo", "preproceso", "formato", "extraccion", "completo")}
    salida = {"gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
              "resultados": resultados, "detalle": detalle}
    destino = RAIZ / "evaluacion" / "resultados" / "ocr_real.json"
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    for nombre, r in resultados.items():
        print(nombre, {v: (m["n"], f"CER {100*m['cer']:.1f}%", f"exact {100*m['exactitud']:.1f}%") for v, m in r.items()})
    for d in detalle:
        print(f"{d['id']:>3} {d['categoria']:<5} {d['ancho_px']:>4}px real={d['real']:<7} formato={d['formato']:<7} completo={d['completo']:<7} bruto={d['lectura_bruta']:<12} zona={d['lectura_bruta_zona']}")


if __name__ == "__main__":
    main()
