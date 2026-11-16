import pytest

from percepcion.ocr import ajustar_formato, cer, extraer_placa, mostrar, normalizar, votar, zona_texto


@pytest.mark.parametrize("entrada, esperado", [
    ("ABC-123", "ABC123"),
    ("PERU ABC-123", "ABC123"),
    ("abc 123", "ABC123"),
    ("V8D-OO1", "V8D001"),   # O en la parte numérica -> 0
    ("A2X-5O6", "A2X506"),
    ("C2N-34B", "C2N348"),   # B -> 8
    ("XPERUV8D001", "V8D001"),
    ("AB-12", ""),            # demasiado corta
])
def test_ajustar_formato(entrada, esperado):
    assert ajustar_formato(entrada) == esperado


def test_no_toca_la_posicion_2():
    assert ajustar_formato("BOS-123") == "BOS123"
    assert ajustar_formato("V8D-123") == "V8D123"


@pytest.mark.parametrize("entrada, esperado", [
    ("53J-646", "S3J646"),   # posición 1: 5 -> S
    ("57J-488", "S7J488"),
    ("A2X-5O6", "A2X506"),
    ("A25-506", "A2S506"),   # posición 3: 5 -> S
])
def test_corrige_posiciones_1_y_3(entrada, esperado):
    assert ajustar_formato(entrada) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("T5S-4571PER", "T5S457"),   # restos de la franja después del texto
    ("T3P-2981", "T3P298"),      # el guion ancla los dos bloques
    ("D9R-052-", "D9R052"),
    ("IBPO306", "BPO306"),       # borde izquierdo leído como I
    ("ICHO-Q02", "CHO002"),
    ("V8D-O01", "V8D001"),
    ("PERU V8D001", "V8D001"),
    ("AB12", ""),
])
def test_extraer_placa(bruto, esperado):
    assert extraer_placa(bruto) == esperado


def test_zona_texto_quita_franja_y_bordes():
    import numpy as np
    img = np.zeros((100, 200, 3), np.uint8)
    assert zona_texto(img).shape[:2] == (65, 184)


def test_normalizar_quita_franja():
    assert normalizar("PERÚ  T3P-298") == "T3P298"


def test_votar_corrige_un_caracter_minoritario():
    lecturas = [("V8D001", 0.9), ("V8D001", 0.8), ("VBD001", 0.6), ("", 0.0)]
    assert votar(lecturas) == ("V8D001", 3)


def test_votar_pondera_por_confianza():
    assert votar([("ABC123", 0.95), ("ABC128", 0.3), ("ABC128", 0.3)])[0] == "ABC123"


def test_votar_sin_lecturas_validas():
    assert votar([("", 0.0), ("AB12", 0.5)]) == ("", 0)


def test_cer():
    assert cer("ABC123", "ABC123") == 0
    assert cer("ABC128", "ABC123") == pytest.approx(1 / 6)
    assert cer("", "ABC123") == 1


def test_mostrar():
    assert mostrar("ABC123") == "ABC-123"
