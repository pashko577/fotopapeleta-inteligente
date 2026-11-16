"""Puente entre la BD y el paquete grafo/ (que no conoce Django)."""
import hashlib
import json

from django.db import transaction

import grafo

from .models import Camara, Tramo


def datos_red():
    """La red en el formato JSON que entiende grafo.construir()."""
    nodos = {}
    for c in Camara.objects.filter(activa=True):
        n = {"nombre": c.nombre}
        if c.x_km is not None and c.y_km is not None:
            n.update(x_km=c.x_km, y_km=c.y_km)
        elif c.lat is not None and c.lon is not None:
            n.update(lat=c.lat, lon=c.lon)
        nodos[c.codigo] = n
    aristas = [{"de": t.origen_id, "a": t.destino_id, "km": t.km, "min": t.minutos,
                "limite_kmh": t.limite_kmh, "dirigida": t.dirigida}
               for t in Tramo.objects.filter(origen__activa=True, destino__activa=True)]
    return {"nodos": nodos, "aristas": aristas}


def version_red(datos):
    """Huella corta del contenido de la red: cada infracción guarda con qué versión se analizó."""
    texto = json.dumps(datos, sort_keys=True)
    return hashlib.sha256(texto.encode()).hexdigest()[:12]


def construir_grafo():
    """(grafo, nodos, version) listos para grafo.evaluar_evento()."""
    datos = datos_red()
    errores = grafo.validar(datos)
    if errores:
        raise ValueError("La red de cámaras es inválida: " + "; ".join(errores))
    return grafo.construir(datos), datos["nodos"], version_red(datos)


@transaction.atomic
def importar_red(datos):
    """Crea o actualiza cámaras y tramos desde el JSON de data/grafo_camaras.json."""
    errores = grafo.validar(datos)
    if errores:
        raise ValueError("; ".join(errores))
    for codigo, n in datos["nodos"].items():
        Camara.objects.update_or_create(codigo=codigo, defaults={
            "nombre": n.get("nombre", codigo), "x_km": n.get("x_km"), "y_km": n.get("y_km"),
            "lat": n.get("lat"), "lon": n.get("lon")})
    vigentes = []
    for a in datos["aristas"]:
        t, _ = Tramo.objects.update_or_create(origen_id=a["de"], destino_id=a["a"], defaults={
            "km": a["km"], "minutos": a["min"], "limite_kmh": a.get("limite_kmh") or 60,
            "dirigida": a.get("dirigida", False), "fuente": a.get("fuente", "manual"), "geometria": a.get("geometria", [])})
        vigentes.append(t.pk)
    # La red importada reemplaza a la anterior: un tramo que ya no está en el archivo deja de existir
    # (las infracciones ya analizadas conservan su ruta, sus km y la versión del grafo con que se decidieron).
    Tramo.objects.exclude(pk__in=vigentes).delete()
    return len(datos["nodos"]), len(datos["aristas"])
