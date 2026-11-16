from django.contrib import admin

from .models import Alerta, AnalisisGrafo, Captura, Evidencia, Infraccion


class EvidenciaInline(admin.TabularInline):
    model = Evidencia
    extra = 0


@admin.register(Captura)
class CapturaAdmin(admin.ModelAdmin):
    list_display = ["evento_id", "placa_formateada", "camara", "timestamp", "placa_confianza", "lecturas_votadas"]
    list_filter = ["camara"]
    search_fields = ["placa", "evento_id"]
    date_hierarchy = "timestamp"
    inlines = [EvidenciaInline]


class AnalisisInline(admin.StackedInline):
    model = AnalisisGrafo
    can_delete = False
    extra = 0


@admin.register(Infraccion)
class InfraccionAdmin(admin.ModelAdmin):
    list_display = ["codigo", "tipo", "placa", "estado", "coincidencia", "creada"]
    list_filter = ["estado", "tipo", "coincidencia"]
    search_fields = ["placa"]
    filter_horizontal = ["capturas"]
    inlines = [AnalisisInline]


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ["tipo", "placa", "revisada", "creada"]
    list_filter = ["tipo", "revisada"]
    search_fields = ["placa"]
