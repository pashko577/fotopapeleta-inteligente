from django.db import models

from camaras.models import Camara


class Captura(models.Model):
    """Un evento del worker de percepción: una placa vista por una cámara."""

    evento_id = models.CharField(max_length=40, unique=True)
    camara = models.ForeignKey(Camara, on_delete=models.PROTECT, related_name="capturas")
    timestamp = models.DateTimeField(db_index=True)
    placa = models.CharField(max_length=10, db_index=True)  # sin guion: V8D001
    placa_clave = models.CharField(max_length=10, db_index=True)  # sin caracteres confundibles
    placa_confianza = models.FloatField()
    lecturas_votadas = models.PositiveSmallIntegerField(default=1)
    lecturas_totales = models.PositiveSmallIntegerField(default=1)
    conf_detector = models.FloatField(null=True, blank=True)
    modelo = models.JSONField("versión de los modelos", default=dict, blank=True)
    recibido = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["placa_clave", "timestamp"])]

    def __str__(self):
        return f"{self.placa_formateada} · {self.camara_id} · {self.timestamp:%d/%m/%Y %H:%M:%S}"

    @property
    def placa_formateada(self):
        return f"{self.placa[:3]}-{self.placa[3:]}" if len(self.placa) == 6 else self.placa


class Evidencia(models.Model):
    captura = models.ForeignKey(Captura, on_delete=models.CASCADE, related_name="evidencias")
    nombre = models.CharField(max_length=120)
    archivo = models.ImageField(upload_to="evidencia/%Y/%m/%d/", null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name_plural = "evidencias"

    def __str__(self):
        return self.nombre


class Infraccion(models.Model):
    """Ciclo de vida de la arquitectura (sección 6.1)."""

    class Tipo(models.TextChoices):
        VELOCIDAD = "velocidad", "Exceso de velocidad"
        SEMAFORO = "semaforo", "Semáforo en rojo"
        PEATONAL = "peatonal", "Invasión de cruce peatonal"
        CELULAR = "celular", "Uso de celular"
        GIRO = "giro", "Giro prohibido"
        CONTRARIO = "contrario", "Sentido contrario"
        SENALES = "senales", "No respetar señales"

    class Estado(models.TextChoices):
        DETECTADA = "detectada", "Detectada"
        EN_VALIDACION = "en_validacion", "En validación"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"
        EMITIDA = "emitida", "Emitida"
        EN_REVISION = "en_revision", "En revisión"
        ANULADA = "anulada", "Anulada"

    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    estado = models.CharField(max_length=14, choices=Estado.choices, default=Estado.EN_VALIDACION, db_index=True)
    placa = models.CharField(max_length=10, db_index=True)
    coincidencia = models.CharField(max_length=12, help_text="confirmada o a_verificar")
    escalada = models.BooleanField(default=False, help_text="un validador pidió la opinión de un administrador")
    capturas = models.ManyToManyField(Captura, related_name="infracciones")
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "infracción"
        verbose_name_plural = "infracciones"
        ordering = ["-creada"]

    def __str__(self):
        return f"INF-{self.pk:06d} · {self.get_tipo_display()} · {self.placa}"

    @property
    def codigo(self):
        return f"INF-{self.pk:06d}"


class AnalisisGrafo(models.Model):
    """Por qué se decidió: ruta mínima, tiempos y velocidad (trazabilidad)."""

    infraccion = models.OneToOneField(Infraccion, on_delete=models.CASCADE, related_name="analisis")
    algoritmo = models.CharField(max_length=40, default="A* (recta_km)")
    ruta = models.JSONField()
    km = models.FloatField()
    segundos = models.FloatField()
    v_medida = models.FloatField()
    v_conservadora = models.FloatField()
    limite = models.FloatField()
    exceso = models.FloatField()
    tolerancia_kmh = models.FloatField()
    error_reloj_s = models.FloatField()
    version_grafo = models.CharField(max_length=12)

    class Meta:
        verbose_name = "análisis del grafo"
        verbose_name_plural = "análisis del grafo"


class Alerta(models.Model):
    """Situaciones que un humano debe revisar pero que no son infracciones (p. ej. placa clonada)."""

    class Tipo(models.TextChoices):
        CAPTURA_IMPOSIBLE = "captura_imposible", "Captura físicamente imposible"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    placa = models.CharField(max_length=10, db_index=True)
    capturas = models.ManyToManyField(Captura, related_name="alertas")
    detalle = models.JSONField(default=dict)
    revisada = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.placa}"
