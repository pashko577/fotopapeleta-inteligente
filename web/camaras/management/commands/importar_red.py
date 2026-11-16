import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from camaras.servicios import construir_grafo, importar_red


class Command(BaseCommand):
    help = "Carga cámaras y tramos desde un JSON de red (por defecto data/grafo_camaras.json)."

    def add_arguments(self, parser):
        parser.add_argument("ruta", nargs="?", default=str(settings.FOTOPAPELETA["GRAFO_JSON"]))

    def handle(self, *args, **opts):
        ruta = Path(opts["ruta"])
        if not ruta.exists():
            raise CommandError(f"No existe {ruta}")
        try:
            n, a = importar_red(json.loads(ruta.read_text(encoding="utf-8")))
        except ValueError as e:
            raise CommandError(f"Red inválida: {e}")
        _, _, version = construir_grafo()
        self.stdout.write(self.style.SUCCESS(f"{n} cámaras y {a} tramos importados (versión de la red {version})."))
