"""Decisión humana sobre una infracción y emisión de la papeleta."""
from django.db import transaction
from django.utils import timezone

import grafo
from infracciones.models import Infraccion

from .models import Papeleta, SolicitudRevision, Validacion


class TransicionInvalida(Exception):
    pass


@transaction.atomic
def validar(infraccion, usuario, decision, motivo="", placa_corregida=""):
    """Aprobar (y emitir la papeleta), rechazar o escalar una infracción en validación.

    - Solo se validan infracciones en estado "En validación".
    - Rechazar y escalar exigen un motivo. Escalar no cambia el estado: la marca para un administrador.
    - Si el validador corrige la placa (p. ej. VBD001 -> V8D001), la papeleta sale con la corregida.
    Devuelve (validacion, papeleta o None).
    """
    infraccion = Infraccion.objects.select_for_update().get(pk=infraccion.pk)
    if infraccion.estado != Infraccion.Estado.EN_VALIDACION:
        raise TransicionInvalida(f"{infraccion.codigo} está en estado «{infraccion.get_estado_display()}».")
    if decision in (Validacion.Decision.RECHAZAR, Validacion.Decision.ESCALAR) and not motivo.strip():
        raise TransicionInvalida(f"Para {decision} se debe indicar un motivo.")
    placa = grafo.evidencia.normalizar(placa_corregida) if placa_corregida else ""
    if placa_corregida and len(placa) < 5:
        raise TransicionInvalida("La placa corregida no es válida.")

    v = Validacion.objects.create(infraccion=infraccion, validador=usuario, decision=decision,
                                  motivo=motivo.strip(), placa_corregida=placa)
    if decision == Validacion.Decision.ESCALAR:
        infraccion.escalada = True
        infraccion.save(update_fields=["escalada", "actualizada"])
        return v, None
    if decision == Validacion.Decision.RECHAZAR:
        infraccion.estado = Infraccion.Estado.RECHAZADA
        infraccion.save(update_fields=["estado", "actualizada"])
        return v, None

    if placa:
        infraccion.placa = placa
    infraccion.estado = Infraccion.Estado.EMITIDA
    infraccion.save(update_fields=["placa", "estado", "actualizada"])
    return v, Papeleta.emitir(infraccion, infraccion.placa)


@transaction.atomic
def anular(papeleta, usuario, motivo):
    """Anula una papeleta emitida o en revisión. El motivo queda en la auditoría."""
    papeleta = Papeleta.objects.select_for_update().get(pk=papeleta.pk)
    if papeleta.estado == Papeleta.Estado.ANULADA:
        raise TransicionInvalida(f"{papeleta.numero} ya está anulada.")
    if not motivo.strip():
        raise TransicionInvalida("Para anular se debe indicar un motivo.")
    papeleta.estado = Papeleta.Estado.ANULADA
    papeleta.anulada, papeleta.anulada_por, papeleta.motivo_anulacion = timezone.now(), usuario, motivo.strip()
    papeleta.save()
    inf = papeleta.infraccion
    inf.estado = Infraccion.Estado.ANULADA
    inf.save(update_fields=["estado", "actualizada"])
    return papeleta


@transaction.atomic
def solicitar_revision(papeleta, motivo, descripcion, correo, adjunto=None):
    """El ciudadano pide revisar una papeleta: queda «En revisión» hasta que se resuelva."""
    if papeleta.estado != Papeleta.Estado.EMITIDA:
        raise TransicionInvalida(f"La papeleta está «{papeleta.get_estado_display()}» y no admite una nueva revisión.")
    s = SolicitudRevision.objects.create(papeleta=papeleta, motivo=motivo, descripcion=descripcion,
                                         correo=correo, adjunto=adjunto)
    papeleta.estado = Papeleta.Estado.EN_REVISION
    papeleta.save(update_fields=["estado"])
    Infraccion.objects.filter(pk=papeleta.infraccion_id).update(estado=Infraccion.Estado.EN_REVISION)
    return s
