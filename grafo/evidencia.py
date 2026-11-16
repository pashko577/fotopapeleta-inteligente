"""Vinculación de capturas entre cámaras: coincidencia de placa y filtro temporal."""
from .busqueda import a_estrella, bfs

# Caracteres que el OCR suele confundir, llevados a una forma común.
_CONFUSIONES = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1",
                              "B": "8", "S": "5", "Z": "2", "G": "6"})


def normalizar(placa):
    return placa.upper().replace("-", "").replace(" ", "")


def clave(placa):
    """Forma de la placa sin caracteres confundibles; se indexa en la BD como placa_clave."""
    return normalizar(placa).translate(_CONFUSIONES)


def _un_caracter_distinto(a, b):
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1


def misma_placa(a, b):
    """'confirmada', 'a_verificar' o None.

    'a_verificar' si difieren solo en caracteres confundibles (B/8, O/0...) o en UN solo
    carácter cualquiera (error típico del OCR entre cámaras con distinta luz). Esas
    coincidencias nunca se emiten sin revisión humana y pasan además por el filtro temporal.
    """
    na, nb = normalizar(a), normalizar(b)
    if na == nb:
        return "confirmada"
    if clave(a) == clave(b) or _un_caracter_distinto(na, nb):
        return "a_verificar"
    return None


V_MAX_PLAUSIBLE_KMH = 200  # ningún vehículo recorre la ciudad más rápido que esto


def velocidad_implicita(grafo, cam_a, ts_a, cam_b, ts_b):
    """(km mínimos entre las cámaras, km/h necesarios para cubrirlos en el tiempo observado)."""
    km = a_estrella(grafo, cam_a, cam_b, peso="km").costo
    horas = abs((ts_b - ts_a).total_seconds()) / 3600
    return km, (float("inf") if horas == 0 else km / horas)


def capturas_coherentes(grafo, evento, capturas, k=2, v_max_kmh=V_MAX_PLAUSIBLE_KMH):
    """Capturas de la misma placa en cámaras cercanas cuyo tiempo es físicamente posible.

    `evento` y cada captura son dicts con: placa, camara, ts (datetime).
    Una captura se acepta si, para recorrer la distancia mínima (A* en km) en el tiempo
    observado, bastaría una velocidad <= v_max_kmh. Así un auto muy rápido (p. ej. 100 km/h
    en zona de 60) se evalúa como posible infracción, y solo lo irreal (> 200 km/h) se trata
    como captura imposible (placa clonada o error de lectura).
    Devuelve [(captura, 'confirmada'|'a_verificar'), ...].
    """
    candidatas = bfs(grafo, evento["camara"], k)
    aceptadas = []
    for c in capturas:
        if c["camara"] == evento["camara"] or c["camara"] not in candidatas:
            continue
        coincidencia = misma_placa(evento["placa"], c["placa"])
        if coincidencia is None:
            continue
        _, v = velocidad_implicita(grafo, c["camara"], c["ts"], evento["camara"], evento["ts"])
        if v <= v_max_kmh:
            aceptadas.append((c, coincidencia))
    return aceptadas
