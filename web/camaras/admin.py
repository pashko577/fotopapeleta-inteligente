from django.contrib import admin

from .models import Camara, Tramo


class TramoInline(admin.TabularInline):
    model = Tramo
    fk_name = "origen"
    extra = 0


@admin.register(Camara)
class CamaraAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "x_km", "y_km", "lat", "lon", "activa"]
    list_filter = ["activa"]
    search_fields = ["codigo", "nombre"]
    inlines = [TramoInline]


@admin.register(Tramo)
class TramoAdmin(admin.ModelAdmin):
    list_display = ["origen", "destino", "km", "minutos", "limite_kmh", "dirigida"]
    list_filter = ["dirigida", "limite_kmh"]
