from django.core.exceptions import ValidationError
from django.db import models


class Camara(models.Model):
    """Nodo del grafo: una cámara fija o un celular usado como cámara."""

    codigo = models.CharField("código", max_length=12, primary_key=True)
    nombre = models.CharField(max_length=120)
    # Coordenadas proyectadas (km) para la heurística de A*; lat/lon opcionales para el mapa.
    x_km = models.FloatField(null=True, blank=True)
    y_km = models.FloatField(null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    url_stream = models.URLField("URL del stream", blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "cámara"
        verbose_name_plural = "cámaras"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Tramo(models.Model):
    """Arista del grafo: vía conducible directamente entre dos cámaras."""

    origen = models.ForeignKey(Camara, on_delete=models.CASCADE, related_name="tramos_salida")
    destino = models.ForeignKey(Camara, on_delete=models.CASCADE, related_name="tramos_entrada")
    km = models.FloatField()
    minutos = models.FloatField()
    limite_kmh = models.PositiveSmallIntegerField("límite (km/h)", default=60)
    dirigida = models.BooleanField("solo un sentido", default=False)
    fuente = models.CharField(max_length=80, blank=True, help_text="manual, u OSRM (calles reales)")
    geometria = models.JSONField(default=list, blank=True)  # [[lat, lon], ...] para dibujar el tramo sobre el mapa

    class Meta:
        verbose_name = "tramo"
        constraints = [models.UniqueConstraint(fields=["origen", "destino"], name="tramo_unico")]

    def clean(self):
        if self.origen_id == self.destino_id:
            raise ValidationError("El origen y el destino deben ser cámaras distintas.")
        if self.km <= 0 or self.minutos <= 0:
            raise ValidationError("La distancia y el tiempo deben ser positivos.")

    def __str__(self):
        flecha = "→" if self.dirigida else "↔"
        return f"{self.origen_id} {flecha} {self.destino_id} ({self.km} km)"
