"""Permisos por rol y consultas que comparten varias pantallas del panel."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from infracciones.models import Infraccion

VER_PANEL = "infracciones.view_infraccion"  # validador y administrador (el worker no entra al panel)


def es_admin(usuario):
    return usuario.is_superuser or usuario.groups.filter(name="administrador").exists()


def requiere(permiso=VER_PANEL, mensaje="Tu rol no permite ver esta pantalla"):
    """login_required + permiso de Django; sin permiso muestra el estado «sin permiso» (sección 12)."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            ok = es_admin(request.user) if permiso == "admin" else request.user.has_perm(permiso)
            if not ok:
                return render(request, "panel/sin_permiso.html", {"mensaje": mensaje}, status=403)
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


def infracciones_con_capturas():
    return (Infraccion.objects.select_related("analisis", "papeleta")
            .prefetch_related("capturas__evidencias", "capturas__camara", "validaciones__validador"))


def capturas_ordenadas(inf):
    return sorted(inf.capturas.all(), key=lambda c: c.timestamp)


def primera_captura(inf):
    caps = capturas_ordenadas(inf)
    return caps[0] if caps else None


def imagen(captura, tipo="cuadro"):
    """URL de la evidencia de una captura: "cuadro" (escena) o "placa" (recorte)."""
    if not captura:
        return None
    evs = [e for e in captura.evidencias.all() if e.archivo]
    preferida = [e for e in evs if f"_{tipo}" in e.nombre]
    elegida = (preferida or evs or [None])[0]
    return elegida.archivo.url if elegida else None


def resumen_fila(inf):
    """Datos de una infracción para tablas y colas (cámara de origen, hora, confianza, miniatura)."""
    c = primera_captura(inf)
    return {
        "inf": inf,
        "captura": c,
        "camara": c.camara if c else None,
        "ts": c.timestamp if c else inf.creada,
        "confianza": min((x.placa_confianza for x in inf.capturas.all()), default=None),
        "miniatura": imagen(c),
        "verificar": inf.coincidencia == "a_verificar",
    }
