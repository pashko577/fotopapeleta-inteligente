"""Detecta fotos repetidas entre splits (o entre datasets) para evitar fugas de datos.

Compara por:
  1) nombre de origen (Roboflow nombra las copias aumentadas como <origen>.rf.<hash>.jpg)
  2) parecido visual (dHash de 64 bits; también prueba la versión volteada horizontalmente)

Uso:  python -m percepcion.datos.auditar_duplicados datasets/peru_billy [datasets/otro ...]
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

UMBRAL_BITS = 6  # distancia de Hamming máxima para considerar dos imágenes "la misma foto"


def origen(nombre):
    base = Path(nombre).stem
    base = base.split(".rf.")[0]
    return re.sub(r"_(jpg|jpeg|png)$", "", base, flags=re.I).lower()


def dhash(img, tam=8):
    g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (tam + 1, tam), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hashes(ruta):
    img = cv2.imread(str(ruta))
    if img is None:
        return None
    return dhash(img), dhash(cv2.flip(img, 1))


def recolectar(raices):
    """[(dataset, split, ruta, origen, (h, h_volteado))]"""
    filas = []
    for raiz in raices:
        raiz = Path(raiz)
        for split in ("train", "valid", "test"):
            for ruta in sorted((raiz / split / "images").glob("*")):
                h = hashes(ruta)
                if h:
                    filas.append((raiz.name, split, ruta, origen(ruta.name), h))
    return filas


def distancia(a, b):
    return min(bin(a[0] ^ b[0]).count("1"), bin(a[0] ^ b[1]).count("1"))


def auditar(filas):
    por_origen = defaultdict(set)
    for ds, split, _, org, _ in filas:
        por_origen[(ds, org)].add(split)
    fugas_nombre = {k: v for k, v in por_origen.items() if len(v) > 1}

    evaluacion = [f for f in filas if f[1] in ("valid", "test")]
    entrenamiento = [f for f in filas if f[1] == "train"]
    h_train = np.array([f[4][0] for f in entrenamiento], dtype=np.uint64)
    h_train_v = np.array([f[4][1] for f in entrenamiento], dtype=np.uint64)
    fugas_visual = []
    for ds, split, ruta, _, (h, hv) in evaluacion:
        d1 = np.array([bin(int(x)).count("1") for x in np.bitwise_xor(h_train, np.uint64(h))])
        d2 = np.array([bin(int(x)).count("1") for x in np.bitwise_xor(h_train_v, np.uint64(h))])
        d = np.minimum(d1, d2)
        i = int(d.argmin())
        if d[i] <= UMBRAL_BITS:
            fugas_visual.append((f"{ds}/{split}/{ruta.name}", f"{entrenamiento[i][0]}/train/{entrenamiento[i][2].name}", int(d[i])))
    return fugas_nombre, fugas_visual


def main(raices):
    filas = recolectar(raices)
    conteo = defaultdict(int)
    for ds, split, *_ in filas:
        conteo[(ds, split)] += 1
    origenes = defaultdict(set)
    for ds, split, _, org, _ in filas:
        origenes[(ds, split)].add(org)
    print("Imágenes (fotos de origen distintas):")
    for (ds, split), n in sorted(conteo.items()):
        print(f"  {ds:<20} {split:<6} {n:>5}  ({len(origenes[(ds, split)])} orígenes)")
    fugas_nombre, fugas_visual = auditar(filas)
    print(f"\nOrígenes repartidos en más de un split: {len(fugas_nombre)}")
    for (ds, org), splits in list(fugas_nombre.items())[:10]:
        print(f"  {ds}: {org} -> {sorted(splits)}")
    print(f"Imágenes de valid/test casi idénticas a una de train (<= {UMBRAL_BITS} bits): {len(fugas_visual)}")
    for a, b, d in fugas_visual[:15]:
        print(f"  {a}  ~  {b}  (d={d})")
    return fugas_nombre, fugas_visual


if __name__ == "__main__":
    main(sys.argv[1:])
