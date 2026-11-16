"""Mide el tráfico de las cámaras públicas en ciclos (es el «worker» del módulo de tránsito).

    python manage.py monitorear_transito                 # sin fin, una ronda cada 2 minutos
    python manage.py monitorear_transito --ciclos 1      # una sola ronda
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from transito.models import CamaraTransito, Medicion
from transito.servicios import StreamNoDisponible, congestion, medir


class Command(BaseCommand):
    help = "Cuenta vehículos en las cámaras públicas de tránsito con YOLOv8 (no lee placas)."

    def add_arguments(self, parser):
        parser.add_argument("--segundos", type=float, default=8, help="segundos de video por cámara")
        parser.add_argument("--ciclos", type=int, default=0, help="0 = sin fin")
        parser.add_argument("--pausa", type=int, default=120, help="segundos entre rondas")
        parser.add_argument("--camaras", nargs="*", help="códigos (por defecto, todas las activas)")

    def handle(self, *args, **o):
        ciclo = 0
        while not o["ciclos"] or ciclo < o["ciclos"]:
            ciclo += 1
            camaras = CamaraTransito.objects.filter(activa=True)
            if o["camaras"]:
                camaras = camaras.filter(codigo__in=o["camaras"])
            for c in camaras:
                try:
                    m = medir(c, o["segundos"])
                    e = congestion(c)
                    self.stdout.write(f"{timezone.localtime():%H:%M:%S} {c.codigo:<20} {m.por_minuto:6.1f} veh/min · "
                                      f"{m.en_cuadro:4.1f} a la vez · {e['nivel']}")
                except StreamNoDisponible as ex:
                    Medicion.objects.create(camara=c, inicio=timezone.now(), segundos=0, cuadros=0, por_minuto=0,
                                            en_cuadro=0, error=str(ex)[:200])
                    self.stdout.write(self.style.WARNING(f"{c.codigo}: {ex}"))
            if not o["ciclos"] or ciclo < o["ciclos"]:
                time.sleep(o["pausa"])
