"""Componentes y formatos del sistema de diseño (prototipo/diseno_prototipo_pencil.md).

Se cargan como builtins (settings.TEMPLATES), así que no hace falta {% load fp %}.
"""
from django import template
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

import lucide

register = template.Library()

# 3.4 Estados de la infracción: color + ícono + texto (nunca solo color)
ESTADOS = {
    "detectada": ("bg-neutral-subtle text-text-secondary", "scan-line", "Detectada"),
    "enriquecida": ("bg-info-subtle text-info", "waypoints", "Enriquecida"),
    "en_validacion": ("bg-warning-subtle text-warning", "hourglass", "En validación"),
    "aprobada": ("bg-success-subtle text-success", "circle-check", "Aprobada"),
    "rechazada": ("bg-danger-subtle text-danger", "circle-x", "Rechazada"),
    "emitida": ("bg-primary-subtle text-primary-text", "file-check", "Emitida"),
    "en_revision": ("bg-warning-subtle text-warning", "message-square", "En revisión"),
    "anulada": ("bg-neutral-subtle text-text-muted", "ban", "Anulada"),
    "escalada": ("bg-warning-subtle text-warning", "flag", "Escalada"),
}

# 3.5 Tipos de infracción: ícono y color categórico
TIPOS = {
    "velocidad": ("gauge", "text-cat-velocidad bg-cat-velocidad/10"),
    "semaforo": ("octagon-alert", "text-cat-semaforo bg-cat-semaforo/10"),
    "peatonal": ("footprints", "text-cat-peatonal bg-cat-peatonal/10"),
    "celular": ("smartphone", "text-cat-celular bg-cat-celular/10"),
    "giro": ("corner-up-right", "text-cat-giro bg-cat-giro/10"),
    "contrario": ("arrow-left-right", "text-cat-contrario bg-cat-contrario/10"),
    "senales": ("signpost", "text-cat-senales bg-cat-senales/10"),
}
NOMBRE_TIPO = {
    "velocidad": "Exceso de velocidad", "semaforo": "Semáforo en rojo", "peatonal": "Invasión de cruce peatonal",
    "celular": "Uso de celular", "giro": "Giro prohibido", "contrario": "Sentido contrario", "senales": "No respetar señales",
}


def icono(nombre, tam=16, clase=""):
    attrs = {"aria-hidden": "true"}
    if clase:
        attrs["class"] = clase
    return mark_safe(lucide._render_icon(nombre, tam, **attrs))


@register.simple_tag
def badge_estado(estado, texto=None):
    clases, ic, nombre = ESTADOS.get(estado, ESTADOS["detectada"])
    return format_html(
        '<span class="inline-flex h-6 items-center gap-1 rounded-full px-2 text-xs font-medium whitespace-nowrap {}">{}{}</span>',
        clases, icono(ic, 14), texto or nombre)


@register.simple_tag
def icono_tipo(tipo, tam=16):
    ic, clases = TIPOS.get(tipo, TIPOS["velocidad"])
    return format_html('<span class="inline-flex size-6 flex-none items-center justify-center rounded-md {}">{}</span>',
                       clases, icono(ic, tam))


@register.simple_tag
def tag_tipo(tipo):
    return format_html('<span class="inline-flex items-center gap-2">{}<span>{}</span></span>',
                       icono_tipo(tipo), NOMBRE_TIPO.get(tipo, tipo))


@register.filter
def nombre_tipo(tipo):
    return NOMBRE_TIPO.get(tipo, tipo)


@register.filter
def placa(valor):
    """V8D001 -> V8D-001 (formato peruano de autos)."""
    v = (valor or "").replace("-", "").upper()
    return f"{v[:3]}-{v[3:]}" if len(v) == 6 else v


@register.simple_tag
def placa_sm(valor, verificar=False):
    if verificar:
        return format_html('<span class="placa-sm verificar">{}{}</span>', placa(valor), icono("triangle-alert", 14))
    return format_html('<span class="placa-sm">{}</span>', placa(valor))


@register.simple_tag
def placa_grande(valor, tam="lg"):
    return format_html('<span class="placa placa-{}" role="img" aria-label="Placa {}">'
                       '<span class="placa-franja">PERÚ</span><span class="placa-num">{}</span></span>',
                       tam, placa(valor), placa(valor))


@register.filter
def pct(valor):
    """0.94 -> "94 %" (sin decimales, sección 13)."""
    if valor is None or valor == "":
        return "—"
    return f"{round(float(valor) * 100)} %"


@register.filter
def num(valor, decimales=1):
    """Punto decimal en km y km/h (sección 13): 87.1"""
    if valor is None or valor == "":
        return "—"
    return f"{float(valor):.{int(decimales)}f}"


@register.filter
def miles(valor):
    """1842 -> "1 842" (espacio fino como separador de miles)."""
    return f"{int(valor):,}".replace(",", " ")


@register.filter
def fecha_hora(dt):
    if not dt:
        return "—"
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M:%S")


@register.filter
def fecha(dt):
    if not dt:
        return "—"
    return (timezone.localtime(dt) if hasattr(dt, "tzinfo") and dt.tzinfo else dt).strftime("%d/%m/%Y")


@register.filter
def hora(dt):
    if not dt:
        return "—"
    return timezone.localtime(dt).strftime("%H:%M:%S")


@register.filter
def hace(dt):
    """Tiempo transcurrido corto: "hace 34 min", "hace 2 h", "hace 3 d"."""
    if not dt:
        return "—"
    s = (timezone.now() - dt).total_seconds()
    if s < 60:
        return "hace segundos"
    if s < 3600:
        return f"hace {int(s // 60)} min"
    if s < 86400:
        return f"hace {int(s // 3600)} h"
    return f"hace {int(s // 86400)} d"


@register.filter
def duracion(segundos):
    """120 -> "2 min 00 s"."""
    if segundos is None:
        return "—"
    m, s = divmod(int(round(float(segundos))), 60)
    if m >= 60:
        return f"{m // 60} h {m % 60:02d} min"
    return f"{m} min {s:02d} s" if m else f"{s} s"


@register.filter
def iniciales(usuario):
    nombre = (usuario.get_full_name() or usuario.username).split()
    return "".join(p[0] for p in nombre[:2]).upper()


@register.filter
def nombre_corto(usuario):
    """Tonny Hinostroza -> T. Hinostroza"""
    if not usuario:
        return "—"
    if usuario.first_name and usuario.last_name:
        return f"{usuario.first_name[0]}. {usuario.last_name.split()[0]}"
    return usuario.get_full_name() or usuario.username


@register.filter
def rol(usuario):
    if usuario.is_superuser:
        return "Administrador"
    grupos = {g.name for g in usuario.groups.all()}
    for g, nombre in (("administrador", "Administrador"), ("validador", "Validador"), ("worker", "Worker")):
        if g in grupos:
            return nombre
    return "Sin rol"


@register.filter
def get(d, clave):
    return d.get(clave) if hasattr(d, "get") else None


@register.simple_tag(takes_context=True)
def url_con(context, **cambios):
    """Querystring actual con algunos parámetros cambiados (filtros y paginación)."""
    q = context["request"].GET.copy()
    for k, v in cambios.items():
        if v in (None, ""):
            q.pop(k, None)
        else:
            q[k] = v
    return "?" + q.urlencode() if q else "?"


@register.simple_tag(takes_context=True)
def datos_tutorial(context):
    """JSON con los pasos del recorrido guiado de la pantalla actual (lo lee static/js/app.js)."""
    import json

    from panel.models import TutorialVisto
    from panel.tutorial import COMUNES, pasos

    usuario, seccion = context["user"], context.get("seccion") or ""
    vistos = set(TutorialVisto.objects.filter(usuario=usuario).values_list("pantalla", flat=True))
    primera = "bienvenida" not in vistos
    manual = pasos(seccion, usuario) or [{"tour": t, "titulo": ti, "texto": tx, "lado": l} for t, ti, tx, _, l in COMUNES]
    from django.urls import reverse
    datos = {"pantalla": seccion, "primera": primera, "manual": manual, "url": reverse("panel:tutorial_visto"),
             "auto": pasos(seccion, usuario, primera) if (primera or seccion not in vistos) else []}
    texto = json.dumps(datos, ensure_ascii=False).replace("<", "\u003c")
    return mark_safe(f'<script id="datos-tutorial" type="application/json">{texto}</script>')
