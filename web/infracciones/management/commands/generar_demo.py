"""Datos de demostración: vehículos simulados que recorren la red de cámaras.

Cada paso por una cámara se registra con `registrar_evento`, el MISMO flujo que usa la API: las
infracciones, los tramos sin infracción y las alertas los decide el sistema, no este comando.
Con --decidir, un usuario «Validador demo» resuelve las infracciones para que haya papeletas y
reportes; las más recientes (--pendientes, 12 por defecto) quedan en la cola para validarlas en vivo.

Todo lo simulado lleva evento_id «SIM-…» y se borra con --borrar. Las imágenes dicen «SIMULADA».
"""
import hashlib
import io
import random
import string
from datetime import datetime, time, timedelta

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

import grafo
from camaras.servicios import construir_grafo
from infracciones.models import Alerta, Captura, Evidencia, Infraccion
from infracciones.servicios import registrar_evento
from validacion.models import Papeleta, SolicitudRevision, Validacion
from validacion.servicios import TransicionInvalida, solicitar_revision, validar

PREFIJO = "SIM-"
LETRAS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # sin I, O, Q
CONFUNDIBLES = {"8": "B", "B": "8", "0": "D", "D": "0", "5": "S", "S": "5", "2": "Z", "Z": "2", "1": "7", "7": "1"}
HORAS = list(range(6, 21))
PESO_HORA = [2, 6, 9, 7, 4, 3, 4, 5, 4, 3, 4, 6, 9, 8, 4]  # horas punta 7-9 y 17-19
MOTIVOS_RECHAZO = ["La placa no es legible en ninguna captura", "Las capturas son de vehículos distintos",
                   "Error de hora en una cámara"]
FUENTE = "C:/Windows/Fonts/arialbd.ttf"


def _fuente(tam):
    try:
        return ImageFont.truetype(FUENTE, tam)
    except OSError:
        return ImageFont.load_default(size=tam)


def placa_aleatoria(rnd):
    if rnd.random() < 0.7:
        inicio = rnd.choice(LETRAS) + rnd.choice(string.digits) + rnd.choice(LETRAS)
    else:
        inicio = "".join(rnd.choice(LETRAS) for _ in range(3))
    return inicio + "".join(rnd.choice(string.digits) for _ in range(3))


def mal_leida(placa, rnd):
    """La misma placa con un carácter confundible cambiado (como el 8/B del OCR real)."""
    posiciones = [i for i, ch in enumerate(placa) if ch in CONFUNDIBLES]
    if not posiciones:
        return None
    i = rnd.choice(posiciones)
    return placa[:i] + CONFUNDIBLES[placa[i]] + placa[i + 1:]


def dibujar_placa(placa, ancho=440):
    W, H = 440, 220
    img = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([3, 3, W - 4, H - 4], radius=14, outline=(20, 20, 20), width=7)
    d.rectangle([10, 10, W - 11, 52], fill=(29, 78, 216))
    d.text((W / 2, 31), "PERÚ", font=_fuente(30), fill=(255, 255, 255), anchor="mm")
    d.text((W / 2, 140), f"{placa[:3]}-{placa[3:]}", font=_fuente(104), fill=(15, 15, 15), anchor="mm")
    return img.resize((ancho, ancho // 2))


def dibujar_escena(captura):
    """Imagen de evidencia SIMULADA: no es una foto, lo dice en la imagen."""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (58, 64, 74))
    d = ImageDraw.Draw(img)
    for y in range(H // 2, H, 6):  # calzada con un degradado simple
        g = 58 + (y - H // 2) // 12
        d.line([(0, y), (W, y)], fill=(g, g + 4, g + 10), width=6)
    for x in range(-200, W, 220):
        d.polygon([(x + 600, H), (x + 660, H), (W // 2 + 4, H // 2), (W // 2 - 4, H // 2)], fill=(90, 96, 106))
    placa = dibujar_placa(captura.placa, 300)
    img.paste(placa, ((W - 300) // 2, 380))
    d.rectangle([(W - 300) // 2 - 6, 374, (W + 300) // 2 + 6, 536], outline=(245, 158, 11), width=4)
    d.rectangle([0, 0, W, 64], fill=(15, 23, 42))
    d.text((24, 32), "EVIDENCIA SIMULADA · datos de demostración", font=_fuente(28), fill=(251, 191, 36), anchor="lm")
    local = timezone.localtime(captura.timestamp)
    d.text((W - 24, 32), f"{captura.camara_id} · {local:%d/%m/%Y %H:%M:%S}", font=_fuente(28), fill=(255, 255, 255), anchor="rm")
    return img


def _jpeg(img, calidad=78):
    b = io.BytesIO()
    img.save(b, "JPEG", quality=calidad)
    return b.getvalue()


class Command(BaseCommand):
    help = "Genera vehículos simulados que pasan por el flujo real (registrar_evento). --borrar elimina lo simulado."

    def add_arguments(self, parser):
        parser.add_argument("--vehiculos", type=int, default=250)
        parser.add_argument("--dias", type=int, default=14, help="días hacia atrás desde hoy")
        parser.add_argument("--semilla", type=int, default=7)
        parser.add_argument("--decidir", action="store_true", help="resolver las infracciones, salvo las más recientes")
        parser.add_argument("--pendientes", type=int, default=12, help="infracciones más recientes que quedan en la cola")
        parser.add_argument("--sin-imagenes", action="store_true")
        parser.add_argument("--borrar", action="store_true", help="solo borrar los datos simulados")

    def handle(self, *args, **o):
        borrados = self.borrar()
        if o["borrar"]:
            self.stdout.write(self.style.SUCCESS(f"Datos simulados borrados: {borrados}"))
            return
        rnd = random.Random(o["semilla"])
        g, nodos, _ = construir_grafo()
        eventos = self.recorridos(rnd, g, o["vehiculos"], o["dias"])
        self.stdout.write(f"{o['vehiculos']} vehículos · {len(eventos)} pasos por cámaras")

        totales = {"infracciones": 0, "sin_infraccion": 0, "alertas": 0}
        for e in sorted(eventos, key=lambda e: e["timestamp"]):  # en orden, como llegarían del worker
            _, resumen, _ = registrar_evento(e)
            for k in totales:
                totales[k] += len(resumen.get(k, []))
        self.ajustar_fechas()
        self.stdout.write(f"Decisión del sistema: {totales['infracciones']} infracciones, "
                          f"{totales['sin_infraccion']} tramos sin infracción, {totales['alertas']} alertas")
        if o["decidir"]:
            self.decidir(rnd, o["pendientes"])
        if not o["sin_imagenes"]:
            n = self.imagenes()
            self.stdout.write(f"{n} imágenes de evidencia simulada")
        self.stdout.write(self.style.SUCCESS("Listo. Para quitar estos datos: python manage.py generar_demo --borrar"))

    # ------------------------------------------------------------------ simulación
    def recorridos(self, rnd, g, n, dias):
        ahora = timezone.localtime()
        eventos, placas = [], set()
        for i in range(n):
            placa = placa_aleatoria(rnd)
            while placa in placas:
                placa = placa_aleatoria(rnd)
            placas.add(placa)
            for _ in range(20):  # una hora de inicio que no esté en el futuro
                dia = ahora.date() - timedelta(days=rnd.randrange(dias))
                inicio = timezone.make_aware(datetime.combine(dia, time(rnd.choices(HORAS, PESO_HORA)[0], rnd.randrange(60), rnd.randrange(60))))
                if inicio < ahora - timedelta(minutes=30):
                    break
            else:
                continue
            tipo = rnd.choices(["normal", "exceso", "verificar", "clonada"], [70, 22, 5, 3])[0]

            if tipo == "clonada":  # dos autos con la misma placa, lejos y casi a la vez
                a, b = rnd.sample(list(g), 2)
                if grafo.a_estrella(g, a, b).costo < 5:
                    continue
                eventos += [self.evento(i, 0, placa, a, inicio, rnd),
                            self.evento(i, 1, placa, b, inicio + timedelta(seconds=rnd.randint(40, 90)), rnd)]
                continue

            ruta = [rnd.choice(list(g))]
            for _ in range(rnd.choice([1, 1, 2, 2, 3])):  # recorre 1 a 3 tramos sin repetir cámaras
                vecinos = [v for v, _ in g[ruta[-1]] if v not in ruta]
                if not vecinos:
                    break
                ruta.append(rnd.choice(vecinos))
            if len(ruta) < 2:
                continue
            t = inicio
            for k, camara in enumerate(ruta):
                if k:
                    km = next(w["km"] for v, w in g[ruta[k - 1]] if v == camara)
                    kmh = rnd.uniform(68, 112) if tipo == "exceso" else rnd.uniform(28, 56)
                    t += timedelta(seconds=km / kmh * 3600 + rnd.uniform(-1.5, 1.5))  # reloj no perfecto
                leida = placa
                if tipo == "verificar" and k == len(ruta) - 1:
                    leida = mal_leida(placa, rnd) or placa
                eventos.append(self.evento(i, k, leida, camara, t, rnd, real=placa))
        return eventos

    @staticmethod
    def evento(i, k, placa, camara, ts, rnd, real=None):
        votadas = rnd.randint(5, 8)
        return {"evento_id": f"{PREFIJO}{i:04d}-{k}", "placa": placa, "camara_id": camara, "timestamp": ts,
                "placa_confianza": round(rnd.uniform(0.55, 0.97), 3), "lecturas_votadas": votadas,
                "lecturas_totales": 8, "conf_detector": round(rnd.uniform(0.8, 0.97), 3),
                "evidencia": [f"{PREFIJO}{i:04d}-{k}_cuadro.jpg", f"{PREFIJO}{i:04d}-{k}_placa.jpg"],
                "modelo": {"origen": "generar_demo (simulado)", "placa_real": real or placa}}

    @staticmethod
    def ajustar_fechas():
        """Las fechas automáticas serían «ahora»; se llevan al momento simulado del evento."""
        sim = Captura.objects.filter(evento_id__startswith=PREFIJO)
        for c in sim.only("pk", "timestamp"):
            Captura.objects.filter(pk=c.pk).update(recibido=c.timestamp + timedelta(seconds=2))
        for inf in Infraccion.objects.filter(capturas__evento_id__startswith=PREFIJO).distinct().annotate(t=Max("capturas__timestamp")):
            Infraccion.objects.filter(pk=inf.pk).update(creada=inf.t + timedelta(seconds=3))
        for a in Alerta.objects.filter(capturas__evento_id__startswith=PREFIJO).distinct().annotate(t=Max("capturas__timestamp")):
            Alerta.objects.filter(pk=a.pk).update(creada=a.t + timedelta(seconds=3))

    def decidir(self, rnd, dejar):
        validador, creado = User.objects.get_or_create(username="validador.demo", defaults={
            "first_name": "Validador", "last_name": "Demo", "email": "validador.demo@ejemplo.com"})
        if creado:
            validador.set_unusable_password()  # no puede iniciar sesión: solo firma las decisiones simuladas
            validador.save()
            validador.groups.add(Group.objects.get(name="validador"))
        hoy = timezone.localdate()
        todas = list(Infraccion.objects.filter(capturas__evento_id__startswith=PREFIJO, estado=Infraccion.Estado.EN_VALIDACION)
                     .distinct().order_by("creada"))
        pendientes = todas[:max(len(todas) - dejar, 0)]  # las «dejar» más recientes quedan para validar en vivo
        conteo = {"aprobar": 0, "rechazar": 0, "escalar": 0, "revision": 0}
        for inf in pendientes:
            caps = list(inf.capturas.all())
            reales = {c.modelo.get("placa_real") for c in caps}
            correccion = ""
            if inf.coincidencia == "a_verificar":  # el validador compara las fotos y corrige la placa
                decision = rnd.choices(["aprobar", "rechazar"], [70, 30])[0]
                correccion = reales.pop() if len(reales) == 1 else ""
            else:
                decision = rnd.choices(["aprobar", "rechazar", "escalar"], [86, 9, 5])[0]
            motivo = rnd.choice(MOTIVOS_RECHAZO) if decision == "rechazar" else "¿Vehículo oficial?" if decision == "escalar" else ""
            try:
                v, papeleta = validar(inf, validador, decision, motivo=motivo, placa_corregida=correccion)
            except TransicionInvalida:
                continue
            conteo[decision] += 1
            cuando = inf.creada + timedelta(minutes=rnd.uniform(3, 90))
            Validacion.objects.filter(pk=v.pk).update(fecha=cuando)
            if papeleta:
                Papeleta.objects.filter(pk=papeleta.pk).update(emitida=cuando + timedelta(seconds=30))
                if rnd.random() < 0.06:  # algunos ciudadanos piden revisión
                    s = solicitar_revision(papeleta, "La placa fue mal leída", "Solicitud simulada para la demostración.",
                                           f"ciudadano{papeleta.pk}@ejemplo.com")
                    SolicitudRevision.objects.filter(pk=s.pk).update(creada=cuando + timedelta(days=1))
                    conteo["revision"] += 1
        Alerta.objects.filter(capturas__evento_id__startswith=PREFIJO, creada__date__lt=hoy - timedelta(days=2)).update(revisada=True)
        self.stdout.write(f"Validador demo: {conteo['aprobar']} aprobadas (papeletas), {conteo['rechazar']} rechazadas, "
                          f"{conteo['escalar']} escaladas, {conteo['revision']} solicitudes de revisión. "
                          f"{min(dejar, len(todas))} infracciones recientes quedan en la cola.")

    @staticmethod
    def imagenes():
        """Evidencia para las capturas que se muestran: las de infracciones y alertas, y la última de cada cámara."""
        sim = Captura.objects.filter(evento_id__startswith=PREFIJO)
        ids = set(sim.filter(infracciones__isnull=False).values_list("pk", flat=True))
        ids |= set(sim.filter(alertas__isnull=False).values_list("pk", flat=True))
        for cam in sim.values_list("camara_id", flat=True).distinct():
            ids.add(sim.filter(camara_id=cam).order_by("-timestamp").values_list("pk", flat=True).first())
        n = 0
        for c in Captura.objects.filter(pk__in=ids):
            for ev in c.evidencias.all():
                img = dibujar_escena(c) if ev.nombre.endswith("_cuadro.jpg") else dibujar_placa(c.placa, 220)
                datos = _jpeg(img)
                ev.sha256 = hashlib.sha256(datos).hexdigest()
                ev.archivo.save(ev.nombre, ContentFile(datos), save=True)
                n += 1
        return n

    @staticmethod
    def borrar():
        sim = Captura.objects.filter(evento_id__startswith=PREFIJO)
        infs = Infraccion.objects.filter(capturas__in=sim).distinct()
        n_inf = infs.count()
        Papeleta.objects.filter(infraccion__in=infs).delete()  # PROTECT: primero las papeletas (con sus revisiones)
        Infraccion.objects.filter(pk__in=list(infs.values_list("pk", flat=True))).delete()
        Alerta.objects.filter(capturas__in=sim).delete()
        for ev in Evidencia.objects.filter(captura__in=sim).exclude(archivo=""):
            ev.archivo.delete(save=False)
        n_cap = sim.count()
        sim.delete()
        return f"{n_cap} capturas y {n_inf} infracciones"
