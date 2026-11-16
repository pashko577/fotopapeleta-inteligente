from django.urls import path

from . import views

app_name = "portal"
urlpatterns = [
    path("", views.consulta, name="consulta"),
    path("resultados/", views.resultados, name="resultados"),
    path("papeleta/<str:numero>/", views.detalle, name="detalle"),
    path("papeleta/<str:numero>/revision/", views.revision, name="revision"),
    path("papeleta/<str:numero>/imprimir/", views.imprimir, name="imprimir"),
    path("como-funciona/", views.como_funciona, name="como_funciona"),
    path("ayuda/", views.ayuda, name="ayuda"),
    path("mis-consultas/", views.mis_consultas, name="mis_consultas"),
]
