"""Calcula los tramos de la red de fiscalización por calles reales (OSRM) a partir de la ubicación de las cámaras.

    python manage.py calcular_tramos            # data/camaras_reales.json -> data/grafo_camaras_real.json
    python manage.py importar_red ../data/grafo_camaras_real.json
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import grafo
from camaras.osrm import calcular_tramos


class Command(BaseCommand):
    help = "Tramos por calles reales (OSRM) sin que la distancia del grafo supere nunca la real (a favor del conductor)."

    def add_arguments(self, parser):
        parser.add_argument("--entrada", default=str(settings.RAIZ_REPO / "data" / "camaras_reales.json"))
        parser.add_argument("--salida", default=str(settings.RAIZ_REPO / "data" / "grafo_camaras_real.json"))
        parser.add_argument("--radio", type=float, default=0.2, help="km: una ruta que pasa a esta distancia de otra cámara pasa por ella")

    def handle(self, *args, **o):
        entrada = json.loads(Path(o["entrada"]).read_text(encoding="utf-8"))
        nodos = entrada["nodos"]
        self.stdout.write(f"Distancias reales entre {len(nodos)} cámaras (OSRM):")
        aristas, verificacion = calcular_tramos(nodos, radio_km=o["radio"], informar=self.stdout.write)
        datos = {"version": "real", "nota": ("Red de fiscalización con ubicaciones de OpenStreetMap y tramos por calles reales "
                                             "(OSRM). Generada por calcular_tramos; no editar a mano."),
                 "nodos": nodos, "aristas": aristas}
        errores = grafo.validar(datos)
        if errores:
            raise CommandError("; ".join(errores))
        Path(o["salida"]).write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        self.stdout.write("Tramos:")
        for a in aristas:
            self.stdout.write(f"  {a['de']} - {a['a']}: {a['km']} km · {a['min']} min · {a['limite_kmh']} km/h · {a['fuente']}")
        peor = max(v["km_grafo"] - v["km_real"] for v in verificacion)
        self.stdout.write(f"Verificación: en los {len(verificacion)} pares, distancia del grafo <= distancia real "
                          f"(mayor diferencia {peor:+.2f} km).")
        self.stdout.write(self.style.SUCCESS(f"Guardado en {o['salida']}"))
