"""Tránsito en vivo: cámaras públicas de Lima (no leen placas) y conteo de vehículos con YOLOv8.

Es una red APARTE de la de fiscalización (camaras.Camara): sirve para medir el flujo y planificar rutas
con A* usando tiempos que cambian según el tráfico observado.
"""
from django.db import models


class CamaraTransito(models.Model):
    codigo = models.CharField(max_length=40, primary_key=True)
    nombre = models.CharField(max_length=120)
    distrito = models.CharField(max_length=60)
    ubicacion = models.CharField("ubicación publicada", max_length=160, blank=True)
    lat = models.FloatField()
    lon = models.FloatField()
    fuente_coordenadas = models.CharField(max_length=80, blank=True)
    url = models.URLField("URL del stream (HLS)")
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "cámara de tránsito"
        verbose_name_plural = "cámaras de tránsito"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.nombre} ({self.distrito})"


class TramoTransito(models.Model):
    origen = models.ForeignKey(CamaraTransito, on_delete=models.CASCADE, related_name="+")
    destino = models.ForeignKey(CamaraTransito, on_delete=models.CASCADE, related_name="+")
    km = models.FloatField()
    minutos_libre = models.FloatField("minutos a flujo libre (OSRM)")
    corredor = models.CharField(max_length=120, blank=True)
    geometria = models.JSONField(default=list, blank=True)  # [[lat, lon], ...] para dibujar la vía

    class Meta:
        verbose_name = "tramo de tránsito"
        constraints = [models.UniqueConstraint(fields=["origen", "destino"], name="tramo_transito_unico")]


class Medicion(models.Model):
    """Unos segundos de video analizados: vehículos distintos (seguimiento) y cuántos hay a la vez."""

    camara = models.ForeignKey(CamaraTransito, on_delete=models.CASCADE, related_name="mediciones")
    inicio = models.DateTimeField(db_index=True)
    segundos = models.FloatField()
    cuadros = models.PositiveIntegerField()
    autos = models.PositiveIntegerField(default=0)
    motos = models.PositiveIntegerField(default=0)
    buses = models.PositiveIntegerField(default=0)
    camiones = models.PositiveIntegerField(default=0)
    por_minuto = models.FloatField("vehículos distintos por minuto")
    en_cuadro = models.FloatField("vehículos visibles a la vez (promedio)")
    imagen = models.ImageField(upload_to="transito/", blank=True)
    error = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "medición"
        verbose_name_plural = "mediciones"
        ordering = ["-inicio"]

    @property
    def total(self):
        return self.autos + self.motos + self.buses + self.camiones
