"""Portal ciudadano (público): consulta por placa, detalle de la papeleta y solicitud de revisión (P1–P4)."""
import re
from collections import Counter

from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

import grafo
from panel.grafo_svg import lienzo
from panel.utilidades import capturas_ordenadas, imagen
from validacion.models import Papeleta, Validacion
from validacion.servicios import TransicionInvalida, solicitar_revision

PLACA_VALIDA = re.compile(r"^[A-Z0-9]{5,7}$")
ESTADOS_PORTAL = [("", "Todas"), ("emitida", "Emitidas"), ("en_revision", "En revisión"), ("anulada", "Anuladas")]


def _placa(texto):
    return grafo.evidencia.normalizar(texto or "")


def _papeletas():
    return (Papeleta.objects.select_related("infraccion__analisis")
            .prefetch_related("infraccion__capturas__evidencias", "infraccion__capturas__camara", "revisiones"))


def consulta(request):
    """P1 · Consulta por placa."""
    return render(request, "portal/consulta.html", {"seccion": "consultar"})


def resultados(request):
    """P2 · Resultados de la consulta."""
    texto = request.GET.get("placa", "")
    placa = _placa(texto)
    if not PLACA_VALIDA.match(placa):
        return render(request, "portal/consulta.html", {"seccion": "consultar", "placa": texto,
                                                        "error": "Escribe una placa válida, por ejemplo ABC-123."})
    todas = list(_papeletas().filter(placa=placa))
    conteo = Counter(p.estado for p in todas)
    estado = request.GET.get("estado", "")
    visibles = [p for p in todas if not estado or p.estado == estado]
    for p in visibles:
        caps = capturas_ordenadas(p.infraccion)
        p.primera, p.ultima = (caps[0], caps[-1]) if caps else (None, None)
        p.miniatura = imagen(p.primera)
        p.revision = max(p.revisiones.all(), key=lambda s: s.creada, default=None)
    return render(request, "portal/resultados.html", {
        "seccion": "consultar", "placa": placa, "papeletas": visibles, "total": len(todas), "estado": estado,
        "chips": [(k, n, len(todas) if not k else conteo[k]) for k, n in ESTADOS_PORTAL], "ahora": timezone.now(),
    })


def _contexto_detalle(p):
    inf = p.infraccion
    caps = capturas_ordenadas(inf)
    a = getattr(inf, "analisis", None)
    ruta = a.ruta if a else []
    aprobacion = inf.validaciones.filter(decision=Validacion.Decision.APROBAR).select_related("validador").first()
    historial = []
    if caps:
        historial.append(("detectada", "Detectada", f"Cámara {caps[0].camara_id}", caps[0].timestamp))
    for c in caps[1:]:
        historial.append(("enriquecida", "Evidencia adicional", f"Reaparición en {c.camara_id}", c.timestamp))
    if aprobacion:
        historial.append(("aprobada", "Aprobada", "Revisada por un validador", aprobacion.fecha))
    historial.append(("emitida", "Emitida", f"Papeleta {p.numero}", p.emitida))
    for s in p.revisiones.all():
        historial.append(("en_revision", "Revisión solicitada", f"Solicitud {s.codigo}", s.creada))
    if p.anulada:
        historial.append(("anulada", "Anulada", p.motivo_anulacion, p.anulada))
    return {
        "p": p, "inf": inf, "analisis": a, "capturas": caps, "miniaturas": [(c, imagen(c)) for c in caps],
        "aprobacion": aprobacion, "historial": sorted(historial, key=lambda h: h[3]),
        "grafo": lienzo(ancho=1100, alto=230, ruta=ruta, origen=ruta[0] if ruta else None,
                        destino=ruta[-1] if ruta else None, etiquetas=None, margen=60),
        "segundos": (caps[-1].timestamp - caps[0].timestamp).total_seconds() if len(caps) > 1 else None,
    }


def detalle(request, numero):
    """P3 · Detalle de papeleta."""
    p = get_object_or_404(_papeletas(), numero=numero.upper())
    return render(request, "portal/detalle.html", {"seccion": "consultar", **_contexto_detalle(p)})


def imprimir(request, numero):
    """Versión imprimible («Descargar PDF» abre el diálogo de impresión del navegador)."""
    p = get_object_or_404(_papeletas(), numero=numero.upper())
    return render(request, "portal/imprimir.html", _contexto_detalle(p))


class RevisionForm(forms.Form):
    MOTIVOS = ["La placa fue mal leída", "No era mi vehículo", "El vehículo estaba exceptuado (emergencia)",
               "Error en la hora o el lugar", "Otro"]
    motivo = forms.ChoiceField(choices=[(m, m) for m in MOTIVOS])
    descripcion = forms.CharField(max_length=500, widget=forms.Textarea, label="Describe lo ocurrido")
    adjunto = forms.FileField(required=False, label="Adjunto")
    correo = forms.EmailField(label="Correo para la respuesta")
    declaracion = forms.BooleanField(error_messages={"required": "Debes aceptar la declaración para enviar la solicitud."})

    def clean_adjunto(self):
        f = self.cleaned_data.get("adjunto")
        if f:
            if f.size > 10 * 1024 * 1024:
                raise forms.ValidationError("El archivo supera los 10 MB.")
            if not f.name.lower().endswith((".jpg", ".jpeg", ".png", ".pdf")):
                raise forms.ValidationError("Solo se aceptan fotos (JPG, PNG) o PDF.")
        return f


def revision(request, numero):
    """P4 · Solicitar revisión."""
    p = get_object_or_404(Papeleta, numero=numero.upper())
    form = RevisionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            s = solicitar_revision(p, d["motivo"], d["descripcion"], d["correo"], d["adjunto"])
        except TransicionInvalida as e:
            form.add_error(None, str(e))
        else:
            return render(request, "portal/revision_enviada.html", {"p": p, "s": s, "correo": d["correo"]})
    return render(request, "portal/revision.html", {"p": p, "form": form, "volver": reverse("portal:detalle", args=[p.numero])})


def como_funciona(request):
    return render(request, "portal/como_funciona.html", {"seccion": "como"})


def ayuda(request):
    return render(request, "portal/ayuda.html", {"seccion": "ayuda"})


def mis_consultas(request):
    return render(request, "portal/mis_consultas.html", {"seccion": "mis"})
