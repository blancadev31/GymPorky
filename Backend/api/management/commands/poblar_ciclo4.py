# Datos de demostración para el Ciclo 4 (CU07, CU21-CU24 y reportes).
# Uso:  python manage.py poblar_ciclo4
# Es idempotente: no duplica contratos ni horarios si ya existen.
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from api.models import (
    ContratoLaboral, HorarioLaboral, MarcacionAcceso, MarcacionPersonal, Socio, Turno, Usuario,
)
from api.membresias import resumen_membresia

DIAS = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']


class Command(BaseCommand):
    help = 'Carga contratos laborales, horarios, marcaciones de personal y accesos de socios de ejemplo.'

    def handle(self, *args, **options):
        random.seed(42)
        hoy = timezone.localdate()
        tz = timezone.get_current_timezone()

        manana, _ = Turno.objects.get_or_create(nombre_turno='Mañana (personal)', defaults={'hora_inicio': time(6, 0), 'hora_fin': time(14, 0)})
        tarde, _ = Turno.objects.get_or_create(nombre_turno='Tarde (personal)', defaults={'hora_inicio': time(14, 0), 'hora_fin': time(22, 0)})

        personal = Usuario.objects.filter(Q(es_administrador=True) | Q(es_recepcionista=True) | Q(es_entrenador=True))
        contratos = []
        for i, u in enumerate(personal):
            c = ContratoLaboral.objects.filter(id_usuario=u, estado='Activo').first()
            if not c:
                cargo = 'Administrador' if u.es_administrador else ('Recepcionista' if u.es_recepcionista else 'Entrenador')
                salario = {'Administrador': 6000, 'Recepcionista': 3000, 'Entrenador': 3500}[cargo]
                c = ContratoLaboral.objects.create(id_usuario=u, cargo=cargo, salario_mensual=Decimal(salario),
                                                   fecha_inicio=hoy - timedelta(days=90))
            contratos.append(c)
            turno = manana if i % 2 == 0 else tarde
            for dia in DIAS[:6]:
                HorarioLaboral.objects.get_or_create(id_contrato_laboral=c, id_turno=turno, dia_semana=dia,
                                                     defaults={'tolerancia_minutos': 10})
        self.stdout.write(f'Contratos activos: {len(contratos)}')

        creadas = 0
        for c in contratos:
            for d in range(45, 0, -1):
                fecha = hoy - timedelta(days=d)
                dia = DIAS[fecha.weekday()]
                h = HorarioLaboral.objects.filter(id_contrato_laboral=c, dia_semana=dia).select_related('id_turno').first()
                if not h or random.random() < 0.08:  # ~8 % de faltas
                    continue
                if MarcacionPersonal.objects.filter(id_contrato_laboral=c, fecha_hora__date=fecha).exists():
                    continue
                entrada = datetime.combine(fecha, h.id_turno.hora_inicio) + timedelta(minutes=random.randint(-10, 25))
                salida = datetime.combine(fecha, h.id_turno.hora_fin) + timedelta(minutes=random.randint(0, 20))
                for evento, momento in (('ENTRADA', entrada), ('SALIDA', salida)):
                    m = MarcacionPersonal.objects.create(id_contrato_laboral=c, tipo_evento=evento, metodo='Sistema Web')
                    MarcacionPersonal.objects.filter(pk=m.pk).update(fecha_hora=timezone.make_aware(momento, tz))
                    creadas += 1
        self.stdout.write(f'Marcaciones de personal creadas: {creadas}')

        accesos = 0
        for s in Socio.objects.all():
            m = resumen_membresia(s)
            for d in range(30, 0, -1):
                if random.random() > 0.45:
                    continue
                momento = datetime.combine(hoy - timedelta(days=d), time(random.choice([6, 7, 8, 12, 17, 18, 19, 20]), random.randint(0, 59)))
                tipo = 'PERMITIDO' if m['estado'] != 'Sin membresía' else 'DENEGADO'
                a = MarcacionAcceso.objects.create(id_socio=s, tipo_acceso=tipo,
                                                   observacion='Membresía vigente' if tipo == 'PERMITIDO' else 'El socio no tiene membresía')
                MarcacionAcceso.objects.filter(pk=a.pk).update(fecha_hora=timezone.make_aware(momento, tz))
                accesos += 1
        self.stdout.write(self.style.SUCCESS(f'Accesos de socios creados: {accesos}. Listo.'))
