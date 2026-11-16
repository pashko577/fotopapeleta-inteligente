"""Verifica que el entorno de percepción funcione: GPU, YOLOv8 y EasyOCR.

Uso:  .venv\\Scripts\\python -m percepcion.verificar_entorno
"""
import time

import cv2
import numpy as np
import torch


def placa_sintetica(texto="ABC-123"):
    """Imagen simple de una placa peruana para probar el OCR."""
    img = np.full((120, 360, 3), 255, np.uint8)
    cv2.rectangle(img, (0, 0), (359, 119), (0, 0, 0), 4)
    cv2.rectangle(img, (4, 4), (355, 28), (216, 78, 29), -1)
    cv2.putText(img, "PERU", (150, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(img, texto, (28, 98), cv2.FONT_HERSHEY_DUPLEX, 2.2, (0, 0, 0), 5)
    return img


def main():
    print(f"PyTorch {torch.__version__} | CUDA disponible: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)} | CUDA {torch.version.cuda}")
        x = torch.randn(4096, 4096, device="cuda")
        (x @ x).sum().item()  # calentamiento: la primera operación inicializa CUDA
        torch.cuda.synchronize(); t = time.perf_counter()
        (x @ x).sum().item()
        print(f"Multiplicación 4096x4096 en GPU: {(time.perf_counter() - t) * 1000:.1f} ms")

    from ultralytics import YOLO
    from ultralytics.utils import ASSETS
    modelo = YOLO("yolov8n.pt")
    dispositivo = 0 if torch.cuda.is_available() else "cpu"
    res = modelo(ASSETS / "bus.jpg", device=dispositivo, verbose=False)[0]
    clases = [res.names[int(c)] for c in res.boxes.cls]
    print(f"YOLOv8n en bus.jpg: {len(clases)} objetos -> {sorted(set(clases))}"
          f" | inferencia {res.speed['inference']:.1f} ms")

    import easyocr
    lector = easyocr.Reader(["en"], gpu=torch.cuda.is_available(), verbose=False)
    lecturas = lector.readtext(placa_sintetica(), allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
    print("EasyOCR sobre placa sintética:", [(t, round(float(c), 2)) for _, t, c in lecturas])


if __name__ == "__main__":
    main()
