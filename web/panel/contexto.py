"""Datos comunes del panel: contador de la cola, alertas y estado del worker (topbar y sidebar)."""
from datetime import timedelta

from django.conf import settings
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone

from infracciones.models import Alerta, Captura, Infraccion

WORKER_EN_LINEA = timedelta(minutes=5)  # sin eventos en este lapso, el worker se muestra inactivo


NAV = [  # 8.3 Sidebar: grupos, ítems (nombre, url, ícono Lucide, clave de sección)
    ("Operación", [("Infracciones", "panel:infracciones", "triangle-alert", "infracciones"),
                   ("Papeletas", "panel:papeletas", "file-text", "papeletas")]),
    ("Red", [("Subir evidencia", "panel:subir", "upload", "subir"),
             ("Tránsito en vivo", "transito:inicio", "traffic-cone", "transito")]),
]


def panel(request):
    if not request.path.startswith("/panel/") or not request.user.is_authenticated:
        return {}
    ultimo = Captura.objects.aggregate(m=Max("recibido"))["m"]
    return {
        "nav": [(g, [(n, reverse(u), i, c) for n, u, i, c in items]) for g, items in NAV],
        "cola_pendientes": Infraccion.objects.filter(estado=Infraccion.Estado.EN_VALIDACION).count(),
        "alertas_abiertas": Alerta.objects.filter(revisada=False)[:6],
        "alertas_total": Alerta.objects.filter(revisada=False).count(),
        "worker_ultimo": ultimo,
        "worker_en_linea": bool(ultimo and timezone.now() - ultimo < WORKER_EN_LINEA),
        "modo_demo": settings.DEBUG,
    }
