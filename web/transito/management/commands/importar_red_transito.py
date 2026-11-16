import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from transito.servicios import importar_red


class Command(BaseCommand):
    help = "Carga las cámaras públicas de tránsito y sus tramos desde data/red_transito.json."

    def add_arguments(self, parser):
        parser.add_argument("ruta", nargs="?", default=str(settings.FOTOPAPELETA["RED_TRANSITO_JSON"]))

    def handle(self, *args, **o):
        n, m = importar_red(json.loads(Path(o["ruta"]).read_text(encoding="utf-8")))
        self.stdout.write(self.style.SUCCESS(f"{n} cámaras de tránsito y {m} tramos cargados."))
