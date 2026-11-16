from rest_framework import serializers

import grafo
from camaras.models import Camara

from .models import Alerta, AnalisisGrafo, Captura, Infraccion


class EventoSerializer(serializers.Serializer):
    """Formato del evento que envía el worker (percepcion/pipeline.py)."""

    evento_id = serializers.CharField(max_length=40)
    placa = serializers.CharField(max_length=12)
    placa_confianza = serializers.FloatField(min_value=0, max_value=1)
    lecturas_votadas = serializers.IntegerField(min_value=0, required=False, default=1)
    lecturas_totales = serializers.IntegerField(min_value=0, required=False, default=1)
    camara_id = serializers.CharField(max_length=12)
    timestamp = serializers.DateTimeField()
    conf_detector = serializers.FloatField(required=False, allow_null=True)
    evidencia = serializers.ListField(child=serializers.CharField(max_length=120), required=False, default=list)
    modelo = serializers.DictField(required=False, default=dict)
    lecturas = serializers.ListField(child=serializers.CharField(), required=False)  # informativo

    def validate_camara_id(self, valor):
        if not Camara.objects.filter(codigo=valor, activa=True).exists():
            raise serializers.ValidationError(f"La cámara {valor} no existe o está inactiva.")
        return valor

    def validate_placa(self, valor):
        if len(grafo.evidencia.normalizar(valor)) < 5:
            raise serializers.ValidationError("Placa demasiado corta.")
        return valor


class CapturaSerializer(serializers.ModelSerializer):
    placa = serializers.CharField(source="placa_formateada")
    evidencias = serializers.SlugRelatedField(many=True, read_only=True, slug_field="nombre")

    class Meta:
        model = Captura
        fields = ["id", "evento_id", "camara", "timestamp", "placa", "placa_confianza",
                  "lecturas_votadas", "lecturas_totales", "conf_detector", "modelo", "evidencias"]


class AnalisisSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalisisGrafo
        exclude = ["id", "infraccion"]


class InfraccionSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(read_only=True)
    tipo_texto = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_texto = serializers.CharField(source="get_estado_display", read_only=True)
    capturas = CapturaSerializer(many=True, read_only=True)
    analisis = AnalisisSerializer(read_only=True)
    papeleta = serializers.SlugRelatedField(read_only=True, slug_field="numero")

    class Meta:
        model = Infraccion
        fields = ["id", "codigo", "tipo", "tipo_texto", "estado", "estado_texto", "placa", "coincidencia",
                  "creada", "capturas", "analisis", "papeleta"]


class AlertaSerializer(serializers.ModelSerializer):
    capturas = CapturaSerializer(many=True, read_only=True)

    class Meta:
        model = Alerta
        fields = ["id", "tipo", "placa", "detalle", "revisada", "creada", "capturas"]
