"""Pantallas web: panel (validación, papeletas, laboratorio, configuración) y portal ciudadano."""
import io
import json
import tempfile
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from camaras.models import Camara
from camaras.servicios import importar_red
from infracciones.models import Alerta, Captura, Infraccion
from infracciones.servicios import registrar_evento
from validacion.models import Papeleta, SolicitudRevision

from .models import ParametrosSistema

T0 = timezone.make_aware(datetime(2026, 10, 15, 8, 42, 0))


def evento(n, placa, camara, segundos):
    return {"evento_id": f"EV-WEB-{n:04d}", "placa": placa, "placa_confianza": 0.9, "lecturas_votadas": 8,
            "lecturas_totales": 8, "camara_id": camara, "timestamp": T0 + timedelta(seconds=segundos), "evidencia": []}


class PantallasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        importar_red(json.loads(settings.FOTOPAPELETA["GRAFO_JSON"].read_text(encoding="utf-8")))
        call_command("crear_roles", "--worker", "worker-web", stdout=io.StringIO())
        cls.admin = User.objects.create_user("admin1", password="x", first_name="Tonny", last_name="Hinostroza",
                                             email="admin1@utp.edu.pe")
        cls.admin.groups.add(Group.objects.get(name="administrador"))
        cls.validador = User.objects.create_user("val1", password="x", email="val1@utp.edu.pe")
        cls.validador.groups.add(Group.objects.get(name="validador"))
        cls.worker = User.objects.get(username="worker-web")
        registrar_evento(evento(1, "VBD-001", "AV-01", 0))
        registrar_evento(evento(2, "VBD-001", "AV-08", 120))     # 87.1 km/h -> infracción
        registrar_evento(evento(3, "XYZ-789", "AV-01", 0))
        registrar_evento(evento(4, "XYZ-789", "AV-08", 45))      # 240 km/h -> alerta
        cls.inf = Infraccion.objects.get()

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def aprobar(self, placa=""):
        self.entrar(self.validador)
        return self.client.post(f"/panel/validacion/{self.inf.pk}/decidir/", {"decision": "aprobar", "placa_corregida": placa})

    # --- Acceso -------------------------------------------------------------------------
    def test_todas_las_pantallas_del_panel_cargan(self):
        self.entrar(self.admin)
        for url in ["/panel/validacion/", f"/panel/validacion/{self.inf.pk}/", "/panel/infracciones/",
                    f"/panel/infracciones/{self.inf.pk}/", "/panel/papeletas/", "/panel/camaras/", "/panel/camaras/?camara=AV-01",
                    "/panel/captura/", "/panel/captura/lecturas/", "/panel/captura/celular/", "/panel/laboratorio/",
                    "/panel/reportes/", "/panel/reportes/?periodo=hoy", "/panel/configuracion/", "/panel/usuarios/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_panel_exige_sesion(self):
        r = self.client.get("/panel/validacion/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/panel/ingresar/", r["Location"])

    def test_ingreso_con_correo(self):
        r = self.client.post("/panel/ingresar/", {"username": "val1@utp.edu.pe", "password": "x"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.validador.pk)

    def test_worker_no_entra_al_panel(self):
        self.entrar(self.worker)
        r = self.client.get("/panel/infracciones/")
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "Tu rol no permite", status_code=403)

    # --- Validación (A4) ----------------------------------------------------------------
    def test_cola_muestra_la_infraccion_y_su_analisis(self):
        self.entrar(self.validador)
        r = self.client.get("/panel/validacion/")
        self.assertContains(r, self.inf.codigo)
        self.assertContains(r, "87.1 km/h")      # velocidad conservadora con punto decimal
        self.assertContains(r, "+27.1 km/h")

    def test_aprobar_con_correccion_emite_papeleta(self):
        r = self.aprobar("V8D-001")
        self.assertEqual(r.status_code, 302)
        p = Papeleta.objects.get()
        self.assertEqual((p.placa, p.infraccion.estado), ("V8D001", "emitida"))
        r = self.client.get(r["Location"])
        self.assertContains(r, "No hay infracciones pendientes")

    def test_rechazar_sin_comentario_no_cambia_el_estado(self):
        self.entrar(self.validador)
        self.client.post(f"/panel/validacion/{self.inf.pk}/decidir/", {"decision": "rechazar"})
        self.inf.refresh_from_db()
        self.assertEqual(self.inf.estado, "en_validacion")

    def test_rechazar_guarda_motivo_y_comentario(self):
        self.entrar(self.validador)
        self.client.post(f"/panel/validacion/{self.inf.pk}/decidir/",
                         {"decision": "rechazar", "motivo": "Error de hora en una cámara", "comentario": "AV-08 adelantada"})
        self.inf.refresh_from_db()
        self.assertEqual(self.inf.estado, "rechazada")
        self.assertEqual(self.inf.validaciones.get().motivo, "Error de hora en una cámara: AV-08 adelantada")

    def test_escalar_deja_la_infraccion_en_la_cola(self):
        self.entrar(self.validador)
        self.client.post(f"/panel/validacion/{self.inf.pk}/decidir/", {"decision": "escalar", "motivo": "¿Vehículo oficial?"})
        self.inf.refresh_from_db()
        self.assertEqual((self.inf.estado, self.inf.escalada), ("en_validacion", True))

    # --- Papeletas -----------------------------------------------------------------------
    def test_solo_el_administrador_anula(self):
        self.aprobar()
        p = Papeleta.objects.get()
        r = self.client.post(f"/panel/papeletas/{p.numero}/anular/", {"motivo": "Revisión aceptada"})
        self.assertEqual(r.status_code, 403)
        self.entrar(self.admin)
        self.client.post(f"/panel/papeletas/{p.numero}/anular/", {"motivo": "Revisión aceptada"})
        p.refresh_from_db()
        self.assertEqual((p.estado, p.infraccion.estado, p.anulada_por), ("anulada", "anulada", self.admin))

    def test_auditoria_reune_todo_el_ciclo(self):
        self.aprobar("V8D-001")
        self.entrar(self.admin)
        r = self.client.get(f"/panel/infracciones/{self.inf.pk}/")
        for texto in ["Detectada", "Captura adicional", "Analizada", "Aprobada", "Placa corregida a V8D001", "Emitida"]:
            self.assertContains(r, texto)

    # --- Infracciones, búsqueda y exportación --------------------------------------------
    def test_filtros_y_busqueda_global(self):
        self.entrar(self.admin)
        self.assertContains(self.client.get("/panel/infracciones/?q=VBD"), self.inf.codigo)
        self.assertContains(self.client.get("/panel/infracciones/?estado=emitida"), "Ninguna infracción coincide")
        self.assertRedirects(self.client.get(f"/panel/buscar/?q={self.inf.codigo}"), f"/panel/infracciones/{self.inf.pk}/")
        self.assertRedirects(self.client.get("/panel/buscar/?q=av-08"), "/panel/camaras/?camara=AV-08")

    def test_exportar_csv(self):
        self.entrar(self.admin)
        r = self.client.get("/panel/infracciones/exportar/")
        filas = r.content.decode("utf-8-sig").strip().splitlines()
        self.assertEqual(len(filas), 2)
        self.assertIn("VBD001", filas[1])

    def test_alerta_se_marca_revisada(self):
        self.entrar(self.validador)
        a = Alerta.objects.get()
        self.client.post(f"/panel/alertas/{a.pk}/revisada/", {"volver": "/panel/"})
        a.refresh_from_db()
        self.assertTrue(a.revisada)

    # --- Red y laboratorio ---------------------------------------------------------------
    def test_laboratorio_a_estrella_y_comparacion(self):
        self.entrar(self.validador)
        base = {"algoritmo": "astar", "origen": "AV-01", "destino": "PN-04", "peso": "km"}
        r1 = self.client.post("/panel/laboratorio/ejecutar/", {**base, "heuristica": "on"})
        r2 = self.client.post("/panel/laboratorio/ejecutar/", {**base, "heuristica": "off"})
        self.assertContains(r1, "AV-01 → AV-08 → AV-12 → PN-04")
        self.assertContains(r2, "12.8 km")
        corridas = self.client.session["lab_corridas"]
        self.assertEqual(len(corridas), 2)
        self.assertEqual(corridas[0]["costo"], corridas[1]["costo"])           # mismo costo
        self.assertLessEqual(corridas[1]["explorados"], corridas[0]["explorados"])  # la heurística explora menos

    def test_laboratorio_dfs_sin_ruta(self):
        self.entrar(self.validador)
        r = self.client.post("/panel/laboratorio/ejecutar/", {"algoritmo": "dfs", "origen": "AV-15", "destino": "PN-04", "max_prof": 1})
        self.assertContains(r, "No existe ruta entre AV-15 y PN-04")

    def test_velocidad_por_tramo_y_captura_imposible(self):
        self.entrar(self.validador)
        r = self.client.post("/panel/laboratorio/velocidad/", {"cam_a": "AV-01", "hora_a": "08:42:00", "cam_b": "AV-08", "hora_b": "08:44:00"})
        self.assertContains(r, "87.1 km/h")
        self.assertContains(r, "Infracción")
        r = self.client.post("/panel/laboratorio/velocidad/", {"cam_a": "AV-01", "hora_a": "08:42:00", "cam_b": "AV-08", "hora_b": "08:42:45"})
        self.assertContains(r, "captura físicamente imposible")

    def test_agregar_camara_valida_la_red(self):
        self.entrar(self.admin)
        datos = {"codigo": "AV-21", "nombre": "Av. Brasil Sur", "x_km": 2.9, "y_km": -6.0, "vecino": "AV-12",
                 "km": 1.0, "minutos": 2, "limite_kmh": 60}
        self.client.post("/panel/camaras/", datos)  # 2.4 km en línea recta > 1.0 km del tramo: A* dejaría de ser exacto
        self.assertFalse(Camara.objects.filter(codigo="AV-21").exists())
        self.client.post("/panel/camaras/", {**datos, "km": 3.0})
        self.assertTrue(Camara.objects.filter(codigo="AV-21").exists())

    def test_validador_no_agrega_camaras(self):
        self.entrar(self.validador)
        r = self.client.post("/panel/camaras/", {"codigo": "AV-22"})
        self.assertEqual(r.status_code, 403)

    # --- Configuración ---------------------------------------------------------------------
    def test_parametros_se_aplican_a_los_nuevos_eventos(self):
        self.entrar(self.admin)
        r = self.client.post("/panel/configuracion/", {"tolerancia_kmh": 5, "error_reloj_s": 2, "k_vecindario": 2,
                                                       "velocidad_max_plausible_kmh": 250})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ParametrosSistema.objects.get().actualizado_por, self.admin)
        registrar_evento(evento(5, "QWE-456", "AV-01", 0))
        registrar_evento(evento(6, "QWE-456", "AV-08", 45))   # 240 km/h < 250: ahora es infracción, no alerta
        self.assertTrue(Infraccion.objects.filter(placa="QWE456").exists())

    def test_validador_no_cambia_parametros(self):
        self.entrar(self.validador)
        r = self.client.post("/panel/configuracion/", {"tolerancia_kmh": 0, "error_reloj_s": 0, "k_vecindario": 1,
                                                       "velocidad_max_plausible_kmh": 100})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(ParametrosSistema.objects.exists())

    # --- Portal ciudadano -------------------------------------------------------------------
    def test_portal_publico(self):
        for url in ["/", "/como-funciona/", "/ayuda/", "/mis-consultas/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_consulta_solo_muestra_papeletas_emitidas(self):
        self.assertContains(self.client.get("/resultados/?placa=VBD-001"), "No hay papeletas registradas")
        self.aprobar()
        self.client.logout()
        r = self.client.get("/resultados/?placa=vbd001")
        self.assertContains(r, "1 papeleta encontrada")
        self.assertContains(r, Papeleta.objects.get().numero)

    def test_placa_invalida(self):
        self.assertContains(self.client.get("/resultados/?placa=12"), "Escribe una placa válida")

    def test_detalle_e_impresion(self):
        self.aprobar()
        self.client.logout()
        p = Papeleta.objects.get()
        r = self.client.get(f"/papeleta/{p.numero}/")
        self.assertContains(r, "Trayectoria reconstruida")
        self.assertContains(r, "87.1")
        self.assertEqual(self.client.get(f"/papeleta/{p.numero}/imprimir/").status_code, 200)
        self.assertEqual(self.client.get("/papeleta/FP-2026-999999/").status_code, 404)

    def test_solicitud_de_revision(self):
        self.aprobar()
        self.client.logout()
        p = Papeleta.objects.get()
        url = f"/papeleta/{p.numero}/revision/"
        r = self.client.post(url, {"motivo": "La placa fue mal leída", "descripcion": "Es V8D-001", "correo": "c@correo.com"})
        self.assertContains(r, "Debes aceptar la declaración")
        r = self.client.post(url, {"motivo": "La placa fue mal leída", "descripcion": "Es V8D-001", "correo": "c@correo.com",
                                   "declaracion": "on"})
        s = SolicitudRevision.objects.get()
        self.assertContains(r, s.codigo)
        p.refresh_from_db()
        self.assertEqual((p.estado, p.infraccion.estado), ("en_revision", "en_revision"))
        r = self.client.post(url, {"motivo": "Otro", "descripcion": "x", "correo": "c@correo.com", "declaracion": "on"})
        self.assertContains(r, "no admite una nueva revisión")


class GenerarDemoTest(TestCase):
    """El comando de datos de demostración usa el flujo real y se puede deshacer sin tocar datos reales."""

    @classmethod
    def setUpTestData(cls):
        importar_red(json.loads(settings.FOTOPAPELETA["GRAFO_JSON"].read_text(encoding="utf-8")))
        call_command("crear_roles", stdout=io.StringIO())
        registrar_evento(evento(1, "VBD-001", "AV-01", 0))  # un dato real que no debe borrarse
        registrar_evento(evento(2, "VBD-001", "AV-08", 120))

    def test_genera_decide_y_borra(self):
        call_command("generar_demo", "--vehiculos", "60", "--decidir", "--pendientes", "3", "--sin-imagenes", stdout=io.StringIO())
        sim = Infraccion.objects.filter(capturas__evento_id__startswith="SIM-").distinct()
        self.assertGreater(sim.count(), 3)
        self.assertEqual(sim.filter(estado="en_validacion", escalada=False).count(), 3)
        self.assertTrue(Papeleta.objects.exists())
        self.assertLess(max(sim.values_list("creada", flat=True)), timezone.now())  # fechas del momento simulado
        call_command("generar_demo", "--borrar", stdout=io.StringIO())
        self.assertFalse(Infraccion.objects.filter(capturas__evento_id__startswith="SIM-").exists())
        self.assertEqual(Infraccion.objects.get().placa, "VBD001")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="fp_test_media_"))  # no ensuciar web/media
class SubirEvidenciaTest(TestCase):
    """«Subir evidencia»: el análisis de ML se simula (las pruebas no dependen de la GPU ni de los pesos)."""

    @classmethod
    def setUpTestData(cls):
        importar_red(json.loads(settings.FOTOPAPELETA["GRAFO_JSON"].read_text(encoding="utf-8")))
        call_command("crear_roles", stdout=io.StringIO())
        cls.admin = User.objects.create_user("admin2", password="x")
        cls.admin.groups.add(Group.objects.get(name="administrador"))
        cls.validador = User.objects.create_user("val2", password="x")
        cls.validador.groups.add(Group.objects.get(name="validador"))

    def setUp(self):
        self.client.force_login(self.admin)

    @staticmethod
    def foto(nombre="auto.jpg"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image as Img
        b = io.BytesIO()
        Img.new("RGB", (64, 32), "white").save(b, "JPEG")
        return SimpleUploadedFile(nombre, b.getvalue(), content_type="image/jpeg")

    def subir(self, camara, hora, **extra):
        return self.client.post("/panel/subir/", {"camara": camara, "fecha_hora": hora, "archivo": self.foto(), **extra})

    def test_dos_fotos_generan_la_infraccion(self):
        from unittest import mock

        def falso(ruta, camara_id, inicio, carpeta):  # lo que devolvería el pipeline del worker
            return [{"evento_id": "EV-X", "placa": "V8D-001", "placa_confianza": 0.8, "lecturas_votadas": 1,
                     "lecturas_totales": 1, "camara_id": camara_id, "timestamp": inicio.isoformat(), "evidencia": []}], \
                   {"dispositivo": "CPU", "cuadros": 1}
        with mock.patch("infracciones.subida.analizar", side_effect=falso):
            r1 = self.subir("AV-01", "2026-10-14T09:30:00")
            r2 = self.subir("AV-08", "2026-10-14T09:32:00")
        self.assertContains(r1, "Primera captura reciente de esta placa")
        self.assertContains(r2, "87.1 km/h")
        inf = Infraccion.objects.get()
        self.assertEqual((inf.placa, inf.analisis.ruta), ("V8D001", ["AV-01", "AV-08"]))
        self.assertTrue(all(c.evento_id.startswith("WEB-") for c in inf.capturas.all()))

    def test_placa_escrita_a_mano(self):
        r = self.client.post("/panel/subir/", {"camara": "AV-01", "fecha_hora": "2026-10-14T09:30:00", "placa_manual": "abc-123"})
        self.assertContains(r, "Placa escrita a mano")
        c = Captura.objects.get()
        self.assertEqual((c.placa, c.modelo["origen"][:6]), ("ABC123", "manual"))

    def test_sin_entorno_de_ml_avisa(self):
        from unittest import mock
        from infracciones.subida import SinEntornoML
        with mock.patch("infracciones.subida.analizar", side_effect=SinEntornoML("Falta el entorno de ML (torch).")):
            r = self.subir("AV-01", "2026-10-14T09:30:00")
        self.assertContains(r, "Falta el entorno de ML")
        self.assertContains(r, "escribir la placa a mano")

    def test_validaciones_del_formulario(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self.client.post("/panel/subir/", {"camara": "AV-01", "archivo": SimpleUploadedFile("x.exe", b"MZ")})
        self.assertContains(r, "Sube una foto (JPG, PNG) o un video")
        r = self.client.post("/panel/subir/", {"camara": "AV-01"})
        self.assertContains(r, "Sube una foto o un video, o escribe la placa a mano")
        r = self.subir("AV-01", "2099-01-01T00:00:00")
        self.assertContains(r, "no puede estar en el futuro")

    def test_placa_no_leida_se_escribe_a_mano_desde_su_recorte(self):
        """El detector vio una placa que el OCR no leyó: se muestra el recorte y una persona la registra."""
        import re
        from unittest import mock

        import numpy as np

        def falso(ruta, camara_id, inicio, carpeta):
            no_leida = {"recorte": np.full((40, 100, 3), 200, np.uint8), "cuadro": np.zeros((480, 640, 3), np.uint8),
                        "ancho": 100, "ts": inicio, "lecturas": 4, "motivo": "El OCR no obtuvo una lectura válida",
                        "sugerencia": "", "conf_detector": 0.83}
            return [], {"dispositivo": "CPU", "cuadros": 30, "no_leidas": [no_leida]}
        with mock.patch("infracciones.subida.analizar", side_effect=falso):
            r = self.subir("AV-01", "2026-10-14T09:30:00")
        self.assertContains(r, "1 placa detectada que el OCR no pudo leer")
        token = re.search(r"/panel/subir/no-leida/([0-9a-f]{16})/", r.content.decode()).group(1)
        url = f"/panel/subir/no-leida/{token}/"
        self.assertContains(self.client.post(url, {"placa": "ACO"}), "Usa el formato ABC-123")
        r = self.client.post(url, {"placa": "aco-484"})
        self.assertContains(r, "ACO-484")
        c = Captura.objects.get()
        self.assertEqual((c.placa, c.camara_id, c.lecturas_totales), ("ACO484", "AV-01", 1))
        self.assertTrue(c.modelo["origen"].startswith("placa escrita por una persona"))
        self.assertEqual(c.evidencias.exclude(archivo="").count(), 2)  # cuadro y recorte como evidencia
        self.assertContains(self.client.post(url, {"placa": "ACO-484"}), "ya se registró")
        self.assertContains(self.client.post("/panel/subir/no-leida/../../x/", {"placa": "ACO-484"}), "", status_code=404)

    def test_validador_no_sube_evidencia(self):
        self.client.force_login(self.validador)
        self.assertEqual(self.client.get("/panel/subir/").status_code, 403)


class TutorialTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        importar_red(json.loads(settings.FOTOPAPELETA["GRAFO_JSON"].read_text(encoding="utf-8")))
        call_command("crear_roles", stdout=io.StringIO())
        cls.admin = User.objects.create_user("admin3", password="x")
        cls.admin.groups.add(Group.objects.get(name="administrador"))
        cls.validador = User.objects.create_user("val3", password="x")
        cls.validador.groups.add(Group.objects.get(name="validador"))

    @staticmethod
    def datos(r):
        html = r.content.decode()
        inicio = html.index('<script id="datos-tutorial" type="application/json">') + len('<script id="datos-tutorial" type="application/json">')
        return json.loads(html[inicio:html.index("</script>", inicio)])

    def test_primera_vez_bienvenida_y_luego_no_se_repite(self):
        self.client.force_login(self.validador)
        d = self.datos(self.client.get("/panel/", follow=True))     # /panel/ lleva a Infracciones
        self.assertTrue(d["primera"])
        self.assertEqual(d["auto"][0]["titulo"], "Bienvenido a FotoPapeleta")
        self.client.post("/panel/tutorial/visto/", {"pantalla": "infracciones", "primera": "1"})
        self.assertEqual(self.datos(self.client.get("/panel/infracciones/"))["auto"], [])
        d = self.datos(self.client.get("/panel/papeletas/"))     # otra pantalla: su propia guía, sin bienvenida
        self.assertFalse(d["primera"])
        self.assertTrue(d["auto"])
        self.assertTrue(d["manual"])                                # el botón «?» siempre tiene pasos

    def test_los_pasos_respetan_los_permisos(self):
        self.client.force_login(self.validador)
        tours = [p["tour"] for p in self.datos(self.client.get("/panel/camaras/"))["manual"]]
        self.assertNotIn("agregar", tours)
        self.client.force_login(self.admin)
        tours = [p["tour"] for p in self.datos(self.client.get("/panel/camaras/"))["manual"]]
        self.assertIn("agregar", tours)

    def test_reiniciar(self):
        self.client.force_login(self.validador)
        self.client.post("/panel/tutorial/visto/", {"pantalla": "resumen", "primera": "1"})
        self.client.post("/panel/tutorial/reiniciar/")
        self.assertTrue(self.datos(self.client.get("/panel/", follow=True))["primera"])

    def test_cada_paso_apunta_a_un_elemento_de_la_pagina(self):
        """Evita guías rotas: todo data-tour de los pasos existe en su pantalla (o en la barra común)."""
        from .tutorial import PASOS
        self.client.force_login(self.admin)
        rutas = {"validacion": "/panel/validacion/", "infracciones": "/panel/infracciones/",
                 "papeletas": "/panel/papeletas/", "camaras": "/panel/camaras/", "captura": "/panel/captura/",
                 "subir": "/panel/subir/", "laboratorio": "/panel/laboratorio/", "reportes": "/panel/reportes/",
                 "configuracion": "/panel/configuracion/", "usuarios": "/panel/usuarios/", "transito": "/panel/transito/"}
        import json as _j
        from transito.servicios import importar_red as importar_transito
        importar_transito(_j.loads(settings.FOTOPAPELETA["RED_TRANSITO_JSON"].read_text(encoding="utf-8")))
        registrar_evento(evento(1, "VBD-001", "AV-01", 0))
        registrar_evento(evento(2, "VBD-001", "AV-08", 120))  # para que Validación tenga una infracción
        for pantalla, url in rutas.items():
            html = self.client.get(url).content.decode()
            for tour, *_ in PASOS[pantalla]:
                with self.subTest(pantalla=pantalla, tour=tour):
                    self.assertIn(f'data-tour="{tour}"', html)
