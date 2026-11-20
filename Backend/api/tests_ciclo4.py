# api/tests_ciclo4.py
# Pruebas automatizadas del Ciclo 3 (pendientes) y Ciclo 4:
#   CU07 Validar acceso de socio, CU21-CU24 Recursos Humanos y reportes (funcionalidad adicional).
# Ejecutar con:  python manage.py test api
from datetime import date, timedelta, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Socio, PlanMembresia, MetodoPago, ContratoMembresia, MarcacionAcceso, ContratoLaboral, Turno,
    HorarioLaboral, MarcacionPersonal, PagoPlanilla, Bitacora,
)

Usuario = get_user_model()


def crear_usuario(username, **roles):
    return Usuario.objects.create_user(username=username, password='Clave123!', email=f'{username}@test.com',
                                       ci=f'CI-{username}', **roles)


class BaseCiclo4(TestCase):
    def setUp(self):
        self.admin = crear_usuario('admin4', es_administrador=True)
        self.recep = crear_usuario('recep4', es_recepcionista=True)
        self.entre = crear_usuario('entre4', es_entrenador=True)
        self.u_socio = crear_usuario('socio4', es_socio=True)
        self.socio = Socio.objects.create(id_socio=self.u_socio, fecha_nacimiento=date(2000, 1, 1))
        self.metodo = MetodoPago.objects.create(descripcion='Efectivo')
        self.plan = PlanMembresia.objects.create(nombre_plan='Mensual', costo_base_origen=Decimal('150'), duracion_dias=30)
        self.client = APIClient()

    def dar_membresia(self, inicio, fin):
        return ContratoMembresia.objects.create(
            id_socio=self.socio, id_metodo_pago=self.metodo, id_plan_mem=self.plan, tipo_operacion='Nuevo',
            fecha_inicio=inicio, fecha_vencimiento=fin, monto_pagado_local=Decimal('150'))


class CU07ValidarAccesoTests(BaseCiclo4):
    def test_acceso_permitido_con_membresia_vigente(self):
        hoy = timezone.localdate()
        self.dar_membresia(hoy - timedelta(days=5), hoy + timedelta(days=25))
        self.client.force_authenticate(self.recep)
        r = self.client.post('/api/acceso/validar/', {'termino': self.u_socio.ci}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['permitido'])
        self.assertEqual(MarcacionAcceso.objects.filter(tipo_acceso='PERMITIDO').count(), 1)
        self.assertTrue(Bitacora.objects.filter(accion='ACCESO').exists())

    def test_acceso_denegado_sin_membresia(self):
        self.client.force_authenticate(self.recep)
        r = self.client.post('/api/acceso/validar/', {'termino': 'socio4'}, format='json')
        self.assertFalse(r.data['permitido'])
        self.assertEqual(MarcacionAcceso.objects.get().tipo_acceso, 'DENEGADO')

    def test_acceso_denegado_membresia_vencida(self):
        hoy = timezone.localdate()
        self.dar_membresia(hoy - timedelta(days=40), hoy - timedelta(days=10))
        self.client.force_authenticate(self.recep)
        r = self.client.post('/api/acceso/validar/', {'termino': 'socio4'}, format='json')
        self.assertFalse(r.data['permitido'])
        self.assertIn('vencida', r.data['motivo'].lower())

    def test_socio_inexistente(self):
        self.client.force_authenticate(self.recep)
        r = self.client.post('/api/acceso/validar/', {'termino': 'no-existe'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_ingreso_duplicado(self):
        hoy = timezone.localdate()
        self.dar_membresia(hoy, hoy + timedelta(days=30))
        self.client.force_authenticate(self.u_socio)
        self.assertTrue(self.client.post('/api/acceso/mi-ingreso/').data['permitido'])
        self.assertFalse(self.client.post('/api/acceso/mi-ingreso/').data['permitido'])

    def test_entrenador_no_ve_historial(self):
        self.client.force_authenticate(self.entre)
        self.assertEqual(self.client.get('/api/acceso/').status_code, 403)


class CU21a24RecursosHumanosTests(BaseCiclo4):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin)

    def crear_contrato(self, usuario=None, inicio=None):
        r = self.client.post('/api/contratos-laborales/', {
            'id_usuario': (usuario or self.recep).id, 'cargo': 'Recepcionista', 'salario_mensual': '3000.00',
            'fecha_inicio': (inicio or date(2026, 1, 1)).isoformat()}, format='json')
        return r

    def test_cu21_crear_y_no_duplicar_contrato(self):
        self.assertEqual(self.crear_contrato().status_code, 201)
        self.assertEqual(self.crear_contrato().status_code, 400)

    def test_cu21_no_contrata_socio(self):
        self.assertEqual(self.crear_contrato(usuario=self.u_socio).status_code, 400)

    def test_cu21_finalizar(self):
        cid = self.crear_contrato().data['id_contrato_laboral']
        r = self.client.post(f'/api/contratos-laborales/{cid}/finalizar/', {}, format='json')
        self.assertEqual(r.data['estado'], 'Finalizado')

    def test_cu22_turno_y_horario_sin_cruce(self):
        cid = self.crear_contrato().data['id_contrato_laboral']
        t1 = self.client.post('/api/turnos-gestion/', {'nombre_turno': 'Mañana', 'hora_inicio': '07:00', 'hora_fin': '13:00'}, format='json')
        t2 = self.client.post('/api/turnos-gestion/', {'nombre_turno': 'Medio', 'hora_inicio': '12:00', 'hora_fin': '16:00'}, format='json')
        self.assertEqual(t1.status_code, 201)
        ok = self.client.post('/api/horarios-laborales/', {'id_contrato_laboral': cid, 'id_turno': t1.data['id_turno'],
                                                            'dia_semana': 'Lunes', 'tolerancia_minutos': 10}, format='json')
        self.assertEqual(ok.status_code, 201, ok.data)
        cruce = self.client.post('/api/horarios-laborales/', {'id_contrato_laboral': cid, 'id_turno': t2.data['id_turno'],
                                                               'dia_semana': 'Lunes'}, format='json')
        self.assertEqual(cruce.status_code, 400)

    def test_cu22_turno_hora_invalida(self):
        r = self.client.post('/api/turnos-gestion/', {'nombre_turno': 'X', 'hora_inicio': '10:00', 'hora_fin': '09:00'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_cu23_marcacion_entrada_salida(self):
        self.crear_contrato()
        self.client.force_authenticate(self.recep)
        r = self.client.post('/api/marcaciones-personal/marcar/')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['tipo_evento'], 'ENTRADA')
        m = MarcacionPersonal.objects.get()
        m.fecha_hora = timezone.now() - timedelta(minutes=5)
        m.save()
        r2 = self.client.post('/api/marcaciones-personal/marcar/')
        self.assertEqual(r2.data['tipo_evento'], 'SALIDA')

    def test_cu23_sin_contrato(self):
        self.client.force_authenticate(self.entre)
        self.assertEqual(self.client.post('/api/marcaciones-personal/marcar/').status_code, 400)

    def test_cu24_liquidar_sin_duplicar(self):
        self.crear_contrato(inicio=date(2026, 1, 1))
        r = self.client.post('/api/planilla/liquidar/', {'mes': 2, 'anio': 2026, 'bonos': {}}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(PagoPlanilla.objects.count(), 1)
        self.assertEqual(PagoPlanilla.objects.get().total_pagado, Decimal('3000.00'))
        r2 = self.client.post('/api/planilla/liquidar/', {'mes': 2, 'anio': 2026}, format='json')
        self.assertEqual(PagoPlanilla.objects.count(), 1)
        self.assertEqual(len(r2.data['omitidos']), 1)

    def test_cu24_periodo_futuro(self):
        self.crear_contrato()
        r = self.client.post('/api/planilla/liquidar/', {'mes': 1, 'anio': 2099}, format='json')
        self.assertEqual(r.status_code, 400)


class ReportesAdicionalTests(BaseCiclo4):
    def test_catalogo_por_perfil(self):
        self.client.force_authenticate(self.admin)
        admin = self.client.get('/api/reportes/').data
        self.client.force_authenticate(self.entre)
        entre = self.client.get('/api/reportes/').data
        self.assertGreaterEqual(len(admin['estaticos']), 3)
        self.assertTrue(all(d['clave'] != 'planilla' for d in entre['dinamicos']))

    def test_socio_no_accede_a_reportes(self):
        self.client.force_authenticate(self.u_socio)
        self.assertEqual(self.client.get('/api/reportes/').status_code, 403)

    def test_estatico_tres_formatos(self):
        self.client.force_authenticate(self.admin)
        pdf = self.client.get('/api/reportes/estatico/socios-membresia/?formato=pdf')
        xlsx = self.client.get('/api/reportes/estatico/socios-membresia/?formato=xlsx')
        csv = self.client.get('/api/reportes/estatico/socios-membresia/?formato=csv')
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertTrue(xlsx.content.startswith(b'PK'))
        self.assertIn('text/csv', csv['Content-Type'])

    def test_dinamico_filtros_y_columnas(self):
        hoy = timezone.localdate()
        self.dar_membresia(hoy, hoy + timedelta(days=30))
        self.client.force_authenticate(self.admin)
        r = self.client.get('/api/reportes/dinamico/membresias/?columnas=socio,plan,monto&plan=Mensual')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([c['clave'] for c in r.data['columnas']], ['socio', 'plan', 'monto'])
        self.assertEqual(r.data['total_filas'], 1)

    def test_recepcionista_no_ve_planilla(self):
        self.client.force_authenticate(self.recep)
        self.assertEqual(self.client.get('/api/reportes/dinamico/planilla/').status_code, 403)

    def test_estadistico(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get('/api/reportes/estadistico/accesos-hora/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('series', r.data)


# ==============================================================================
# FUNCIONALIDADES ADICIONALES
# ==============================================================================
from .models import Notificacion, AlertaReposicion, KardexInventario, CategoriaProducto, Producto  # noqa: E402
from .automatizacion import generar_recordatorios_vencimiento  # noqa: E402


class ExtrasTests(BaseCiclo4):
    def crear_producto(self, stock=10, minimo=5):
        cat = CategoriaProducto.objects.create(nombre_categoria='Bebidas')
        return Producto.objects.create(id_categoria=cat, nombre_producto='Agua 600 ml', precio_base_original=Decimal('5'),
                                       precio_venta_local=Decimal('5'), stock_actual=stock, stock_minimo=minimo)

    def test_stock_bajo_genera_alerta_y_notificacion(self):
        p = self.crear_producto()
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/kardex/', {'id_producto': p.pk, 'tipo_movimiento': 'AJUSTE_NEGATIVO',
                                              'cantidad': 7, 'motivo': 'Producto dañado'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(AlertaReposicion.objects.filter(id_producto=p, estado_alerta='Pendiente').exists())
        self.assertTrue(Notificacion.objects.filter(id_usuario=self.admin, tipo='STOCK_BAJO').exists())
        # Repetir el movimiento no duplica la notificación del día.
        self.client.post('/api/kardex/', {'id_producto': p.pk, 'tipo_movimiento': 'AJUSTE_NEGATIVO',
                                          'cantidad': 1, 'motivo': 'Otro'}, format='json')
        self.assertEqual(Notificacion.objects.filter(id_usuario=self.admin, tipo='STOCK_BAJO').count(), 1)

    def test_recuperar_stock_cierra_alerta(self):
        p = self.crear_producto(stock=2)
        self.client.force_authenticate(self.admin)
        self.client.post('/api/kardex/', {'id_producto': p.pk, 'tipo_movimiento': 'AJUSTE_NEGATIVO', 'cantidad': 1, 'motivo': 'x'}, format='json')
        self.client.post('/api/kardex/', {'id_producto': p.pk, 'tipo_movimiento': 'INGRESO', 'cantidad': 20, 'motivo': 'reposición'}, format='json')
        self.assertFalse(AlertaReposicion.objects.filter(id_producto=p, estado_alerta='Pendiente').exists())

    def test_recordatorio_vencimiento_2_dias(self):
        hoy = timezone.localdate()
        self.dar_membresia(hoy - timedelta(days=28), hoy + timedelta(days=2))
        generar_recordatorios_vencimiento(forzar=True)
        self.assertTrue(Notificacion.objects.filter(id_usuario=self.u_socio, tipo='VENCIMIENTO').exists())
        self.assertTrue(Notificacion.objects.filter(id_usuario=self.recep, tipo='VENCIMIENTO').exists())
        generar_recordatorios_vencimiento(forzar=True)  # idempotente
        self.assertEqual(Notificacion.objects.filter(id_usuario=self.u_socio, tipo='VENCIMIENTO').count(), 1)

    def test_sin_recordatorio_si_faltan_10_dias(self):
        hoy = timezone.localdate()
        self.dar_membresia(hoy, hoy + timedelta(days=10))
        generar_recordatorios_vencimiento(forzar=True)
        self.assertFalse(Notificacion.objects.filter(tipo='VENCIMIENTO').exists())

    def test_campana_y_marcar_leida(self):
        Notificacion.objects.create(id_usuario=self.admin, tipo='SISTEMA', titulo='t', mensaje='m', referencia='r1')
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/notificaciones/no-leidas/').data['total'], 1)
        nid = self.client.get('/api/notificaciones/').data[0]['id_notificacion']
        self.client.post(f'/api/notificaciones/{nid}/leer/')
        self.assertEqual(self.client.get('/api/notificaciones/no-leidas/').data['total'], 0)

    def test_dashboard_por_perfil(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get('/api/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('ingresos_mes', r.data['kpis'])
        self.client.force_authenticate(self.recep)
        self.assertNotIn('ingresos_mes', self.client.get('/api/dashboard/').data['kpis'])
        self.client.force_authenticate(self.u_socio)
        self.assertEqual(self.client.get('/api/dashboard/').status_code, 403)

    def test_panel_socio(self):
        hoy = timezone.localdate()
        self.dar_membresia(hoy, hoy + timedelta(days=2))
        self.client.force_authenticate(self.u_socio)
        r = self.client.get('/api/mi-panel/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['alerta_vencimiento'])

    def test_chatbot_membresia_y_permisos(self):
        hoy = timezone.localdate()
        self.dar_membresia(hoy, hoy + timedelta(days=20))
        self.client.force_authenticate(self.u_socio)
        r = self.client.post('/api/chatbot/', {'mensaje': '¿Cuándo vence mi membresía?'}, format='json')
        self.assertIn('Mensual', r.data['respuesta'])
        r = self.client.post('/api/chatbot/', {'mensaje': 'abrir reportes'}, format='json')
        self.assertIsNone(r.data['accion'])  # un socio no puede abrir reportes
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/chatbot/', {'mensaje': 'abrir reportes'}, format='json')
        self.assertEqual(r.data['accion']['pantalla'], 'reportes')
