"""Red de fiscalización por calles reales: la distancia del grafo nunca supera la real (a favor del conductor)."""
import json

from django.conf import settings
from django.test import TestCase

import grafo
from camaras.models import Tramo
from camaras.osrm import calcular_tramos, distancia_a_linea_km
from camaras.servicios import importar_red

# Tres cámaras en línea (A - B - C, 1 km entre cada una) y D al costado de B.
NODOS = {"A": {"lat": 0.0, "lon": 0.0}, "B": {"lat": 0.0, "lon": 0.009}, "C": {"lat": 0.0, "lon": 0.018},
         "D": {"lat": 0.009, "lon": 0.009}}
REAL = {("A", "B"): 1.0, ("B", "C"): 1.0, ("A", "C"): 2.0, ("B", "D"): 1.0, ("A", "D"): 1.6, ("C", "D"): 1.6}


def osrm_falso(a, b):
    """Ruta en línea recta entre los dos puntos; distancia de la tabla REAL."""
    codigo = {(v["lat"], v["lon"]): k for k, v in NODOS.items()}
    par = tuple(sorted((codigo[(a["lat"], a["lon"])], codigo[(b["lat"], b["lon"])])))
    return REAL[par], REAL[par] * 2, [[a["lat"], a["lon"]], [b["lat"], b["lon"]]]


class RedRealTest(TestCase):
    def test_no_se_une_un_par_cuya_ruta_pasa_por_otra_camara(self):
        aristas, _ = calcular_tramos(NODOS, consultar=osrm_falso, informar=lambda *a: None)
        pares = {tuple(sorted((a["de"], a["a"]))) for a in aristas}
        self.assertNotIn(("A", "C"), pares)  # pasa por B: se evalúa A-B y B-C
        self.assertIn(("A", "B"), pares)

    def test_la_distancia_del_grafo_nunca_supera_la_real(self):
        """A-D real = 1.6 km, pero por el grafo sería A-B-D = 2.0 km: se agrega el tramo directo."""
        aristas, verificacion = calcular_tramos(NODOS, consultar=osrm_falso, informar=lambda *a: None)
        self.assertIn(("A", "D"), {tuple(sorted((a["de"], a["a"]))) for a in aristas})
        for v in verificacion:
            self.assertLessEqual(v["km_grafo"], v["km_real"] + 0.05, v["par"])

    def test_distancia_a_linea(self):
        self.assertAlmostEqual(distancia_a_linea_km([0.0, 0.009], [[0.0, 0.0], [0.0, 0.018]]), 0.0, places=3)
        self.assertAlmostEqual(distancia_a_linea_km([0.009, 0.009], [[0.0, 0.0], [0.0, 0.018]]), 0.995, places=2)

    def test_red_real_del_repositorio(self):
        """data/grafo_camaras_real.json es válido, conexo y cumple la verificación por par."""
        datos = json.loads((settings.RAIZ_REPO / "data" / "grafo_camaras_real.json").read_text(encoding="utf-8"))
        self.assertEqual(grafo.validar(datos), [])
        g = grafo.construir(datos)
        for a in datos["nodos"]:
            for b in datos["nodos"]:
                self.assertNotEqual(grafo.a_estrella(g, a, b).costo, float("inf"))
        self.assertTrue(all(a["fuente"].startswith("OSRM") and len(a["geometria"]) > 2 for a in datos["aristas"]))

    def test_importar_reemplaza_los_tramos_anteriores(self):
        importar_red(json.loads(settings.FOTOPAPELETA["GRAFO_JSON"].read_text(encoding="utf-8")))
        self.assertEqual(Tramo.objects.count(), 6)
        importar_red(json.loads((settings.RAIZ_REPO / "data" / "grafo_camaras_real.json").read_text(encoding="utf-8")))
        self.assertEqual(Tramo.objects.count(), 13)
        self.assertFalse(Tramo.objects.filter(fuente="manual").exists())
