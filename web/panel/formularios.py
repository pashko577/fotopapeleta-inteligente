from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

import grafo
from camaras.models import Camara
from camaras.servicios import datos_red

from .models import ParametrosSistema


class IngresoForm(AuthenticationForm):
    """Acepta el usuario o el correo institucional."""

    error_messages = {
        "invalid_login": "Usuario, correo o contraseña incorrectos.",
        "inactive": "Esta cuenta está desactivada.",
    }

    def clean(self):
        u = (self.cleaned_data.get("username") or "").strip()
        if "@" in u:
            usuario = get_user_model().objects.filter(email__iexact=u).first()
            if usuario:
                self.cleaned_data["username"] = usuario.username
        return super().clean()


class CamaraForm(forms.Form):
    """Modal «Agregar cámara»: la cámara y su primer tramo (sin tramo no forma parte del grafo)."""

    codigo = forms.RegexField(regex=r"^[A-Z]{2}-\d{2,3}$", max_length=12, label="Código",
                              error_messages={"invalid": "Usa el formato AV-21."})
    nombre = forms.CharField(max_length=120)
    x_km = forms.FloatField(label="x (km)")
    y_km = forms.FloatField(label="y (km)")
    url_stream = forms.URLField(label="URL del stream", required=False)
    vecino = forms.ModelChoiceField(Camara.objects.filter(activa=True), label="Conectar con")
    km = forms.FloatField(min_value=0.1, label="Distancia (km)")
    minutos = forms.FloatField(min_value=0.1, label="Tiempo típico (min)")
    limite_kmh = forms.IntegerField(min_value=10, max_value=120, initial=60, label="Límite (km/h)")

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"]
        if Camara.objects.filter(codigo=codigo).exists():
            raise forms.ValidationError(f"Ya existe la cámara {codigo}.")
        return codigo

    def clean(self):
        d = super().clean()
        if self.errors:
            return d
        red = datos_red()  # la red resultante debe seguir siendo válida (A* exacto)
        red["nodos"][d["codigo"]] = {"nombre": d["nombre"], "x_km": d["x_km"], "y_km": d["y_km"]}
        red["aristas"].append({"de": d["codigo"], "a": d["vecino"].codigo, "km": d["km"], "min": d["minutos"],
                               "limite_kmh": d["limite_kmh"]})
        errores = grafo.validar(red)
        if errores:
            raise forms.ValidationError(errores)
        return d


class ParametrosForm(forms.ModelForm):
    class Meta:
        model = ParametrosSistema
        fields = ["tolerancia_kmh", "error_reloj_s", "k_vecindario", "velocidad_max_plausible_kmh"]


class SubidaForm(forms.Form):
    """«Subir evidencia»: una foto o un video corto de una cámara del grafo."""

    MAX_MB = 100
    camara = forms.ModelChoiceField(Camara.objects.filter(activa=True), label="Cámara que tomó la imagen")
    fecha_hora = forms.DateTimeField(required=False, label="Fecha y hora de la captura",
                                     input_formats=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"])
    usar_exif = forms.BooleanField(required=False, initial=True, label="Usar la hora guardada en la foto (EXIF) si existe")
    archivo = forms.FileField(label="Foto o video", required=False)
    placa_manual = forms.RegexField(regex=r"^[A-Za-z0-9]{3}-?[0-9]{3}$", required=False, label="Placa escrita a mano (opcional)",
                                    error_messages={"invalid": "Usa el formato ABC-123."})

    def clean_archivo(self):
        from infracciones.subida import tipo_archivo
        f = self.cleaned_data["archivo"]
        if not f:
            return f
        if not tipo_archivo(f.name):
            raise forms.ValidationError("Sube una foto (JPG, PNG) o un video (MP4, AVI, MOV, MKV, WEBM).")
        if f.size > self.MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"El archivo supera los {self.MAX_MB} MB.")
        return f

    def clean_fecha_hora(self):
        ts = self.cleaned_data["fecha_hora"]
        from django.utils import timezone
        if ts and ts > timezone.now():
            raise forms.ValidationError("La hora de la captura no puede estar en el futuro.")
        return ts

    def clean_placa_manual(self):
        return self.cleaned_data["placa_manual"].upper()

    def clean(self):
        d = super().clean()
        if not self.errors and not d.get("archivo") and not d.get("placa_manual"):
            raise forms.ValidationError("Sube una foto o un video, o escribe la placa a mano.")
        return d
