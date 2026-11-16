from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from infracciones.models import Infraccion


class Validacion(models.Model):
    """Decisión humana sobre una infracción. Ninguna papeleta se emite sin una aprobación."""

    class Decision(models.TextChoices):
        APROBAR = "aprobar", "Aprobar"
        RECHAZAR = "rechazar", "Rechazar"
        ESCALAR = "escalar", "Escalar"  # duda: se deja en la cola marcada para un administrador

    infraccion = models.ForeignKey(Infraccion, on_delete=models.CASCADE, related_name="validaciones")
    validador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=10, choices=Decision.choices)
    motivo = models.TextField(blank=True)
    placa_corregida = models.CharField(max_length=10, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "validación"
        verbose_name_plural = "validaciones"
        ordering = ["-fecha"]


class Papeleta(models.Model):
    class Estado(models.TextChoices):
        EMITIDA = "emitida", "Emitida"
        EN_REVISION = "en_revision", "En revisión"
        ANULADA = "anulada", "Anulada"

    numero = models.CharField(max_length=20, unique=True)
    infraccion = models.OneToOneField(Infraccion, on_delete=models.PROTECT, related_name="papeleta")
    placa = models.CharField(max_length=10, db_index=True)
    emitida = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.EMITIDA)
    anulada = models.DateTimeField(null=True, blank=True)
    anulada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="+")
    motivo_anulacion = models.TextField(blank=True)

    class Meta:
        ordering = ["-emitida"]

    def __str__(self):
        return self.numero

    @classmethod
    @transaction.atomic
    def emitir(cls, infraccion, placa):
        anio = timezone.localdate().year
        ultimo = cls.objects.select_for_update().filter(numero__startswith=f"FP-{anio}-").order_by("-numero").first()
        siguiente = int(ultimo.numero.rsplit("-", 1)[1]) + 1 if ultimo else 1
        return cls.objects.create(numero=f"FP-{anio}-{siguiente:06d}", infraccion=infraccion, placa=placa)


class SolicitudRevision(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACEPTADA = "aceptada", "Aceptada"
        DENEGADA = "denegada", "Denegada"

    papeleta = models.ForeignKey(Papeleta, on_delete=models.CASCADE, related_name="revisiones")
    motivo = models.CharField(max_length=120)
    descripcion = models.TextField()
    correo = models.EmailField()
    adjunto = models.FileField(upload_to="revisiones/%Y/%m/", null=True, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "solicitud de revisión"
        verbose_name_plural = "solicitudes de revisión"

    @property
    def codigo(self):
        return f"REV-{self.pk:06d}"
