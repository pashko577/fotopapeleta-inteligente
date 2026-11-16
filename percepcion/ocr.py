"""Lectura de placas peruanas: preprocesado, OCR, ajuste al formato y votación entre cuadros.

Las funciones de texto (normalizar, ajustar_formato, votar, cer) son puras y no dependen de
EasyOCR, para poder probarlas sin GPU.
"""
import re
import unicodedata
from collections import defaultdict

import cv2
import numpy as np

PERMITIDOS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
FORMATO = re.compile(r"^[A-Z0-9]{3}\d{3}$")  # sin guion; se muestra como ABC-123

# Confusiones típicas del OCR según lo que se espera en cada posición.
A_DIGITO = str.maketrans({"O": "0", "Q": "0", "D": "0", "U": "0", "I": "1", "L": "1", "T": "1",
                          "Z": "2", "S": "5", "G": "6", "B": "8", "A": "4"})
A_LETRA = str.maketrans({"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "7": "T", "8": "B"})


def normalizar(texto):
    """Mayúsculas, solo letras y dígitos, y sin la palabra PERU de la franja superior."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()  # PERÚ -> PERU
    t = re.sub(r"[^A-Z0-9]", "", sin_tildes.upper())
    return t.replace("PERU", "")


def ajustar_formato(texto):
    """Ajusta una lectura al formato de placa de auto XXX-999 (V8D-001 o ABC-123).

    En ambos formatos las posiciones 1 y 3 son letras y las 4-6 son dígitos; se corrigen
    los caracteres confundibles en esas posiciones (5->S, 0->O... / O->0, S->5, B->8...).
    La posición 2 puede ser letra o dígito y no se toca.
    Devuelve '' si no se puede llevar al formato.
    """
    t = normalizar(texto)
    if len(t) > 6:  # restos de la franja o del marco: quedarse con el bloque final
        t = t[-6:]
    if len(t) != 6:
        return ""
    t = t[0].translate(A_LETRA) + t[1] + t[2].translate(A_LETRA) + t[3:].translate(A_DIGITO)
    return t if FORMATO.match(t) else ""


def _correcciones(v):
    """Cuántos caracteres de una ventana de 6 hay que corregir para que cumpla el formato
    (None si alguno no se puede corregir)."""
    n = 0
    for i, ch in enumerate(v):
        if i in (0, 2):
            ok = ch.isalpha() or ch in "01245678"
            n += ch.isdigit()
        elif i >= 3:
            ok = ch.isdigit() or ch in "OQDUILTZSGBA"
            n += ch.isalpha()
        else:
            ok = True
        if not ok:
            return None
    return n


def extraer_placa(texto_bruto):
    """Saca la placa de una lectura con restos del marco o de la franja.

    1) Si hay un guion con al menos 3 caracteres a cada lado, se toman los 3 anteriores y
       los 3 posteriores (el guion separa los dos bloques de la placa).
    2) Si no, se elige la ventana de 6 caracteres que necesita menos correcciones para
       cumplir el formato; ante empate, se descarta un "I"/"1" inicial (borde del marco).
    Devuelve la placa ajustada al formato o ''.
    """
    sin_tildes = unicodedata.normalize("NFKD", texto_bruto).encode("ascii", "ignore").decode().upper()
    sin_tildes = re.sub(r"PERU?", "", sin_tildes)
    for m in re.finditer(r"-", sin_tildes):
        izq = re.sub(r"[^A-Z0-9]", "", sin_tildes[:m.start()])
        der = re.sub(r"[^A-Z0-9]", "", sin_tildes[m.end():])
        if len(izq) >= 3 and len(der) >= 3:
            placa = ajustar_formato(izq[-3:] + der[:3])
            if placa:
                return placa
    t = re.sub(r"[^A-Z0-9]", "", sin_tildes)
    candidatas = []
    for i in range(0, max(len(t) - 5, 0)):
        v = t[i:i + 6]
        n = _correcciones(v)
        if n is not None:
            candidatas.append((n, i == 0 and len(t) > 6 and v[0] in "I1L", i, v))
    if not candidatas:
        return ""
    return ajustar_formato(min(candidatas)[3])


def zona_texto(recorte, arriba=0.30, abajo=0.95, lados=0.04):
    """Quita la franja 'PERÚ' (cuarto superior de la placa) y los bordes del marco.

    Pensado para recortes del detector con un margen de ~10 % alrededor de la placa.
    EXPERIMENTAL: no se usa en `LectorPlacas.leer` porque empeoró la lectura real.
    """
    h, w = recorte.shape[:2]
    return recorte[int(h * arriba):int(h * abajo), int(w * lados):int(w * (1 - lados))]


def mostrar(placa):
    return f"{placa[:3]}-{placa[3:]}" if len(placa) == 6 else placa


def votar(lecturas):
    """Combina lecturas de varios cuadros de la misma placa.

    `lecturas`: lista de (texto, confianza). Vota carácter por carácter entre las lecturas
    válidas de 6 caracteres, ponderando por confianza. Devuelve (placa, n_validas).
    """
    validas = [(t, c) for t, c in lecturas if len(t) == 6]
    if not validas:
        return "", 0
    placa = ""
    for i in range(6):
        pesos = defaultdict(float)
        for t, c in validas:
            pesos[t[i]] += c
        placa += max(pesos, key=pesos.get)
    return placa, len(validas)


def distancia_edicion(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(predicha, real):
    """Tasa de error por carácter (puede superar 1 si la lectura es muy larga)."""
    return distancia_edicion(predicha, real) / max(len(real), 1)


def preprocesar(recorte, alto_objetivo=64):
    """Escala de grises, ampliación a una altura fija y ecualización local del contraste."""
    gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY) if recorte.ndim == 3 else recorte
    f = alto_objetivo / max(gris.shape[0], 1)
    if f > 1:
        gris = cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gris)


MODELO_PLACAS = "cct-xs-v2-global-model"  # fast-plate-ocr: 86.7 % en 30 placas reales frente a 23.3 % de EasyOCR (docs/pruebas/12)


class LectorPlacas:
    """OCR de placas. Motor por defecto: fast-plate-ocr (modelo entrenado con placas); si no está instalado, EasyOCR.

    motor: "auto" | "fast-plate-ocr" | "easyocr". Las evaluaciones históricas (docs/pruebas/06) fijan "easyocr".
    """

    def __init__(self, gpu=True, motor="auto"):
        self.placas = None
        if motor in ("auto", "fast-plate-ocr"):
            try:
                from fast_plate_ocr import LicensePlateRecognizer
                self.placas = LicensePlateRecognizer(MODELO_PLACAS, device="cpu")  # 3 ms por placa en CPU
                self.motor = f"fast-plate-ocr {MODELO_PLACAS}"
            except ImportError:
                if motor == "fast-plate-ocr":
                    raise
        if self.placas is None:
            import easyocr
            self.lector = easyocr.Reader(["en"], gpu=gpu, verbose=False)
            self.motor = "easyocr 1.7"

    def leer_bruto(self, img):
        """Texto tal como lo devuelve EasyOCR (fragmentos unidos de izquierda a derecha)."""
        res = self.lector.readtext(img, allowlist=PERMITIDOS + "-", detail=1, paragraph=False)
        if not res:
            return "", 0.0
        res.sort(key=lambda r: min(p[0] for p in r[0]))
        return "".join(r[1] for r in res), float(np.mean([r[2] for r in res]))

    def leer(self, recorte):
        """Lectura completa: preprocesado -> OCR -> extracción de la placa.

        No usa `zona_texto`: en la prueba con placas reales empeoró la exactitud (23.3 % -> 6.7 %)
        porque también cortaba parte de los caracteres (ver docs/pruebas/06).
        Devuelve (placa sin guion o '', confianza).
        """
        if self.placas is not None:
            rgb = cv2.cvtColor(recorte, cv2.COLOR_BGR2RGB) if recorte.ndim == 3 else cv2.cvtColor(recorte, cv2.COLOR_GRAY2RGB)
            p = self.placas.run_one(rgb, return_confidence=True)
            conf = float(np.mean(p.char_probs)) if getattr(p, "char_probs", None) is not None and len(p.char_probs) else 0.0
            return extraer_placa(p.plate), conf
        texto, conf = self.leer_bruto(preprocesar(recorte))
        return extraer_placa(texto), conf
