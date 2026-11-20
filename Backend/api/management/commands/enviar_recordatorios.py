# Recordatorios automáticos de vencimiento de membresía (3, 2, 1 y 0 días antes).
# Programarlo una vez al día, por ejemplo con cron en el servidor:
#   0 8 * * *  cd /ruta/Backend && venv/bin/python manage.py enviar_recordatorios
# (También se ejecuta solo, una vez al día, cuando un usuario abre sus notificaciones.)
from django.core.management.base import BaseCommand

from api.automatizacion import generar_recordatorios_vencimiento


class Command(BaseCommand):
    help = 'Genera las notificaciones y correos de membresías que vencen en los próximos 3 días.'

    def handle(self, *args, **options):
        n = generar_recordatorios_vencimiento(forzar=True)
        self.stdout.write(self.style.SUCCESS(f'Recordatorios enviados a socios: {n}'))
