from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ParametrosSistema(models.Model):
    """Parámetros de decisión editables desde Configuración (una sola fila).

    Si la fila no existe se usan los valores de settings.FOTOPAPELETA.
    """

    tolerancia_kmh = models.FloatField("tolerancia de velocidad (km/h)", validators=[MinValueValidator(0), MaxValueValidator(15)])
    error_reloj_s = models.FloatField("error de reloj por cámara (s)", validators=[MinValueValidator(0), MaxValueValidator(30)])
    k_vecindario = models.PositiveSmallIntegerField("profundidad BFS (k)", validators=[MinValueValidator(1), MaxValueValidator(6)])
    velocidad_max_plausible_kmh = models.FloatField("velocidad máxima plausible (km/h)",
                                                    validators=[MinValueValidator(100), MaxValueValidator(400)])
    actualizado = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "parámetros del sistema"
        verbose_name_plural = "parámetros del sistema"

    def __str__(self):
        return "Parámetros del sistema"


def parametros():
    """Parámetros vigentes como dict con las mismas claves de settings.FOTOPAPELETA."""
    cfg = dict(settings.FOTOPAPELETA)
    p = ParametrosSistema.objects.first()
    if p:
        cfg.update(TOLERANCIA_KMH=p.tolerancia_kmh, ERROR_RELOJ_S=p.error_reloj_s, K_VECINDARIO=p.k_vecindario,
                   VELOCIDAD_MAX_PLAUSIBLE_KMH=p.velocidad_max_plausible_kmh)
    return cfg


class TutorialVisto(models.Model):
    """El recorrido guiado de cada pantalla se muestra solo la primera vez (por usuario, en cualquier equipo)."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutoriales")
    pantalla = models.CharField(max_length=30)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tutorial visto"
        verbose_name_plural = "tutoriales vistos"
        constraints = [models.UniqueConstraint(fields=["usuario", "pantalla"], name="tutorial_unico")]
