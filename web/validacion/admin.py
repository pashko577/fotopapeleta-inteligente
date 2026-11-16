from django.contrib import admin

from .models import Papeleta, SolicitudRevision, Validacion


@admin.register(Validacion)
class ValidacionAdmin(admin.ModelAdmin):
    list_display = ["infraccion", "decision", "validador", "placa_corregida", "fecha"]
    list_filter = ["decision"]
    readonly_fields = ["fecha"]


@admin.register(Papeleta)
class PapeletaAdmin(admin.ModelAdmin):
    list_display = ["numero", "placa", "infraccion", "estado", "emitida"]
    list_filter = ["estado"]
    search_fields = ["numero", "placa"]


@admin.register(SolicitudRevision)
class SolicitudRevisionAdmin(admin.ModelAdmin):
    list_display = ["codigo", "papeleta", "motivo", "estado", "creada"]
    list_filter = ["estado"]
