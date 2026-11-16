import hashlib
import json
from datetime import datetime
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from infracciones.models import Evidencia
from infracciones.servicios import registrar_evento


class Command(BaseCommand):
    help = ("Pasa por el mismo flujo de la API los eventos de un archivo JSON (p. ej. demo/salida/eventos.json) "
            "y adjunta sus imágenes de evidencia.")

    def add_arguments(self, parser):
        parser.add_argument("ruta", help="eventos.json generado por la demo o por el worker")
        parser.add_argument("--evidencia", help="carpeta con las imágenes (por defecto: <ruta>/../evidencia)")

    def handle(self, *args, **opts):
        ruta = Path(opts["ruta"])
        if not ruta.exists():
            raise CommandError(f"No existe {ruta}")
        carpeta = Path(opts["evidencia"]) if opts["evidencia"] else ruta.parent / "evidencia"
        eventos = sorted(json.loads(ruta.read_text(encoding="utf-8")), key=lambda e: e["timestamp"])
        for e in eventos:
            e = {**e, "timestamp": datetime.fromisoformat(e["timestamp"])}
            captura, resumen, creada = registrar_evento(e)
            if not creada:
                self.stdout.write(f"{e['evento_id']}: ya existía, se omite")
                continue
            for ev in Evidencia.objects.filter(captura=captura):
                img = carpeta / ev.nombre
                if img.exists():
                    with open(img, "rb") as f:
                        ev.sha256 = hashlib.sha256(f.read()).hexdigest()
                        f.seek(0)
                        ev.archivo.save(ev.nombre, File(f), save=True)
            partes = [f"{len(resumen['infracciones'])} infracción(es)", f"{len(resumen['sin_infraccion'])} tramo(s) sin infracción",
                      f"{len(resumen['alertas'])} alerta(s)"]
            self.stdout.write(f"{e['evento_id']} {captura.placa_formateada} @ {captura.camara_id}: " + ", ".join(partes))
        self.stdout.write(self.style.SUCCESS(f"{len(eventos)} eventos procesados."))
