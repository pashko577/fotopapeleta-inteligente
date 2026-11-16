"""Flujo completo por la API: evento -> grafo -> infracción/alerta -> validación -> papeleta."""
import io
import json
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from camaras.servicios import importar_red
from validacion.models import Papeleta

from .models import Alerta, Captura, Infraccion

T0 = timezone.make_aware(datetime(2026, 10, 15, 8, 42, 0))


def evento(n, placa, camara, segundos, **extra):
    return {"evento_id": f"EV-TEST-{n:04d}", "placa": placa, "placa_confianza": 0.9, "lecturas_votadas": 8,
            "lecturas_totales": 8, "camara_id": camara, "timestamp": (T0 + timedelta(seconds=segundos)).isoformat(),
            "evidencia": [f"EV-TEST-{n:04d}_cuadro.jpg"], **extra}


class FlujoAPITest(TestCase):
    @classmethod
    def setUpTestData(cls):
        importar_red(json.loads(settings.FOTOPAPELETA["GRAFO_JSON"].read_text(encoding="utf-8")))
        call_command("crear_roles", "--worker", "worker-av01", stdout=io.StringIO())
        cls.token_worker = Token.objects.get(user__username="worker-av01").key
        cls.validador = User.objects.create_user("validador1", password="x")
        cls.validador.groups.add(Group.objects.get(name="validador"))
        cls.ciudadano = User.objects.create_user("sin_rol", password="x")

    def setUp(self):
        self.worker = APIClient()
        self.worker.credentials(HTTP_AUTHORIZATION=f"Token {self.token_worker}")
        self.val = APIClient()
        self.val.force_authenticate(self.validador)

    def post(self, *args, **kw):
        return self.worker.post("/api/eventos/", evento(*args, **kw), format="json")

    # --- Registro de eventos y decisión -------------------------------------------------
    def test_infraccion_de_velocidad(self):
        self.assertEqual(self.post(1, "VBD-001", "AV-01", 0).status_code, 201)
        r = self.post(2, "VBD-001", "AV-08", 120)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data["infracciones"]), 1)
        inf = Infraccion.objects.get()
        self.assertEqual((inf.estado, inf.placa, inf.coincidencia), ("en_validacion", "VBD001", "confirmada"))
        self.assertEqual(inf.capturas.count(), 2)
        a = inf.analisis
        self.assertEqual((a.ruta, a.km, a.v_conservadora, a.exceso, a.limite), (["AV-01", "AV-08"], 3.0, 87.1, 27.1, 60))
        self.assertEqual(len(a.version_grafo), 12)

    def test_sin_infraccion_y_vinculo_a_verificar(self):
        self.post(1, "D9R-052", "AV-01", 0)
        r = self.post(2, "DOR-052", "AV-08", 200)
        self.assertEqual(r.data["infracciones"], [])
        self.assertEqual(r.data["sin_infraccion"][0]["coincidencia"], "a_verificar")
        self.assertEqual(r.data["sin_infraccion"][0]["v_conservadora"], 52.9)

    def test_alerta_por_captura_imposible(self):
        self.post(1, "T3P-298", "AV-01", 0)
        r = self.post(2, "T3P-298", "AV-12", 60)
        self.assertEqual(len(r.data["alertas"]), 1)
        alerta = Alerta.objects.get()
        self.assertEqual(alerta.detalle["velocidad_necesaria_kmh"], 408.0)
        self.assertFalse(Infraccion.objects.exists())

    def test_regresion_auto_muy_rapido_es_infraccion(self):
        """3 km en 110 s (94.7 km/h): antes se tomaba como captura imposible (prueba en vivo, 16/10)."""
        self.post(1, "ABC-123", "AV-01", 0)
        r = self.post(2, "ABC-123", "AV-08", 110)
        self.assertEqual((len(r.data["infracciones"]), len(r.data["alertas"])), (1, 0))

    def test_evento_repetido_no_duplica(self):
        self.post(1, "VBD-001", "AV-01", 0)
        self.post(2, "VBD-001", "AV-08", 120)
        r = self.post(2, "VBD-001", "AV-08", 120)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["duplicado"])
        self.assertEqual((Captura.objects.count(), Infraccion.objects.count()), (2, 1))

    def test_misma_captura_con_otro_id_no_duplica(self):
        """Regresión (16/10/2026): subir dos veces la misma foto creaba dos infracciones para un solo paso."""
        self.post(1, "VBD-001", "AV-01", 0)
        self.post(2, "VBD-001", "AV-08", 120)
        r = self.post(3, "VBD-001", "AV-08", 120)  # mismo paso, otro evento_id
        self.assertTrue(r.data["duplicado"])
        self.assertEqual((Captura.objects.count(), Infraccion.objects.count()), (2, 1))
        self.assertEqual(self.post(4, "VBD-001", "AV-08", 125).status_code, 201)  # 5 s después sí es otra captura

    def test_hora_sin_zona_se_toma_como_hora_de_lima(self):
        datos = evento(1, "ABC-123", "AV-01", 0)
        datos["timestamp"] = "2026-10-15T08:42:00"
        self.worker.post("/api/eventos/", datos, format="json")
        self.assertEqual(timezone.localtime(Captura.objects.get().timestamp).hour, 8)

    def test_camara_inexistente_es_rechazada(self):
        r = self.post(1, "ABC-123", "XX-99", 0)
        self.assertEqual(r.status_code, 400)
        self.assertIn("camara_id", r.data)

    # --- Permisos ----------------------------------------------------------------------
    def test_sin_token_no_puede_reportar(self):
        self.assertEqual(APIClient().post("/api/eventos/", evento(1, "ABC-123", "AV-01", 0), format="json").status_code, 401)

    def test_usuario_sin_rol_no_puede_reportar_ni_validar(self):
        c = APIClient()
        c.force_authenticate(self.ciudadano)
        self.assertEqual(c.post("/api/eventos/", evento(1, "ABC-123", "AV-01", 0), format="json").status_code, 403)
        self.post(1, "VBD-001", "AV-01", 0)
        self.post(2, "VBD-001", "AV-08", 120)
        inf = Infraccion.objects.get()
        self.assertEqual(c.post(f"/api/infracciones/{inf.pk}/validar/", {"decision": "aprobar"}).status_code, 403)

    def test_worker_no_puede_ver_infracciones_ni_alertas(self):
        self._infraccion()
        self.assertEqual(self.worker.get("/api/infracciones/").status_code, 403)
        self.assertEqual(self.worker.get("/api/alertas/").status_code, 403)

    # --- Validación humana y papeleta --------------------------------------------------
    def _infraccion(self):
        self.post(1, "VBD-001", "AV-01", 0)
        self.post(2, "VBD-001", "AV-08", 120)
        return Infraccion.objects.get()

    def test_aprobar_con_placa_corregida_emite_papeleta(self):
        inf = self._infraccion()
        r = self.val.post(f"/api/infracciones/{inf.pk}/validar/", {"decision": "aprobar", "placa_corregida": "V8D-001"})
        self.assertEqual(r.status_code, 200)
        p = Papeleta.objects.get()
        self.assertEqual((p.placa, p.numero), ("V8D001", f"FP-{timezone.localdate().year}-000001"))
        inf.refresh_from_db()
        self.assertEqual((inf.estado, inf.placa), ("emitida", "V8D001"))

    def test_rechazar_exige_motivo(self):
        inf = self._infraccion()
        r = self.val.post(f"/api/infracciones/{inf.pk}/validar/", {"decision": "rechazar"})
        self.assertEqual(r.status_code, 409)
        r = self.val.post(f"/api/infracciones/{inf.pk}/validar/", {"decision": "rechazar", "motivo": "Placa ilegible"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["papeleta"])
        self.assertFalse(Papeleta.objects.exists())

    def test_no_se_valida_dos_veces(self):
        inf = self._infraccion()
        self.val.post(f"/api/infracciones/{inf.pk}/validar/", {"decision": "aprobar"})
        r = self.val.post(f"/api/infracciones/{inf.pk}/validar/", {"decision": "aprobar"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Papeleta.objects.count(), 1)

    def test_numeracion_correlativa_de_papeletas(self):
        for n, placa in ((1, "AAA-111"), (3, "BBB-222")):
            self.post(n, placa, "AV-01", 0)
            self.post(n + 1, placa, "AV-08", 120)
        for inf in Infraccion.objects.order_by("pk"):
            self.val.post(f"/api/infracciones/{inf.pk}/validar/", {"decision": "aprobar"})
        anio = timezone.localdate().year
        self.assertEqual(sorted(Papeleta.objects.values_list("numero", flat=True)),
                         [f"FP-{anio}-000001", f"FP-{anio}-000002"])

    # --- Consultas ---------------------------------------------------------------------
    def test_listado_filtra_por_estado_y_placa(self):
        self._infraccion()
        r = self.val.get("/api/infracciones/?estado=en_validacion&placa=vbd-001")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["analisis"]["v_conservadora"], 87.1)
        self.assertEqual(self.val.get("/api/infracciones/?estado=emitida").data["count"], 0)

    def test_grafo(self):
        r = self.val.get("/api/grafo/")
        self.assertEqual((len(r.data["nodos"]), len(r.data["aristas"])), (6, 6))
