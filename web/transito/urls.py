from django.urls import path

from . import views

app_name = "transito"
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("ruta/", views.calcular_ruta, name="ruta"),
    path("<str:codigo>/medir/", views.medir_ahora, name="medir"),
    path("<str:codigo>/video/", views.video, name="video"),
    path("<str:codigo>/en-vivo/", views.datos_en_vivo, name="en_vivo"),
]
