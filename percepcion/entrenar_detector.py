"""Entrena el detector de placas (YOLOv8) y lo evalúa en el split de prueba sin fugas.

Uso:  python -m percepcion.entrenar_detector [--modelo yolov8n.pt] [--epocas 100] [--nombre yolov8n_peru]
Resultados: runs/placas/<nombre>/ (pesos, curvas) y evaluacion/resultados/detector_<nombre>.json
"""
import argparse
import json
from pathlib import Path

import torch
from ultralytics import YOLO

RAIZ = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default=str(RAIZ / "datasets" / "combinado" / "data.yaml"))
    ap.add_argument("--modelo", default="yolov8n.pt")
    ap.add_argument("--epocas", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--nombre", default="yolov8n_peru")
    # En Windows cada worker vuelve a cargar PyTorch (~2-3 GB de memoria virtual);
    # con 4 workers y 16 GB de RAM se agota el archivo de paginación (WinError 1455).
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()

    dispositivo = 0 if torch.cuda.is_available() else "cpu"
    modelo = YOLO(a.modelo)
    modelo.train(data=a.datos, epochs=a.epocas, imgsz=a.imgsz, batch=16, patience=20, seed=42,
                 device=dispositivo, workers=a.workers, project=str(RAIZ / "runs" / "placas"), name=a.nombre,
                 exist_ok=True, plots=True, verbose=False)

    mejor = YOLO(str(RAIZ / "runs" / "placas" / a.nombre / "weights" / "best.pt"))
    resultados = {}
    for split in ("val", "test"):
        m = mejor.val(data=a.datos, split=split, imgsz=a.imgsz, device=dispositivo, verbose=False,
                      project=str(RAIZ / "runs" / "placas"), name=f"{a.nombre}_{split}", exist_ok=True)
        resultados[split] = {"precision": round(float(m.box.mp), 4), "exhaustividad": round(float(m.box.mr), 4),
                             "mAP50": round(float(m.box.map50), 4), "mAP50_95": round(float(m.box.map), 4),
                             "ms_inferencia_por_imagen": round(float(m.speed["inference"]), 2)}
    salida = {"modelo_base": a.modelo, "datos": a.datos, "imgsz": a.imgsz, "epocas_max": a.epocas,
              "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
              "resultados": resultados}
    destino = RAIZ / "evaluacion" / "resultados" / f"detector_{a.nombre}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(salida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
