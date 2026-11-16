# 02 · Entorno de ML

## Objetivo
Confirmar que la PC del equipo puede entrenar y ejecutar los modelos de percepción en GPU.

## Instalación
Entorno virtual `.venv` en la raíz del proyecto (no se versiona).

| Paquete | Versión | Nota |
|---|---|---|
| Python | 3.12.10 | — |
| PyTorch | 2.11.0+cu128 | Debe instalarse desde el índice de CUDA 12.8; la versión de PyPI no reconoce la RTX 5070 |
| torchvision | 0.26.0+cu128 | — |
| Ultralytics | 8.4.177 | YOLOv8 |
| EasyOCR | 1.7.2 | — |
| OpenCV | 5.0.0.93 | — |
| NetworkX | 3.7 | Igual a la versión citada en el paper |

Versiones fijadas en [`requirements-ml.txt`](../../requirements-ml.txt).

## Prueba: `python -m percepcion.verificar_entorno`

| Verificación | Resultado |
|---|---|
| PyTorch detecta CUDA | Sí: NVIDIA GeForce RTX 5070, CUDA 12.8 |
| Multiplicación de matrices 4096 × 4096 en GPU | 7.6 ms (tras calentamiento) |
| YOLOv8n preentrenado (COCO) sobre `bus.jpg` | 6 objetos: `bus`, `person`, `stop sign`; 7.9 ms |
| EasyOCR sobre placa sintética "ABC-123" | Lee `PERU` y `ABC-123` con confianza 1.0 |

## Observaciones
- La primera medición de la GPU dio 220 ms porque incluía la inicialización de CUDA. El script ahora hace una operación de calentamiento antes de medir.
- La placa sintética es perfecta (fondo blanco, tipografía limpia). No representa la dificultad de una placa real; solo confirma que el OCR funciona.
