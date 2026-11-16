from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token

ROLES = {
    # El worker solo puede reportar capturas.
    "worker": ["infracciones.add_captura", "infracciones.view_captura", "camaras.view_camara"],
    "validador": ["infracciones.view_captura", "infracciones.view_infraccion", "infracciones.view_alerta",
                  "infracciones.change_alerta", "validacion.add_validacion", "validacion.view_validacion",
                  "validacion.view_papeleta", "camaras.view_camara", "camaras.view_tramo"],
    "administrador": None,  # todos los permisos de las apps del proyecto
}
APPS = ["camaras", "infracciones", "validacion", "panel"]


class Command(BaseCommand):
    help = "Crea los grupos worker, validador y administrador; opcionalmente un usuario worker con token."

    def add_arguments(self, parser):
        parser.add_argument("--worker", metavar="USUARIO", help="crea este usuario en el grupo worker y muestra su token")

    def handle(self, *args, **opts):
        for nombre, perms in ROLES.items():
            grupo, _ = Group.objects.get_or_create(name=nombre)
            if perms is None:
                qs = Permission.objects.filter(content_type__app_label__in=APPS)
            else:
                qs = Permission.objects.none()
                for p in perms:
                    app, codename = p.split(".")
                    qs |= Permission.objects.filter(content_type__app_label=app, codename=codename)
            grupo.permissions.set(qs)
            self.stdout.write(f"Grupo {nombre}: {qs.count()} permisos")
        if opts["worker"]:
            u, _ = User.objects.get_or_create(username=opts["worker"])
            u.groups.add(Group.objects.get(name="worker"))
            token, _ = Token.objects.get_or_create(user=u)
            self.stdout.write(self.style.SUCCESS(f"Usuario {u.username} listo. Token: {token.key}"))
