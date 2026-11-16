from django.contrib import admin

from .models import ParametrosSistema


@admin.register(ParametrosSistema)
class ParametrosSistemaAdmin(admin.ModelAdmin):
    list_display = ("tolerancia_kmh", "error_reloj_s", "k_vecindario", "velocidad_max_plausible_kmh", "actualizado")
