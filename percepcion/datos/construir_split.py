"""Une uno o más datasets YOLO y crea una división train/valid/test SIN fugas.

Agrupa en un mismo "grupo" las imágenes que son la misma foto (mismo origen en Roboflow)
o casi idénticas (copias, cuadros consecutivos de una ráfaga), y asigna cada grupo
completo a un solo split. En valid/test se deja una sola imagen por grupo.

Uso:
  python -m percepcion.datos.construir_split datasets/combinado datasets/peru_billy [datasets/otro ...]
Escribe <salida>/{train,valid,test}/{images,labels}, data.yaml y reporte_split.json
"""
import json
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from .auditar_duplicados import UMBRAL_BITS, recolectar

PROPORCION = {"train": 0.75, "valid": 0.15, "test": 0.10}
SEMILLA = 42
LADO_MAX = 1280  # las fotos de 4000x3000 se reducen; las etiquetas YOLO son relativas y no cambian


def normalizar_etiquetas(texto):
    """Una sola clase (0) y siempre cajas.

    Convierte polígonos (formato de segmentación: clase x1 y1 x2 y2 ...) en la caja que los
    encierra, y unifica clases equivalentes como 'Placa' y 'placa'.
    """
    salida = []
    for linea in texto.splitlines():
        v = linea.split()
        if len(v) < 5:
            continue
        coords = [min(max(float(x), 0.0), 1.0) for x in v[1:]]
        if len(coords) == 4:
            cx, cy, w, h = coords
        else:
            xs, ys = coords[0::2], coords[1::2]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            w, h = max(xs) - min(xs), max(ys) - min(ys)
        if w > 0 and h > 0:
            salida.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    return "\n".join(salida) + ("\n" if salida else "")


def copiar_imagen(src, dst):
    img = cv2.imread(str(src))
    alto, ancho = img.shape[:2]
    if max(alto, ancho) > LADO_MAX:
        f = LADO_MAX / max(alto, ancho)
        img = cv2.resize(img, (round(ancho * f), round(alto * f)), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(dst.with_suffix(".jpg")), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    else:
        shutil.copy2(src, dst)


class UnionFind:
    def __init__(self, n):
        self.p = list(range(n))

    def buscar(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def unir(self, a, b):
        self.p[self.buscar(a)] = self.buscar(b)


def popcount64(x):
    x = x - ((x >> np.uint64(1)) & np.uint64(0x5555555555555555))
    x = (x & np.uint64(0x3333333333333333)) + ((x >> np.uint64(2)) & np.uint64(0x3333333333333333))
    x = (x + (x >> np.uint64(4))) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return (x * np.uint64(0x0101010101010101)) >> np.uint64(56)


def agrupar(filas):
    uf = UnionFind(len(filas))
    primero = {}
    for i, (ds, _, _, org, _) in enumerate(filas):
        if (ds, org) in primero:
            uf.unir(i, primero[(ds, org)])
        else:
            primero[(ds, org)] = i
    h = np.array([f[4][0] for f in filas], dtype=np.uint64)
    hv = np.array([f[4][1] for f in filas], dtype=np.uint64)
    with np.errstate(over="ignore"):
        for i in range(len(filas)):
            d = np.minimum(popcount64(h[i + 1:] ^ h[i]), popcount64(hv[i + 1:] ^ h[i]))
            for j in np.nonzero(d <= UMBRAL_BITS)[0]:
                uf.unir(i, i + 1 + int(j))
    grupos = defaultdict(list)
    for i in range(len(filas)):
        grupos[uf.buscar(i)].append(i)
    return list(grupos.values())


def main(salida, raices):
    salida = Path(salida)
    filas = recolectar(raices)
    grupos = agrupar(filas)
    asignacion = {}
    for ds in sorted({f[0] for f in filas}):  # estratificado por dataset de origen
        gs = [g for g in grupos if filas[g[0]][0] == ds]
        # Semilla propia por dataset: agregar otro dataset no cambia la división de los anteriores.
        random.Random(SEMILLA).shuffle(gs)
        total = sum(len({filas[i][3] for i in g}) for g in gs)
        acumulado = 0
        for g in gs:
            frac = acumulado / total
            split = "test" if frac < PROPORCION["test"] else "valid" if frac < PROPORCION["test"] + PROPORCION["valid"] else "train"
            asignacion[id(g)] = split
            acumulado += len({filas[i][3] for i in g})

    if salida.exists():
        shutil.rmtree(salida)
    conteo = defaultdict(lambda: defaultdict(int))
    mapa = []  # nombre corto -> archivo original (los nombres de Roboflow superan MAX_PATH en Windows)
    for s in PROPORCION:
        for sub in ("images", "labels"):
            (salida / s / sub).mkdir(parents=True, exist_ok=True)
    for gi, g in enumerate(grupos):
        split = asignacion[id(g)]
        miembros = g if split == "train" else g[:1]  # en evaluación, una imagen por grupo
        for i in miembros:
            ds, split_orig, ruta, _, _ = filas[i]
            corto = f"{ds}_{i:05d}"
            etiqueta = ruta.parent.parent / "labels" / (ruta.stem + ".txt")
            copiar_imagen(ruta, salida / split / "images" / (corto + ruta.suffix.lower()))
            texto = etiqueta.read_text(encoding="utf-8") if etiqueta.exists() else ""
            (salida / split / "labels" / (corto + ".txt")).write_text(normalizar_etiquetas(texto), encoding="utf-8")
            mapa.append({"archivo": corto, "split": split, "grupo": gi,
                         "origen": f"{ds}/{split_orig}/{ruta.name}"})
            conteo[split][ds] += 1
    (salida / "mapa_archivos.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=1), encoding="utf-8")

    (salida / "data.yaml").write_text(
        f"path: {salida.resolve().as_posix()}\ntrain: train/images\nval: valid/images\ntest: test/images\nnc: 1\nnames: ['placa']\n",
        encoding="utf-8")
    reporte = {
        "datasets": [Path(r).name for r in raices],
        "imagenes_entrada": len(filas),
        "grupos_sin_fuga": len(grupos),
        "grupos_con_mas_de_una_foto_de_origen": sum(1 for g in grupos if len({filas[i][3] for i in g}) > 1),
        "umbral_dhash_bits": UMBRAL_BITS,
        "semilla": SEMILLA,
        "imagenes_por_split": {s: dict(v) | {"total": sum(v.values())} for s, v in conteo.items()},
    }
    (salida / "reporte_split.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
