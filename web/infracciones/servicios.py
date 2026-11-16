"""Registro de eventos y decisión: lo que pasa cuando el worker reporta una placa."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

import grafo
from camaras.servicios import construir_grafo
from panel.models import parametros

from .models import Alerta, AnalisisGrafo, Captura, Evidencia, Infraccion

VENTANA_BUSQUEDA = timedelta(hours=3)  # solo se comparan capturas recientes
MISMO_INSTANTE = timedelta(seconds=1)


def _como_dict(c):
    return {"id": c.pk, "placa": c.placa, "camara": c.camara_id, "ts": c.timestamp}


@transaction.atomic
def registrar_evento(datos):
    """Guarda la captura y evalúa si genera infracciones o alertas.

    `datos`: dict validado por EventoSerializer. Devuelve (captura, resumen, creada).
    Si el evento ya existía (mismo evento_id), no lo procesa de nuevo.
    """
    existente = Captura.objects.filter(evento_id=datos["evento_id"]).first()
    if existente:
        return existente, {"duplicado": True}, False

    ts = datos["timestamp"]
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts)
    placa = grafo.evidencia.normalizar(datos["placa"])
    # La misma cámara no ve la misma placa dos veces en el mismo segundo: es un reenvío con otro id
    # (p. ej. la misma foto subida dos veces). Sin esto se duplicaban las infracciones.
    existente = Captura.objects.filter(camara_id=datos["camara_id"], placa=placa, timestamp__gte=ts - MISMO_INSTANTE,
                                       timestamp__lte=ts + MISMO_INSTANTE).first()
    if existente:
        return existente, {"duplicado": True}, False
    captura = Captura.objects.create(
        evento_id=datos["evento_id"], camara_id=datos["camara_id"], timestamp=ts, placa=placa,
        placa_clave=grafo.clave(placa), placa_confianza=datos["placa_confianza"],
        lecturas_votadas=datos.get("lecturas_votadas", 1), lecturas_totales=datos.get("lecturas_totales", 1),
        conf_detector=datos.get("conf_detector"), modelo=datos.get("modelo", {}))
    for nombre in datos.get("evidencia", []):
        Evidencia.objects.create(captura=captura, nombre=nombre)

    previas = [c for c in Captura.objects.filter(timestamp__gte=ts - VENTANA_BUSQUEDA, timestamp__lte=ts + VENTANA_BUSQUEDA)
               .exclude(pk=captura.pk) if grafo.misma_placa(c.placa, placa)]
    g, nodos, version = construir_grafo()
    cfg = parametros()
    r = grafo.evaluar_evento(g, nodos, _como_dict(captura), [_como_dict(c) for c in previas], k=cfg["K_VECINDARIO"],
                             v_max_kmh=cfg["VELOCIDAD_MAX_PLAUSIBLE_KMH"], tolerancia_kmh=cfg["TOLERANCIA_KMH"], error_reloj_s=cfg["ERROR_RELOJ_S"])

    resumen = {"infracciones": [], "sin_infraccion": r["sin_infraccion"], "alertas": []}
    for fila in r["infracciones"]:
        par = {fila["captura_anterior"], fila["captura_actual"]}
        ya_existe = (Infraccion.objects.filter(tipo=Infraccion.Tipo.VELOCIDAD, capturas=fila["captura_anterior"])
                     .filter(capturas=fila["captura_actual"]).exists())  # dos filtros: debe contener AMBAS
        if ya_existe:
            continue  # ese tramo ya generó una infracción
        inf = Infraccion.objects.create(tipo=Infraccion.Tipo.VELOCIDAD, placa=placa, coincidencia=fila["coincidencia"])
        inf.capturas.set(par)
        AnalisisGrafo.objects.create(infraccion=inf, ruta=fila["ruta"], km=fila["km"], segundos=fila["segundos"],
                                     v_medida=fila["v_medida"], v_conservadora=fila["v_conservadora"],
                                     limite=fila["limite"], exceso=fila["exceso"], tolerancia_kmh=cfg["TOLERANCIA_KMH"],
                                     error_reloj_s=cfg["ERROR_RELOJ_S"], version_grafo=version)
        resumen["infracciones"].append({"codigo": inf.codigo, **fila})
    for fila in r["alertas"]:
        alerta = Alerta.objects.create(tipo=Alerta.Tipo.CAPTURA_IMPOSIBLE, placa=placa, detalle=fila)
        alerta.capturas.set([fila["captura_anterior"], fila["captura_actual"]])
        resumen["alertas"].append({"id": alerta.pk, **fila})
    return captura, resumen, True
