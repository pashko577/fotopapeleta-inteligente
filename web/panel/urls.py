from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import views, views_red, views_sistema

app_name = "panel"
urlpatterns = [
    path("ingresar/", views.IngresoView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("", RedirectView.as_view(pattern_name="panel:infracciones"), name="resumen"),
    path("validacion/", views.validacion, name="validacion"),
    path("validacion/<int:pk>/", views.validacion, name="validacion_detalle"),
    path("validacion/<int:pk>/decidir/", views.decidir, name="decidir"),
    path("infracciones/", views.infracciones, name="infracciones"),
    path("infracciones/exportar/", views.exportar_infracciones, name="exportar_infracciones"),
    path("infracciones/<int:pk>/", views.infraccion_detalle, name="infraccion"),
    path("papeletas/", views.papeletas, name="papeletas"),
    path("papeletas/<str:numero>/anular/", views.anular_papeleta, name="anular_papeleta"),
    path("buscar/", views.buscar, name="buscar"),
    path("tutorial/visto/", views.tutorial_visto, name="tutorial_visto"),
    path("tutorial/reiniciar/", views.tutorial_reiniciar, name="tutorial_reiniciar"),
    path("alertas/<int:pk>/revisada/", views.alerta_revisada, name="alerta_revisada"),
    path("camaras/", views_red.camaras, name="camaras"),
    path("captura/", views_red.captura, name="captura"),
    path("captura/lecturas/", views_red.lecturas, name="lecturas"),
    path("captura/celular/", views_red.captura_celular, name="captura_celular"),
    path("subir/", views_red.subir, name="subir"),
    path("subir/no-leida/<str:token>/", views_red.escribir_no_leida, name="escribir_no_leida"),
    path("laboratorio/", views_red.laboratorio, name="laboratorio"),
    path("laboratorio/ejecutar/", views_red.laboratorio_ejecutar, name="laboratorio_ejecutar"),
    path("laboratorio/velocidad/", views_red.laboratorio_velocidad, name="laboratorio_velocidad"),
    path("laboratorio/limpiar/", views_red.laboratorio_limpiar, name="laboratorio_limpiar"),
    path("laboratorio/csv/", views_red.laboratorio_csv, name="laboratorio_csv"),
    path("reportes/", views_sistema.reportes, name="reportes"),
    path("configuracion/", views_sistema.configuracion, name="configuracion"),
    path("usuarios/", views_sistema.usuarios, name="usuarios"),
]
