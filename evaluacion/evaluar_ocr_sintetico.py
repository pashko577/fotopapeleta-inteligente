"""Experimento 06: OCR de placas peruanas sintéticas, con y sin votación entre cuadros.

Para cada nivel (fácil, media, difícil) genera N placas y 9 "cuadros" degradados de forma
independiente por placa (como un video). Compara tres variantes acumulativas:
  crudo       : EasyOCR sobre el recorte, solo normalizar texto
  preproceso  : + escala de grises, ampliación y CLAHE
  formato     : + ajuste al formato peruano (posiciones 1 y 3 letras, 4-6 dígitos)
  extraccion  : + guion como ancla y mejor ventana de 6 caracteres
  completo    : + lectura solo de la zona del texto (sin franja PERÚ ni bordes)
y mide CER y exactitud de placa completa con 1 cuadro y votando entre 3, 5 y 9.

Uso:  python -m evaluacion.evaluar_ocr_sintetico [--placas 100]
"""
import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path

import torch

from percepcion.datos.placas_sinteticas import FUENTES, NIVELES, degradar, renderizar, texto_aleatorio
from percepcion.ocr import (LectorPlacas, ajustar_formato, cer, extraer_placa, normalizar, preprocesar,
                            votar, zona_texto)

RAIZ = Path(__file__).resolve().parents[1]
CUADROS = 9
VARIANTES = ("crudo", "preproceso", "formato", "extraccion", "completo")


def leer(lector, img):
    res = lector.lector.readtext(img, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-", detail=1)
    if not res:
        return "", 0.0
    res.sort(key=lambda r: min(p[0] for p in r[0]))
    return "".join(r[1] for r in res), sum(r[2] for r in res) / len(res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placas", type=int, default=100)
    ap.add_argument("--semilla", type=int, default=7)
    a = ap.parse_args()

    lector = LectorPlacas(gpu=torch.cuda.is_available(), motor="easyocr")
    rnd = random.Random(a.semilla)
    registros = []  # una fila por placa y nivel con las lecturas de cada cuadro
    t0 = time.perf_counter()
    for nivel in NIVELES:
        for _ in range(a.placas):
            real = texto_aleatorio(rnd)
            limpia = renderizar(real, rnd.choice(FUENTES))
            lecturas = {v: [] for v in VARIANTES}
            for _ in range(CUADROS):
                img = degradar(limpia, nivel, rnd)
                t_crudo, c_crudo = leer(lector, img)
                t_pre, c_pre = leer(lector, preprocesar(img))
                lecturas["crudo"].append((normalizar(t_crudo), c_crudo))
                lecturas["preproceso"].append((normalizar(t_pre), c_pre))
                lecturas["formato"].append((ajustar_formato(t_pre), c_pre))
                lecturas["extraccion"].append((extraer_placa(t_pre), c_pre))
                t_zona, c_zona = leer(lector, preprocesar(zona_texto(img)))
                lecturas["completo"].append((extraer_placa(t_zona), c_zona))
            registros.append({"nivel": nivel, "real": real, "lecturas": lecturas})
        print(f"{nivel}: listo ({time.perf_counter() - t0:.0f} s)", flush=True)

    resultados = {}
    confusiones = Counter()
    for nivel in NIVELES:
        filas = [r for r in registros if r["nivel"] == nivel]
        resultados[nivel] = {}
        for v in VARIANTES:
            un_cuadro = [(t, r["real"]) for r in filas for t, _ in r["lecturas"][v]]
            m = {"1": {"cer": sum(cer(t, real) for t, real in un_cuadro) / len(un_cuadro),
                       "exactitud": sum(t == real for t, real in un_cuadro) / len(un_cuadro),
                       "sin_lectura": sum(t == "" for t, _ in un_cuadro) / len(un_cuadro)}}
            for k in (3, 5, 9):
                votadas = [(votar(r["lecturas"][v][:k])[0], r["real"]) for r in filas]
                m[str(k)] = {"cer": sum(cer(t, real) for t, real in votadas) / len(votadas),
                             "exactitud": sum(t == real for t, real in votadas) / len(votadas),
                             "sin_lectura": sum(t == "" for t, _ in votadas) / len(votadas)}
            resultados[nivel][v] = {k: {kk: round(vv, 4) for kk, vv in d.items()} for k, d in m.items()}
        for r in filas:  # confusiones de carácter de la variante completa, cuadro a cuadro
            for t, _ in r["lecturas"]["completo"]:
                if len(t) == 6:
                    confusiones.update(f"{a_}→{b_}" for a_, b_ in zip(r["real"], t) if a_ != b_)

    salida = {"placas_por_nivel": a.placas, "cuadros_por_placa": CUADROS, "semilla": a.semilla,
              "lecturas_ocr": len(registros) * CUADROS * 3, "segundos": round(time.perf_counter() - t0, 1),
              "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
              "resultados": resultados, "confusiones_frecuentes": confusiones.most_common(15)}
    destino = RAIZ / "evaluacion" / "resultados" / "ocr_sintetico.json"
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(salida, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
