# api/reportes_views.py
# ==============================================================================
# REPORTES (funcionalidad adicional, no es caso de uso)
#   1) Reportes ESTÁTICOS   : formato y columnas fijas (no requieren parámetros).
#   2) Reportes DINÁMICOS   : el usuario elige entidad, columnas, filtros y orden.
#   3) Reportes ESTADÍSTICOS: datos agregados que el frontend dibuja en gráficos.
# Todos se exportan a 3 formatos: PDF, Excel (.xlsx) y CSV (?formato=pdf|xlsx|csv).
# Sin ?formato se devuelven en JSON para la vista previa en pantalla.
# La visibilidad depende del perfil del usuario (Administrador, Recepcionista,
# Entrenador).
# ==============================================================================
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum, F, Q
from django.db.models.functions import TruncDate, ExtractHour
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .exportadores import respuesta_archivo
from .membresias import resumen_membresia
from .models import (
    Socio, Producto, ArqueoCaja, Venta, ContratoMembresia, MarcacionAcceso, Compra, KardexInventario,
    PagoPlanilla, MarcacionPersonal, AsignacionRutina, DetalleVentaProducto, Bitacora, ContratoLaboral,
)
from .views import registrar_bitacora

AD, RE, EN = 'Administrador', 'Recepcionista', 'Entrenador'


def roles_de(usuario):
    r = set()
    if usuario.es_administrador:
        r.add(AD)
    if usuario.es_recepcionista:
        r.add(RE)
    if usuario.es_entrenador:
        r.add(EN)
    return r


def _nombre(u):
    return f'{u.first_name} {u.last_name}'.strip() or u.username


def _fmt_dt(v):
    return timezone.localtime(v).strftime('%d/%m/%Y %H:%M') if v else ''


def _fmt_d(v):
    return v.strftime('%d/%m/%Y') if v else ''


def _col(clave, titulo):
    return {'clave': clave, 'titulo': titulo}


# ==============================================================================
# 1) REPORTES ESTÁTICOS
# ==============================================================================
def rep_socios_membresia(params):
    filas = []
    for s in Socio.objects.select_related('id_socio').order_by('id_socio__last_name', 'id_socio__first_name'):
        m = resumen_membresia(s)
        u = s.id_socio
        filas.append({
            'ci': u.ci or '', 'socio': _nombre(u), 'telefono': u.telefono or '', 'email': u.email,
            'plan': m['plan'] or '-', 'estado': m['estado'],
            'vence': m['fecha_vencimiento'] or '-', 'dias': m['dias_restantes'] if m['dias_restantes'] is not None else '-',
        })
    cols = [_col('ci', 'CI'), _col('socio', 'Socio'), _col('telefono', 'Teléfono'), _col('email', 'Correo'),
            _col('plan', 'Plan'), _col('estado', 'Estado membresía'), _col('vence', 'Vencimiento'),
            _col('dias', 'Días restantes')]
    vig = sum(1 for f in filas if f['estado'] == 'Vigente')
    return cols, filas, f'Socios: {len(filas)}  |  Vigentes: {vig}  |  Vencidos/sin plan: {len(filas) - vig}'


def rep_inventario_stock(params):
    filas = []
    for p in Producto.objects.select_related('id_categoria').order_by('id_categoria__nombre_categoria', 'nombre_producto'):
        estado = 'Agotado' if p.stock_actual <= 0 else ('Bajo mínimo' if p.stock_actual <= p.stock_minimo else 'Normal')
        filas.append({
            'producto': p.nombre_producto, 'categoria': p.id_categoria.nombre_categoria,
            'stock': p.stock_actual, 'minimo': p.stock_minimo, 'precio': p.precio_venta_local,
            'costo': p.costo_promedio_local,
            'valorizado': (p.costo_promedio_local * max(p.stock_actual, 0)).quantize(Decimal('0.01')),
            'estado': estado,
        })
    cols = [_col('producto', 'Producto'), _col('categoria', 'Categoría'), _col('stock', 'Stock'),
            _col('minimo', 'Stock mín.'), _col('precio', 'Precio venta (Bs)'), _col('costo', 'Costo prom. (Bs)'),
            _col('valorizado', 'Valorizado (Bs)'), _col('estado', 'Estado')]
    total = sum(f['valorizado'] for f in filas)
    return cols, filas, f'Productos: {len(filas)}  |  Inventario valorizado: Bs {total}'


def rep_cierres_caja(params):
    filas = []
    for c in ArqueoCaja.objects.select_related('responsable', 'turno').order_by('-fecha_apertura')[:300]:
        filas.append({
            'id': c.id_caja, 'responsable': _nombre(c.responsable) if c.responsable else '-',
            'turno': c.turno.nombre_turno if c.turno else '-', 'apertura': _fmt_dt(c.fecha_apertura),
            'cierre': _fmt_dt(c.fecha_cierre), 'inicial': c.monto_inicial, 'final': c.monto_final if c.monto_final is not None else '-',
            'contado': c.efectivo_contado if c.efectivo_contado is not None else '-',
            'diferencia': c.diferencia if c.diferencia is not None else '-', 'estado': c.estado,
        })
    cols = [_col('id', 'N° Caja'), _col('responsable', 'Responsable'), _col('turno', 'Turno'),
            _col('apertura', 'Apertura'), _col('cierre', 'Cierre'), _col('inicial', 'Monto inicial'),
            _col('final', 'Monto esperado'), _col('contado', 'Efectivo contado'), _col('diferencia', 'Diferencia'),
            _col('estado', 'Estado')]
    return cols, filas, f'Arqueos registrados: {len(filas)}'


def rep_personal_planilla(params):
    filas = []
    for c in ContratoLaboral.objects.select_related('id_usuario').order_by('-estado', 'id_usuario__username'):
        ultimo = PagoPlanilla.objects.filter(id_contrato_laboral=c).order_by('-periodo_anio', '-periodo_mes').first()
        filas.append({
            'empleado': _nombre(c.id_usuario), 'cargo': c.cargo, 'salario': c.salario_mensual,
            'inicio': _fmt_d(c.fecha_inicio), 'fin': _fmt_d(c.fecha_finalizacion) or 'Indefinido', 'estado': c.estado,
            'ultimo_pago': f'{ultimo.periodo_mes:02d}/{ultimo.periodo_anio} - Bs {ultimo.total_pagado}' if ultimo else 'Sin pagos',
        })
    cols = [_col('empleado', 'Empleado'), _col('cargo', 'Cargo'), _col('salario', 'Salario (Bs)'),
            _col('inicio', 'Inicio'), _col('fin', 'Fin'), _col('estado', 'Estado'), _col('ultimo_pago', 'Último pago')]
    return cols, filas, f'Contratos: {len(filas)}'


ESTATICOS = {
    'socios-membresia': {'titulo': 'Socios y estado de membresía', 'roles': {AD, RE}, 'fn': rep_socios_membresia},
    'inventario-stock': {'titulo': 'Inventario y stock de productos', 'roles': {AD}, 'fn': rep_inventario_stock},
    'cierres-caja': {'titulo': 'Arqueos y cierres de caja', 'roles': {AD, RE}, 'fn': rep_cierres_caja},
    'personal-planilla': {'titulo': 'Personal y planilla de sueldos', 'roles': {AD}, 'fn': rep_personal_planilla},
}


# ==============================================================================
# 2) REPORTES DINÁMICOS: definición de entidades, columnas y filtros
# ==============================================================================
def _ventas(qs_params):
    qs = Venta.objects.select_related('id_usuario', 'id_metodo_pago', 'id_socio__id_socio')
    return qs, 'fecha_hora', lambda v: {
        'id': v.id_venta, 'fecha': _fmt_dt(v.fecha_hora), 'socio': _nombre(v.id_socio.id_socio),
        'cajero': v.id_usuario.username, 'metodo': v.id_metodo_pago.descripcion,
        'factura': v.nro_factura or '', 'monto': v.monto_total_local, 'estado': v.estado_venta,
    }


def _membresias(_):
    qs = ContratoMembresia.objects.select_related('id_socio__id_socio', 'id_plan_mem', 'id_metodo_pago')
    return qs, 'fecha_inicio', lambda c: {
        'id': c.id_contrato_mem, 'socio': _nombre(c.id_socio.id_socio), 'ci': c.id_socio.id_socio.ci or '',
        'plan': c.id_plan_mem.nombre_plan, 'operacion': c.tipo_operacion, 'inicio': _fmt_d(c.fecha_inicio),
        'vencimiento': _fmt_d(c.fecha_vencimiento), 'metodo': c.id_metodo_pago.descripcion,
        'monto': c.monto_pagado_local, 'estado': c.estado_membresia,
    }


def _accesos(_):
    qs = MarcacionAcceso.objects.select_related('id_socio__id_socio')
    return qs, 'fecha_hora', lambda m: {
        'id': m.id_marcacion_acceso, 'fecha': _fmt_dt(m.fecha_hora), 'socio': _nombre(m.id_socio.id_socio),
        'ci': m.id_socio.id_socio.ci or '', 'resultado': m.tipo_acceso or '', 'observacion': m.observacion or '',
    }


def _compras(_):
    qs = Compra.objects.select_related('id_proveedor')
    return qs, 'fecha_hora', lambda c: {
        'id': c.id_compra, 'fecha': _fmt_dt(c.fecha_hora), 'proveedor': c.id_proveedor.razon_social,
        'factura': c.nro_factura_proveedor or '', 'monto_origen': c.monto_total_origen,
        'tasa': c.tasa_cambio_aplicada, 'monto': c.monto_total_local, 'estado': c.estado_compra,
    }


def _kardex(_):
    qs = KardexInventario.objects.select_related('id_producto')
    return qs, 'fecha_movimiento', lambda k: {
        'id': k.id_kardex, 'fecha': _fmt_dt(k.fecha_movimiento), 'producto': k.id_producto.nombre_producto,
        'tipo': k.tipo_movimiento, 'cantidad': k.cantidad, 'motivo': k.motivo,
    }


def _asistencia(_):
    qs = MarcacionPersonal.objects.select_related('id_contrato_laboral__id_usuario')
    return qs, 'fecha_hora', lambda m: {
        'id': m.id_marcacion_personal, 'fecha': _fmt_dt(m.fecha_hora),
        'empleado': _nombre(m.id_contrato_laboral.id_usuario), 'cargo': m.id_contrato_laboral.cargo,
        'evento': m.tipo_evento, 'metodo': m.metodo or '',
    }


def _planilla(_):
    qs = PagoPlanilla.objects.select_related('id_contrato_laboral__id_usuario')
    return qs, 'fecha_pagada', lambda p: {
        'id': p.id_pago_planilla, 'periodo': f'{p.periodo_mes:02d}/{p.periodo_anio}',
        'empleado': _nombre(p.id_contrato_laboral.id_usuario), 'cargo': p.id_contrato_laboral.cargo,
        'base': p.salario_base, 'bonos': p.bonos, 'descuentos': p.descuentos, 'total': p.total_pagado,
        'fecha': _fmt_d(p.fecha_pagada),
    }


def _asignaciones(_):
    qs = AsignacionRutina.objects.select_related('id_socio__id_socio', 'id_rutina', 'id_entrenador__id_entrenador')
    return qs, 'fecha_asignacion', lambda a: {
        'id': a.id_asignacion_rutina, 'fecha': _fmt_d(a.fecha_asignacion), 'socio': _nombre(a.id_socio.id_socio),
        'rutina': a.id_rutina.nombre_rutina, 'nivel': a.id_rutina.nivel,
        'entrenador': _nombre(a.id_entrenador.id_entrenador), 'turno': a.turno, 'estado': a.estado,
    }


def _bitacora(_):
    qs = Bitacora.objects.all()
    return qs, 'fecha_hora', lambda b: {
        'id': b.id_bitacora, 'fecha': _fmt_dt(b.fecha_hora), 'usuario': b.nombre_usuario_db or '',
        'accion': b.accion, 'tabla': b.tabla_afectada, 'ip': b.direccion_ip or '', 'descripcion': b.descripcion or '',
    }


DINAMICOS = {
    'ventas': {
        'titulo': 'Ventas POS', 'roles': {AD, RE}, 'fn': _ventas,
        'columnas': [_col('id', 'N°'), _col('fecha', 'Fecha'), _col('socio', 'Socio'), _col('cajero', 'Cajero'),
                     _col('metodo', 'Método de pago'), _col('factura', 'N° factura'), _col('monto', 'Monto (Bs)'),
                     _col('estado', 'Estado')],
        'filtros': {'metodo': 'id_metodo_pago__descripcion__icontains', 'estado': 'estado_venta__iexact',
                    'q': ['id_socio__id_socio__username__icontains', 'id_socio__id_socio__first_name__icontains',
                          'id_socio__id_socio__last_name__icontains', 'nro_factura__icontains']},
        'total': 'monto',
    },
    'membresias': {
        'titulo': 'Contratos de membresía', 'roles': {AD, RE}, 'fn': _membresias,
        'columnas': [_col('id', 'N°'), _col('socio', 'Socio'), _col('ci', 'CI'), _col('plan', 'Plan'),
                     _col('operacion', 'Operación'), _col('inicio', 'Inicio'), _col('vencimiento', 'Vencimiento'),
                     _col('metodo', 'Método de pago'), _col('monto', 'Monto (Bs)'), _col('estado', 'Estado')],
        'filtros': {'plan': 'id_plan_mem__nombre_plan__icontains', 'metodo': 'id_metodo_pago__descripcion__icontains',
                    'estado': 'estado_membresia__iexact',
                    'q': ['id_socio__id_socio__username__icontains', 'id_socio__id_socio__ci__icontains',
                          'id_socio__id_socio__first_name__icontains', 'id_socio__id_socio__last_name__icontains']},
        'total': 'monto',
    },
    'accesos': {
        'titulo': 'Accesos de socios', 'roles': {AD, RE}, 'fn': _accesos,
        'columnas': [_col('id', 'N°'), _col('fecha', 'Fecha y hora'), _col('socio', 'Socio'), _col('ci', 'CI'),
                     _col('resultado', 'Resultado'), _col('observacion', 'Observación')],
        'filtros': {'estado': 'tipo_acceso__iexact',
                    'q': ['id_socio__id_socio__username__icontains', 'id_socio__id_socio__ci__icontains',
                          'id_socio__id_socio__first_name__icontains', 'id_socio__id_socio__last_name__icontains']},
    },
    'compras': {
        'titulo': 'Compras de mercadería', 'roles': {AD}, 'fn': _compras,
        'columnas': [_col('id', 'N°'), _col('fecha', 'Fecha'), _col('proveedor', 'Proveedor'), _col('factura', 'N° factura'),
                     _col('monto_origen', 'Monto origen'), _col('tasa', 'Tasa cambio'), _col('monto', 'Monto (Bs)'),
                     _col('estado', 'Estado')],
        'filtros': {'estado': 'estado_compra__iexact', 'q': ['id_proveedor__razon_social__icontains', 'nro_factura_proveedor__icontains']},
        'total': 'monto',
    },
    'kardex': {
        'titulo': 'Movimientos de kardex', 'roles': {AD}, 'fn': _kardex,
        'columnas': [_col('id', 'N°'), _col('fecha', 'Fecha'), _col('producto', 'Producto'), _col('tipo', 'Tipo'),
                     _col('cantidad', 'Cantidad'), _col('motivo', 'Motivo')],
        'filtros': {'estado': 'tipo_movimiento__iexact', 'q': ['id_producto__nombre_producto__icontains', 'motivo__icontains']},
    },
    'asistencia': {
        'titulo': 'Asistencia del personal', 'roles': {AD}, 'fn': _asistencia,
        'columnas': [_col('id', 'N°'), _col('fecha', 'Fecha y hora'), _col('empleado', 'Empleado'), _col('cargo', 'Cargo'),
                     _col('evento', 'Evento'), _col('metodo', 'Método')],
        'filtros': {'estado': 'tipo_evento__iexact',
                    'q': ['id_contrato_laboral__id_usuario__username__icontains', 'id_contrato_laboral__cargo__icontains']},
    },
    'planilla': {
        'titulo': 'Pagos de planilla', 'roles': {AD}, 'fn': _planilla,
        'columnas': [_col('id', 'N°'), _col('periodo', 'Periodo'), _col('empleado', 'Empleado'), _col('cargo', 'Cargo'),
                     _col('base', 'Salario base'), _col('bonos', 'Bonos'), _col('descuentos', 'Descuentos'),
                     _col('total', 'Total pagado'), _col('fecha', 'Fecha pago')],
        'filtros': {'q': ['id_contrato_laboral__id_usuario__username__icontains', 'id_contrato_laboral__cargo__icontains']},
        'total': 'total',
    },
    'asignaciones': {
        'titulo': 'Rutinas asignadas a socios', 'roles': {AD, EN}, 'fn': _asignaciones,
        'columnas': [_col('id', 'N°'), _col('fecha', 'Fecha'), _col('socio', 'Socio'), _col('rutina', 'Rutina'),
                     _col('nivel', 'Nivel'), _col('entrenador', 'Entrenador'), _col('turno', 'Turno'), _col('estado', 'Estado')],
        'filtros': {'estado': 'estado__iexact',
                    'q': ['id_rutina__nombre_rutina__icontains', 'id_socio__id_socio__username__icontains']},
    },
    'bitacora': {
        'titulo': 'Bitácora de auditoría', 'roles': {AD}, 'fn': _bitacora,
        'columnas': [_col('id', 'N°'), _col('fecha', 'Fecha'), _col('usuario', 'Usuario'), _col('accion', 'Acción'),
                     _col('tabla', 'Tabla'), _col('ip', 'IP'), _col('descripcion', 'Descripción')],
        'filtros': {'estado': 'accion__iexact', 'q': ['nombre_usuario_db__icontains', 'descripcion__icontains', 'tabla_afectada__icontains']},
    },
}


# ==============================================================================
# 3) REPORTES ESTADÍSTICOS (para gráficos)
# ==============================================================================
def _rango(params, dias_def=30):
    hoy = timezone.localdate()
    desde = params.get('desde') or (hoy - timedelta(days=dias_def - 1)).isoformat()
    hasta = params.get('hasta') or hoy.isoformat()
    return desde, hasta


def est_ingresos_diarios(params):
    desde, hasta = _rango(params)
    ventas = dict(Venta.objects.filter(fecha_hora__date__gte=desde, fecha_hora__date__lte=hasta)
                  .annotate(d=TruncDate('fecha_hora')).values('d').annotate(t=Sum('monto_total_local')).values_list('d', 't'))
    membr = dict(ContratoMembresia.objects.filter(fecha_inicio__gte=desde, fecha_inicio__lte=hasta)
                 .values('fecha_inicio').annotate(t=Sum('monto_pagado_local')).values_list('fecha_inicio', 't'))
    fechas = sorted(set(ventas) | set(membr))
    filas = [{'etiqueta': _fmt_d(f), 'ventas': ventas.get(f, Decimal('0')) or Decimal('0'),
              'membresias': membr.get(f, Decimal('0')) or Decimal('0')} for f in fechas]
    for f in filas:
        f['total'] = f['ventas'] + f['membresias']
    cols = [_col('etiqueta', 'Fecha'), _col('ventas', 'Ventas POS (Bs)'), _col('membresias', 'Membresías (Bs)'), _col('total', 'Total (Bs)')]
    return cols, filas, ['ventas', 'membresias'], f'Del {desde} al {hasta}'


def est_ingresos_metodo(params):
    desde, hasta = _rango(params)
    agg = {}
    for d, t in (Venta.objects.filter(fecha_hora__date__gte=desde, fecha_hora__date__lte=hasta)
                 .values('id_metodo_pago__descripcion').annotate(t=Sum('monto_total_local'))
                 .values_list('id_metodo_pago__descripcion', 't')):
        agg[d] = agg.get(d, Decimal('0')) + (t or 0)
    for d, t in (ContratoMembresia.objects.filter(fecha_inicio__gte=desde, fecha_inicio__lte=hasta)
                 .values('id_metodo_pago__descripcion').annotate(t=Sum('monto_pagado_local'))
                 .values_list('id_metodo_pago__descripcion', 't')):
        agg[d] = agg.get(d, Decimal('0')) + (t or 0)
    filas = [{'etiqueta': k, 'total': v} for k, v in sorted(agg.items(), key=lambda x: -x[1])]
    return [_col('etiqueta', 'Método de pago'), _col('total', 'Total (Bs)')], filas, ['total'], f'Del {desde} al {hasta}'


def est_accesos_hora(params):
    desde, hasta = _rango(params)
    datos = dict(MarcacionAcceso.objects.filter(tipo_acceso='PERMITIDO', fecha_hora__date__gte=desde, fecha_hora__date__lte=hasta)
                 .annotate(h=ExtractHour('fecha_hora')).values('h').annotate(n=Count('pk')).values_list('h', 'n'))
    filas = [{'etiqueta': f'{h:02d}:00', 'accesos': datos.get(h, 0)} for h in range(5, 24)]
    return [_col('etiqueta', 'Hora'), _col('accesos', 'Accesos')], filas, ['accesos'], f'Horas pico del {desde} al {hasta}'


def est_top_productos(params):
    desde, hasta = _rango(params)
    datos = (DetalleVentaProducto.objects.filter(id_venta__fecha_hora__date__gte=desde, id_venta__fecha_hora__date__lte=hasta)
             .values('id_producto__nombre_producto').annotate(cant=Sum('cantidad'), total=Sum('subtotal_local'))
             .order_by('-cant')[:10])
    filas = [{'etiqueta': d['id_producto__nombre_producto'], 'cantidad': d['cant'], 'total': d['total']} for d in datos]
    return ([_col('etiqueta', 'Producto'), _col('cantidad', 'Unidades vendidas'), _col('total', 'Total (Bs)')],
            filas, ['cantidad'], f'Top 10 del {desde} al {hasta}')


def est_rutinas_nivel(params):
    datos = (AsignacionRutina.objects.filter(estado='Activa').values('id_rutina__nivel').annotate(n=Count('pk')).order_by('-n'))
    filas = [{'etiqueta': d['id_rutina__nivel'], 'asignaciones': d['n']} for d in datos]
    return [_col('etiqueta', 'Nivel'), _col('asignaciones', 'Asignaciones activas')], filas, ['asignaciones'], 'Asignaciones activas'


ESTADISTICOS = {
    'ingresos-diarios': {'titulo': 'Ingresos diarios (ventas + membresías)', 'roles': {AD}, 'fn': est_ingresos_diarios, 'tipo': 'barras'},
    'ingresos-metodo': {'titulo': 'Ingresos por método de pago', 'roles': {AD}, 'fn': est_ingresos_metodo, 'tipo': 'barras'},
    'accesos-hora': {'titulo': 'Accesos por hora (horas pico)', 'roles': {AD, RE}, 'fn': est_accesos_hora, 'tipo': 'barras'},
    'top-productos': {'titulo': 'Productos más vendidos', 'roles': {AD, RE}, 'fn': est_top_productos, 'tipo': 'barras'},
    'rutinas-nivel': {'titulo': 'Rutinas asignadas por nivel', 'roles': {AD, EN}, 'fn': est_rutinas_nivel, 'tipo': 'barras'},
}


# ==============================================================================
# VISTAS
# ==============================================================================
class EsPersonalReportes(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and roles_de(u))


def _serializable(filas):
    salida = []
    for f in filas:
        salida.append({k: (str(v) if isinstance(v, Decimal) else v) for k, v in f.items()})
    return salida


def _entregar(request, clave, titulo, cols, filas, subtitulo, extra=None):
    formato = (request.query_params.get('formato') or '').lower()
    if formato in ('pdf', 'xlsx', 'csv'):
        registrar_bitacora(request, 'REPORTE', 'reporte',
                           f"Reporte '{titulo}' exportado en {formato.upper()} ({len(filas)} filas).", usuario=request.user)
        return respuesta_archivo(formato, clave.replace('-', '_'), titulo, cols, filas, subtitulo)
    datos = {'titulo': titulo, 'subtitulo': subtitulo, 'columnas': cols, 'filas': _serializable(filas), 'total_filas': len(filas)}
    if extra:
        datos.update(extra)
    return Response(datos)


class CatalogoReportesView(APIView):
    """GET /api/reportes/ -> reportes visibles para el perfil del usuario."""
    permission_classes = [EsPersonalReportes]

    def get(self, request):
        r = roles_de(request.user)
        return Response({
            'roles': sorted(r),
            'estaticos': [{'clave': k, 'titulo': v['titulo']} for k, v in ESTATICOS.items() if v['roles'] & r],
            'dinamicos': [{'clave': k, 'titulo': v['titulo'], 'columnas': v['columnas'],
                           'filtros': [f for f in v['filtros'] if f != 'q']}
                          for k, v in DINAMICOS.items() if v['roles'] & r],
            'estadisticos': [{'clave': k, 'titulo': v['titulo'], 'tipo': v['tipo']} for k, v in ESTADISTICOS.items() if v['roles'] & r],
            'formatos': ['pdf', 'xlsx', 'csv'],
        })


class ReporteEstaticoView(APIView):
    permission_classes = [EsPersonalReportes]

    def get(self, request, clave):
        rep = ESTATICOS.get(clave)
        if not rep:
            return Response({'detail': 'Reporte no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if not (rep['roles'] & roles_de(request.user)):
            return Response({'detail': 'Su perfil no tiene acceso a este reporte.'}, status=status.HTTP_403_FORBIDDEN)
        cols, filas, sub = rep['fn'](request.query_params)
        return _entregar(request, clave, rep['titulo'], cols, filas, sub)


class ReporteDinamicoView(APIView):
    """
    GET /api/reportes/dinamico/<entidad>/?columnas=a,b&desde=AAAA-MM-DD&hasta=...&q=texto
        &metodo=...&estado=...&plan=...&orden=asc|desc&limite=N&formato=pdf|xlsx|csv
    """
    permission_classes = [EsPersonalReportes]

    def get(self, request, entidad):
        rep = DINAMICOS.get(entidad)
        if not rep:
            return Response({'detail': 'Entidad no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not (rep['roles'] & roles_de(request.user)):
            return Response({'detail': 'Su perfil no tiene acceso a este reporte.'}, status=status.HTTP_403_FORBIDDEN)
        p = request.query_params
        qs, campo_fecha, a_fila = rep['fn'](p)

        # Un entrenador (sin rol de administrador) solo ve sus propias asignaciones.
        if entidad == 'asignaciones' and not request.user.es_administrador:
            qs = qs.filter(id_entrenador__id_entrenador=request.user)

        if p.get('desde'):
            qs = qs.filter(**{f'{campo_fecha}__gte' if campo_fecha in ('fecha_inicio', 'fecha_pagada', 'fecha_asignacion')
                              else f'{campo_fecha}__date__gte': p['desde']})
        if p.get('hasta'):
            qs = qs.filter(**{f'{campo_fecha}__lte' if campo_fecha in ('fecha_inicio', 'fecha_pagada', 'fecha_asignacion')
                              else f'{campo_fecha}__date__lte': p['hasta']})
        for nombre, lookup in rep['filtros'].items():
            valor = (p.get(nombre) or '').strip()
            if not valor:
                continue
            if isinstance(lookup, list):
                cond = Q()
                for lk in lookup:
                    cond |= Q(**{lk: valor})
                qs = qs.filter(cond)
            else:
                qs = qs.filter(**{lookup: valor})

        orden = '' if p.get('orden') == 'asc' else '-'
        qs = qs.order_by(f'{orden}{campo_fecha}')
        try:
            limite = max(1, min(5000, int(p.get('limite') or 1000)))
        except ValueError:
            limite = 1000
        filas = [a_fila(o) for o in qs[:limite]]

        claves_validas = [c['clave'] for c in rep['columnas']]
        pedidas = [c for c in (p.get('columnas') or '').split(',') if c in claves_validas]
        cols = [c for c in rep['columnas'] if not pedidas or c['clave'] in pedidas]

        partes = []
        if p.get('desde') or p.get('hasta'):
            partes.append(f"Periodo: {p.get('desde') or 'inicio'} a {p.get('hasta') or 'hoy'}")
        for nombre in rep['filtros']:
            if p.get(nombre):
                partes.append(f'{nombre}: {p.get(nombre)}')
        partes.append(f'Registros: {len(filas)}')
        if rep.get('total'):
            total = sum((f.get(rep['total']) or 0) for f in filas)
            partes.append(f'Total: Bs {total}')
        return _entregar(request, f'dinamico_{entidad}', rep['titulo'], cols, filas, '  |  '.join(partes))


class ReporteEstadisticoView(APIView):
    permission_classes = [EsPersonalReportes]

    def get(self, request, clave):
        rep = ESTADISTICOS.get(clave)
        if not rep:
            return Response({'detail': 'Reporte no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if not (rep['roles'] & roles_de(request.user)):
            return Response({'detail': 'Su perfil no tiene acceso a este reporte.'}, status=status.HTTP_403_FORBIDDEN)
        cols, filas, series, sub = rep['fn'](request.query_params)
        return _entregar(request, clave, rep['titulo'], cols, filas, sub, {'series': series, 'tipo': rep['tipo']})
