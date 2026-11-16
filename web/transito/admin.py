from django.contrib import admin

from .models import CamaraTransito, Medicion, TramoTransito


@admin.register(CamaraTransito)
class CamaraTransitoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "distrito", "lat", "lon", "activa")
    list_filter = ("distrito", "activa")


@admin.register(TramoTransito)
class TramoTransitoAdmin(admin.ModelAdmin):
    list_display = ("origen", "destino", "km", "minutos_libre", "corredor")


@admin.register(Medicion)
class MedicionAdmin(admin.ModelAdmin):
    list_display = ("camara", "inicio", "por_minuto", "en_cuadro", "autos", "motos", "buses", "camiones", "error")
    list_filter = ("camara",)
