"""Tránsito en vivo: red real, congestión relativa y A* con tiempos dinámicos (sin red ni GPU)."""
import io
import json
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import CamaraTransito, Medicion
from .servicios import congestion, importar_red, red, ruta


class TransitoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        importar_red(json.loads(settings.FOTOPAPELETA["RED_TRANSITO_JSON"].read_text(encoding="utf-8")))
        call_command("crear_roles", stdout=io.StringIO())
        cls.validador = User.objects.create_user("val_t", password="x")
        cls.validador.groups.add(Group.objects.get(name="validador"))

    def medicion(self, codigo, en_cuadro, minutos_atras=0):
        return Medicion.objects.create(camara_id=codigo, inicio=timezone.now() - timedelta(minutes=minutos_atras),
                                       segundos=10, cuadros=100, por_minuto=60, en_cuadro=en_cuadro)

    def test_la_red_real_es_valida_y_conexa(self):
        self.assertEqual(CamaraTransito.objects.count(), 15)
        r = ruta("gallinazos", "domo_punta_negra")
        self.assertEqual((r["ruta"][0], r["ruta"][-1]), ("gallinazos", "domo_punta_negra"))
        self.assertEqual(r["minutos"], r["minutos_libre"])  # sin mediciones, todo a flujo libre

    def test_congestion_relativa_a_lo_normal_de_cada_camara(self):
        self.assertEqual(congestion(CamaraTransito.objects.get(pk="angamos"))["nivel"], "sin datos")
        for i in range(5):
            self.medicion("angamos", 4, minutos_atras=20 - i)
        self.assertEqual(congestion(CamaraTransito.objects.get(pk="angamos"))["nivel"], "fluido")
        self.medicion("angamos", 9)  # más del doble de lo normal
        e = congestion(CamaraTransito.objects.get(pk="angamos"))
        self.assertEqual((e["nivel"], e["tipico"]), ("congestionado", 4))
        self.assertGreater(e["factor"], 1.6)

    def test_medicion_vieja_no_cuenta(self):
        for i in range(6):
            self.medicion("derby", 9, minutos_atras=60 + i)
        self.assertEqual(congestion(CamaraTransito.objects.get(pk="derby"))["nivel"], "sin datos")

    def test_a_estrella_evita_el_tramo_congestionado(self):
        """Angamos -> Javier Prado: con tráfico en Angamos, A* elige otra ruta o tarda más; nunca menos que a flujo libre."""
        libre = ruta("republicapanama", "derby")
        for codigo in ("angamos", "javierprado"):
            for i in range(5):
                self.medicion(codigo, 3, minutos_atras=25 - i)
            self.medicion(codigo, 9)
        ahora = ruta("republicapanama", "derby")
        self.assertGreaterEqual(ahora["minutos"], libre["minutos"])
        self.assertGreaterEqual(ahora["minutos"], ahora["minutos_libre"])

    def test_heuristica_admisible(self):
        """La heurística (recta a la velocidad máxima de la red) nunca supera el tiempo real de un tramo."""
        import grafo
        g, nodos, _, vmax = red()
        h = grafo.recta_min(nodos, vmax_kmh=vmax)
        for a, vecinos in g.items():
            for b, w in vecinos:
                self.assertLessEqual(h(a, b), w["min"] + 1e-9, (a, b))

    def test_pantalla_y_ruta(self):
        self.client.force_login(self.validador)
        self.assertContains(self.client.get("/panel/transito/"), "Tránsito en vivo")
        self.assertContains(self.client.get("/panel/transito/?camara=javierprado"), "Av. Javier Prado Este")
        r = self.client.post("/panel/transito/ruta/", {"origen": "lamarina", "destino": "derby"})
        self.assertContains(r, "ruta-codigos")
        self.assertContains(self.client.post("/panel/transito/ruta/", {"origen": "derby", "destino": "derby"}), "dos cámaras distintas")

    def test_medir_ahora_con_stream_caido(self):
        from .servicios import StreamNoDisponible
        self.client.force_login(self.validador)
        with mock.patch("transito.views.medir", side_effect=StreamNoDisponible("No se pudo abrir el stream de Av. Angamos.")):
            r = self.client.post("/panel/transito/angamos/medir/")
        self.assertContains(r, "No se pudo abrir el stream")

    def test_sin_sesion_no_entra(self):
        self.assertEqual(self.client.get("/panel/transito/").status_code, 302)


class EnVivoTest(TestCase):
    """Análisis continuo: ventanas deslizantes y pantallas, sin abrir streams (el hilo no se arranca)."""

    @classmethod
    def setUpTestData(cls):
        importar_red(json.loads(settings.FOTOPAPELETA["RED_TRANSITO_JSON"].read_text(encoding="utf-8")))
        call_command("crear_roles", stdout=io.StringIO())
        cls.validador = User.objects.create_user("val_v", password="x")
        cls.validador.groups.add(Group.objects.get(name="validador"))

    def setUp(self):
        from . import en_vivo
        en_vivo._activos.clear()
        self.addCleanup(en_vivo._activos.clear)
        for nombre in ("start", "is_alive"):  # como si el hilo estuviera corriendo, sin abrir el stream
            p = mock.patch.object(en_vivo.Analizador, nombre, return_value=True)
            p.start()
            self.addCleanup(p.stop)

    def test_ventanas_deslizantes(self):
        from . import en_vivo
        a = en_vivo.obtener(CamaraTransito.objects.get(pk="angamos"))
        self.assertIsNone(a.resumen()["por_minuto"])                     # sin video todavía
        ahora = a._t = 100.0                                             # segundos de video
        a._desde = ahora - 30                                            # 30 s de video
        a._visibles.extend([(ahora - 20, 50), (ahora - 2, 4), (ahora - 1, 6)])  # el de hace 20 s ya no cuenta
        a._conteos.extend([(ahora - 25, "autos"), (ahora - 10, "autos"), (ahora - 5, "motos")])
        r = a.resumen()
        self.assertEqual(r["en_cuadro"], 5)
        self.assertEqual(r["por_minuto"], 6.0)                           # 3 vehículos en 30 s
        self.assertEqual(r["por_clase"]["autos"], 2)

    def test_un_analizador_por_camara(self):
        from . import en_vivo
        c = CamaraTransito.objects.get(pk="derby")
        self.assertIs(en_vivo.obtener(c), en_vivo.obtener(c))

    def test_pantalla_con_deteccion_en_vivo(self):
        self.client.force_login(self.validador)
        r = self.client.get("/panel/transito/?camara=javierprado")
        self.assertContains(r, "/panel/transito/javierprado/video/")
        self.assertContains(r, "/panel/transito/javierprado/en-vivo/")
        self.assertContains(self.client.get("/panel/transito/javierprado/en-vivo/"), "Conectando")

    def test_error_del_stream_se_muestra(self):
        from . import en_vivo
        a = en_vivo.obtener(CamaraTransito.objects.get(pk="angamos"))
        a.error = "No se pudo abrir el stream de Av. Angamos."
        self.client.force_login(self.validador)
        self.assertContains(self.client.get("/panel/transito/angamos/en-vivo/"), "No se pudo abrir el stream")
