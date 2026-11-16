"""Recorta las placas que detecta el modelo entrenado en las imágenes de prueba (sin fugas).

Los recortes sirven para medir el OCR en placas reales: cada uno se transcribe a mano en
evaluacion/resultados/ocr_real_transcripcion.csv (columna `texto_real`; 'ILEGIBLE' si no se lee).

Uso:  python -m evaluacion.recortar_placas_reales
"""
import csv
from pathlib import Path

import cv2
from ultralytics import YOLO

RAIZ = Path(__file__).resolve().parents[1]
MODELO = RAIZ / "runs" / "placas" / "yolov8n_peru" / "weights" / "best.pt"
PRUEBA = RAIZ / "datasets" / "combinado" / "test" / "images"
SALIDA = RAIZ / "datasets" / "ocr_real" / "recortes"
CONF_MIN = 0.5
MARGEN = 0.10


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    modelo = YOLO(str(MODELO))
    filas = []
    for ruta in sorted(PRUEBA.glob("*")):
        img = cv2.imread(str(ruta))
        res = modelo(img, conf=CONF_MIN, verbose=False)[0]
        for k, (caja, conf) in enumerate(zip(res.boxes.xyxy.tolist(), res.boxes.conf.tolist())):
            x1, y1, x2, y2 = caja
            mx, my = (x2 - x1) * MARGEN, (y2 - y1) * MARGEN
            x1, y1 = max(int(x1 - mx), 0), max(int(y1 - my), 0)
            x2, y2 = min(int(x2 + mx), img.shape[1]), min(int(y2 + my), img.shape[0])
            nombre = f"{ruta.stem}_p{k}.png"
            cv2.imwrite(str(SALIDA / nombre), img[y1:y2, x1:x2])
            filas.append({"recorte": nombre, "ancho_px": x2 - x1, "alto_px": y2 - y1,
                          "conf_detector": round(conf, 3), "texto_real": ""})
    destino = RAIZ / "evaluacion" / "resultados" / "ocr_real_recortes.csv"
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} recortes en {SALIDA}")


if __name__ == "__main__":
    main()
