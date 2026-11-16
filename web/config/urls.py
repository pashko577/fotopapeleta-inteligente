from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from infracciones.views import AlertaViewSet, CapturaViewSet, EventoView, GrafoView, InfraccionViewSet

router = DefaultRouter()
router.register("infracciones", InfraccionViewSet, basename="infraccion")
router.register("capturas", CapturaViewSet, basename="captura")
router.register("alertas", AlertaViewSet, basename="alerta")

admin.site.site_header = "FotoPapeleta Inteligente — Administración"
admin.site.site_title = "FotoPapeleta"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/eventos/", EventoView.as_view(), name="eventos"),
    path("api/grafo/", GrafoView.as_view(), name="grafo"),
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("panel/transito/", include("transito.urls")),
    path("panel/", include("panel.urls")),
    path("", include("portal.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
