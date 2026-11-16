from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from camaras.servicios import datos_red, version_red
from validacion.models import Validacion
from validacion.servicios import TransicionInvalida, validar

from .models import Alerta, Captura, Infraccion
from .serializers import AlertaSerializer, CapturaSerializer, EventoSerializer, InfraccionSerializer
from .servicios import registrar_evento


class TienePermiso(permissions.BasePermission):
    """Exige un permiso de Django concreto (asignado por rol con `manage.py crear_roles`)."""

    def __init__(self, permiso):
        self.permiso = permiso

    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm(self.permiso))


class EventoView(APIView):
    """POST /api/eventos/ — el worker de percepción reporta una placa vista por una cámara."""

    def get_permissions(self):
        return [permissions.IsAuthenticated(), TienePermiso("infracciones.add_captura")]

    def post(self, request):
        s = EventoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        captura, resumen, creada = registrar_evento(s.validated_data)
        return Response({"captura": CapturaSerializer(captura).data, **resumen},
                        status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK)


class GrafoView(APIView):
    """GET /api/grafo/ — red de cámaras (para el mapa y el laboratorio del grafo)."""

    def get(self, request):
        datos = datos_red()
        return Response({"version": version_red(datos), **datos})


class InfraccionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/infracciones/?estado=en_validacion&placa=V8D001 · POST /api/infracciones/{id}/validar/"""

    serializer_class = InfraccionSerializer

    def get_permissions(self):
        if self.action == "validar":
            return [permissions.IsAuthenticated()]  # el permiso de validar se revisa dentro de la acción
        return [permissions.IsAuthenticated(), TienePermiso("infracciones.view_infraccion")]

    def get_queryset(self):
        qs = (Infraccion.objects.select_related("analisis", "papeleta")
              .prefetch_related("capturas__evidencias"))
        estado, placa = self.request.query_params.get("estado"), self.request.query_params.get("placa")
        if estado:
            qs = qs.filter(estado=estado)
        if placa:
            qs = qs.filter(placa__icontains=placa.replace("-", "").upper())
        return qs

    class ValidarSerializer(serializers.Serializer):
        decision = serializers.ChoiceField(choices=Validacion.Decision.choices)
        motivo = serializers.CharField(required=False, allow_blank=True, default="")
        placa_corregida = serializers.CharField(required=False, allow_blank=True, default="")

    @action(detail=True, methods=["post"])
    def validar(self, request, pk=None):
        if not request.user.has_perm("validacion.add_validacion"):
            return Response({"detail": "Tu rol no permite validar infracciones."}, status=status.HTTP_403_FORBIDDEN)
        s = self.ValidarSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            v, papeleta = validar(self.get_object(), request.user, **s.validated_data)
        except TransicionInvalida as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        inf = Infraccion.objects.get(pk=pk)
        return Response({"infraccion": InfraccionSerializer(inf).data, "papeleta": papeleta.numero if papeleta else None})


class CapturaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Captura.objects.prefetch_related("evidencias")
    serializer_class = CapturaSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated(), TienePermiso("infracciones.view_captura")]


class AlertaViewSet(mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    """Las alertas se pueden marcar como revisadas (PATCH {"revisada": true})."""

    queryset = Alerta.objects.prefetch_related("capturas")
    serializer_class = AlertaSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        permiso = "infracciones.change_alerta" if self.request.method == "PATCH" else "infracciones.view_alerta"
        return [permissions.IsAuthenticated(), TienePermiso(permiso)]
