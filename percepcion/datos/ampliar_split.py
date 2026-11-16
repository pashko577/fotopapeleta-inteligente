"""Amplía la división sin fugas (datasets/combinado) con las fotos REALMENTE nuevas de otro dataset.

- train, valid y test actuales se copian sin cambios: la prueba de 97 imágenes sigue siendo comparable.
- Del dataset nuevo solo entran las fotos que no repiten ninguna de combinado (mismo origen o dHash <= 6 bits,
  también volteada). Se agrupan entre sí (versiones aumentadas y fotos casi iguales) y cada grupo va a un solo
  destino: test_nuevas (prueba aparte), train o valid.

Uso: python -m percepcion.datos.ampliar_split datasets/combinado datasets/peruvian_plates datasets/combinado_v2
"""
import json
import random
import shutil
import sys
from pathlib import Path

import numpy as np

import cv2

from .auditar_duplicados import UMBRAL_BITS, dhash, origen, recolectar
from .construir_split import agrupar, copiar_imagen, normalizar_etiquetas, popcount64

N_TEST_NUEVAS = 20      # grupos para la segunda prueba
FRACCION_VALID = 0.15   # del resto
SEMILLA = 42


def hashes_sin_bordes(ruta):
    """(dHash, dHash volteado) de la imagen sin las franjas negras del relleno."""
    img = cv2.imread(str(ruta))
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ys, xs = np.nonzero(gris > 12)
    if len(xs):
        img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return dhash(img), dhash(cv2.flip(img, 1))


def main(base, nuevo, salida):
    base, nuevo, salida = Path(base), Path(nuevo), Path(salida)
    if salida.exists():
        shutil.rmtree(salida)
    for split in ("train", "valid", "test"):
        shutil.copytree(base / split, salida / split)

    filas_base = recolectar([base])
    filas_nuevo = [f for f in recolectar([nuevo])]
    # combinado renombró los archivos: el nombre de origen se recupera de su mapa
    mapa_base = json.loads((base / "mapa_archivos.json").read_text(encoding="utf-8"))
    origenes_base = {origen(Path(m["origen"]).name).lower() for m in mapa_base}
    # algunos datasets agregan bordes negros para llevar la foto a 640 x 640: se quitan antes de comparar
    hb = np.array([h for f in filas_base for h in hashes_sin_bordes(f[2])], dtype=np.uint64)
    nuevas = []
    with np.errstate(over="ignore"):
        for f in filas_nuevo:
            if f[3].lower() in origenes_base:
                continue
            d = min(int(popcount64(hb ^ np.uint64(h)).min()) for h in (*f[4], *hashes_sin_bordes(f[2])))
            if d > UMBRAL_BITS:
                nuevas.append(f)
    grupos = agrupar(nuevas)
    rnd = random.Random(SEMILLA)
    rnd.shuffle(grupos)
    n_valid = round((len(grupos) - N_TEST_NUEVAS) * FRACCION_VALID)
    destino = {}
    for k, g in enumerate(grupos):
        split = "test_nuevas" if k < N_TEST_NUEVAS else "valid" if k < N_TEST_NUEVAS + n_valid else "train"
        miembros = g if split == "train" else g[:1]  # en evaluación, una sola imagen por grupo
        for i in miembros:
            destino[i] = (split, k)

    mapa, conteo, sin_etiqueta = [], {}, 0
    for n, (i, (split, k)) in enumerate(sorted(destino.items())):
        _, split_orig, ruta, org, _ = nuevas[i]
        nombre = f"pp_{n:05d}"
        (salida / split / "images").mkdir(parents=True, exist_ok=True)
        (salida / split / "labels").mkdir(parents=True, exist_ok=True)
        copiar_imagen(ruta, salida / split / "images" / (nombre + Path(ruta).suffix.lower()))
        etiqueta = Path(str(ruta).replace(f"{split_orig}\\images", f"{split_orig}\\labels").replace(f"{split_orig}/images", f"{split_orig}/labels")).with_suffix(".txt")
        texto = normalizar_etiquetas(etiqueta.read_text(encoding="utf-8")) if etiqueta.exists() else ""
        sin_etiqueta += not texto
        (salida / split / "labels" / (nombre + ".txt")).write_text(texto, encoding="utf-8")
        mapa.append({"archivo": nombre, "split": split, "grupo": k, "origen": str(Path(ruta).relative_to(nuevo.parent))})
        conteo[split] = conteo.get(split, 0) + 1

    (salida / "mapa_archivos_nuevas.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=1), encoding="utf-8")
    ruta_abs = str(salida.resolve()).replace("\\", "/")
    (salida / "data.yaml").write_text(f"path: {ruta_abs}\ntrain: train/images\nval: valid/images\ntest: test/images\nnc: 1\nnames: ['placa']\n", encoding="utf-8")
    (salida / "data_test_nuevas.yaml").write_text(f"path: {ruta_abs}\ntrain: train/images\nval: test_nuevas/images\ntest: test_nuevas/images\nnc: 1\nnames: ['placa']\n", encoding="utf-8")
    reporte = {"fotos_nuevas": len(nuevas), "grupos": len(grupos), "agregadas_por_split": conteo, "sin_etiqueta": sin_etiqueta,
               "total": {s: len(list((salida / s / "images").glob("*"))) for s in ("train", "valid", "test", "test_nuevas")}}
    (salida / "reporte_ampliacion.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(reporte, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
