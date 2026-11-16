"""Placas peruanas sintéticas con texto conocido, para medir el OCR.

Formatos: 70 % letra-dígito-letra (V8D-001, A2X-506) y 30 % tres letras (ABC-123).
Niveles de degradación que imitan una placa recortada por el detector:
  facil   : placa cercana y nítida (160-220 px de ancho)
  media   : distancia media, algo de desenfoque y rotación (70-110 px)
  dificil : lejos o con poca luz, movimiento y compresión (55-80 px); difícil pero legible
            para una persona (una versión de 40-60 px resultó ilegible incluso a simple vista)
"""
import random
import string

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FUENTES = ["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/verdanab.ttf"]
LETRAS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # sin I, O, Q (no se usan en placas)

NIVELES = {
    "facil":   dict(ancho=(160, 220), rot=3,  sigma=(0.0, 0.6), mov=(0, 0), ruido=3,  luz=(0.9, 1.1), jpeg=85),
    "media":   dict(ancho=(70, 110),  rot=8,  sigma=(0.5, 1.2), mov=(0, 5), ruido=6,  luz=(0.6, 1.0), jpeg=60),
    "dificil": dict(ancho=(55, 80),   rot=12, sigma=(0.8, 1.3), mov=(2, 5), ruido=8,  luz=(0.45, 0.7), jpeg=45),
}


def texto_aleatorio(rnd):
    if rnd.random() < 0.7:
        inicio = rnd.choice(LETRAS) + rnd.choice(string.digits) + rnd.choice(LETRAS)
    else:
        inicio = "".join(rnd.choice(LETRAS) for _ in range(3))
    return inicio + "".join(rnd.choice(string.digits) for _ in range(3))


def renderizar(placa, fuente):
    """Placa limpia de 440x220 px (proporción real 2:1) en BGR."""
    W, H = 440, 220
    img = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([3, 3, W - 4, H - 4], radius=14, outline=(20, 20, 20), width=7)
    d.rectangle([10, 10, W - 11, 52], fill=(29, 78, 216))
    f_band = ImageFont.truetype(fuente, 30)
    d.text((W / 2, 31), "PERÚ", font=f_band, fill=(255, 255, 255), anchor="mm")
    texto = f"{placa[:3]}-{placa[3:]}"
    tam = 118
    while tam > 40:  # reducir hasta que el texto quepa con margen dentro del marco
        f = ImageFont.truetype(fuente, tam)
        x0, _, x1, _ = d.textbbox((0, 0), texto, font=f)
        if x1 - x0 <= W - 50:
            break
        tam -= 4
    d.text((W / 2, 140), texto, font=f, fill=(15, 15, 15), anchor="mm")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def degradar(limpia, nivel, rnd):
    p = NIVELES[nivel]
    img = limpia.copy()
    h, w = img.shape[:2]
    # Margen gris (como el recorte del detector, que incluye algo del auto) y rotación/perspectiva
    img = cv2.copyMakeBorder(img, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=(90, 90, 90))
    H, W = img.shape[:2]
    ang = rnd.uniform(-p["rot"], p["rot"])
    M = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0)
    img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REPLICATE)
    d = p["rot"] * 1.5
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    dst = src + np.float32([[rnd.uniform(-d, d), rnd.uniform(-d, d)] for _ in range(4)])
    img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (W, H), borderMode=cv2.BORDER_REPLICATE)
    img = img[22:H - 22, 22:W - 22]
    # Tamaño final (distancia a la cámara)
    ancho = rnd.randint(*p["ancho"])
    img = cv2.resize(img, (ancho, round(ancho * img.shape[0] / img.shape[1])), interpolation=cv2.INTER_AREA)
    # Desenfoque y movimiento
    s = rnd.uniform(*p["sigma"])
    if s > 0.05:
        img = cv2.GaussianBlur(img, (0, 0), s)
    largo = rnd.randint(*p["mov"])
    if largo > 1:
        k = np.zeros((largo, largo), np.float32)
        k[largo // 2, :] = 1 / largo
        img = cv2.filter2D(img, -1, k)
    # Iluminación y ruido
    img = np.clip(img.astype(np.float32) * rnd.uniform(*p["luz"]) + np.random.default_rng(rnd.randint(0, 1 << 30)).normal(0, p["ruido"], img.shape), 0, 255).astype(np.uint8)
    # Compresión JPEG
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, p["jpeg"]])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)
