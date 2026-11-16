"""Decisión ante un evento nuevo: ¿hay infracción de velocidad o una captura imposible?

Es lo que hace el sistema cada vez que una cámara reporta una placa. Función pura: la usan
la API de Django y la demo, sin depender de ninguna de las dos.
"""
from .evidencia import V_MAX_PLAUSIBLE_KMH, capturas_coherentes, misma_placa, velocidad_implicita
from .heuristicas import recta_km
from .velocidad import velocidad_por_tramo


def evaluar_evento(grafo, nodos, evento, capturas_previas, k=2, v_max_kmh=V_MAX_PLAUSIBLE_KMH,
                   **opciones_velocidad):
    """Compara un evento con las capturas previas de la misma placa.

    `evento` y cada captura: dict con placa, camara, ts (datetime) y un identificador `id`.
    Devuelve dict con tres listas:
      infracciones   : tramo desde la captura más cercana en el tiempo, por encima del límite + tolerancia
      sin_infraccion : tramos dentro del límite
      alertas        : misma placa en otra cámara en un tiempo físicamente imposible
                       (haría falta ir a más de v_max_kmh por la ruta más corta)
    """
    h = recta_km(nodos)
    aceptadas = capturas_coherentes(grafo, evento, capturas_previas, k=k, v_max_kmh=v_max_kmh)
    ids_ok = {c["id"] for c, _ in aceptadas}
    resultado = {"infracciones": [], "sin_infraccion": [], "alertas": []}

    for c in capturas_previas:
        if c["id"] in ids_ok or c["camara"] == evento["camara"]:
            continue
        coincidencia = misma_placa(c["placa"], evento["placa"])
        if coincidencia is None:
            continue
        km, v = velocidad_implicita(grafo, c["camara"], c["ts"], evento["camara"], evento["ts"])
        if km == float("inf") or v <= v_max_kmh:
            continue  # sin conexión en la red, o posible pero fuera del vecindario k: nada que alertar
        observado = abs((evento["ts"] - c["ts"]).total_seconds()) / 60
        resultado["alertas"].append({
            "tipo": "captura_imposible", "placa": evento["placa"], "coincidencia": coincidencia,
            "captura_anterior": c["id"], "captura_actual": evento["id"],
            "de": c["camara"], "a": evento["camara"], "km_minimos": km,
            "minutos_observados": round(observado, 2), "velocidad_necesaria_kmh": round(v, 1),
            "velocidad_maxima_plausible_kmh": v_max_kmh, "minimo_plausible_min": round(km / v_max_kmh * 60, 2),
            "motivo": "Captura físicamente imposible: posible placa clonada o error de lectura"})

    # Solo la captura más cercana en el tiempo: con A -> B -> C se evalúan A-B y luego B-C, nunca A-C,
    # que repetiría un recorrido ya evaluado (control por tramos consecutivos).
    aceptadas = sorted(aceptadas, key=lambda x: abs((evento["ts"] - x[0]["ts"]).total_seconds()))[:1]
    for c, coincidencia in aceptadas:
        anterior, actual = sorted((c, evento), key=lambda x: x["ts"])
        v = velocidad_por_tramo(grafo, anterior["camara"], anterior["ts"], actual["camara"], actual["ts"], h,
                                **opciones_velocidad)
        if v is None:
            continue
        fila = {"placa": evento["placa"], "coincidencia": coincidencia,
                "captura_anterior": anterior["id"], "captura_actual": actual["id"],
                "ruta": v.ruta, "km": v.km, "segundos": (actual["ts"] - anterior["ts"]).total_seconds(),
                "v_medida": v.v_medida, "v_conservadora": v.v_conservadora,
                "limite": v.limite, "exceso": v.exceso}
        resultado["infracciones" if v.infraccion else "sin_infraccion"].append(fila)
    return resultado
