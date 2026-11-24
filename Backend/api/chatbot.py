# api/chatbot.py
# ==============================================================================
# FUNCIONALIDAD ADICIONAL: ASISTENTE VIRTUAL "PORKYBOT"
# Chatbot basado en reglas (intenciones por palabras clave) que responde con
# datos reales del sistema según el perfil del usuario. No depende de servicios
# externos ni de claves de API, por lo que funciona siempre y no expone datos.
# Devuelve: {respuesta, sugerencias[], accion: {tipo: 'navegar', pantalla} | None}
# ==============================================================================
import re
import unicodedata
from datetime import timedelta

from django.db.models import F, Q, Sum
from django.utils import timezone

from .membresias import resumen_membresia
from .models import (
    AsignacionRutina, ContratoMembresia, DetalleRutina, Ejercicio, Entrenador, HorarioEntrenador, MarcacionAcceso,
    PlanMembresia, Producto, Socio, Venta,
)

# Información general del gimnasio (editable aquí).
HORARIO_GIMNASIO = 'Lunes a viernes de 06:00 a 22:00 y sábados de 07:00 a 14:00. Domingos y feriados cerrado.'
REGLAS_GIMNASIO = (
    'Normas básicas de Porky Gym:\n'
    '• Uso obligatorio de toalla personal y ropa/calzado deportivo limpio.\n'
    '• Devuelve los discos, barras y mancuernas a su lugar al terminar.\n'
    '• Alterna las máquinas en tiempos de descanso y cuida el equipo.\n'
    '• Si tu plan incluye piscina, usa gorro y sandalias en el área húmeda.\n'
    '• Mantén una buena convivencia y respeta el espacio de los demás socios.'
)
INFO_PAGO_RENOVACION = (
    'Para inscribirte o renovar tu membresía acércate a recepción con tu documento de identidad. '
    'Aceptamos efectivo, transferencia/QR y tarjeta. Si necesitas factura o comprobante, solicítalo al momento del pago.'
)
INFO_PRIMER_DIA = (
    'Para tu primer día trae ropa cómoda, calzado deportivo, toalla personal y agua. '
    'Puedes solicitar una evaluación inicial con nuestros entrenadores en sala para armar tu rutina '
    'y conocer cómo funciona el ingreso al gimnasio.'
)
INFO_CONTACTO_SOPORTE = (
    'Si tienes dudas con tu cuenta, tu ingreso o tu membresía, acércate directamente a recepción '
    'en el horario de atención del gimnasio o consulta con el administrador del sistema.'
)

PANTALLAS = {
    'historial-ventas': ['historial de ventas', 'historial de venta'],
    'metodos-pago': ['metodos de pago', 'metodo de pago'],
    'configuracion': ['tipo de cambio', 'configuracion'],
    'entrenadores': ['entrenadores', 'gestionar entrenadores'],
    'planes': ['gestionar planes', 'planes de membresia', 'planes'],
    'ventas': ['venta', 'ventas', 'pos', 'punto de venta', 'vender'],
    'caja': ['caja', 'arqueo'],
    'acceso': ['acceso', 'ingreso', 'validar', 'entrada de socio'],
    'reportes': ['reporte', 'reportes'],
    'dashboard': ['dashboard', 'tablero', 'estadistica', 'estadisticas', 'panel'],
    'rrhh': ['personal', 'recursos humanos', 'planilla', 'asistencia', 'contrato laboral', 'turnos'],
    'productos': ['producto', 'productos', 'inventario'],
    'proveedores': ['proveedor', 'proveedores'],
    'compras': ['compra', 'compras'],
    'categorias': ['categoria', 'categorias'],
    'kardex': ['kardex'],
    'alertas': ['alerta', 'alertas'],
    'entrenamiento': ['entrenamiento', 'rutina', 'rutinas', 'ejercicio', 'ejercicios'],
    'contrato': ['membresia', 'membresias', 'renovar', 'contrato', 'registrar contrato'],
    'registrar-socio': ['nuevo socio', 'registrar socio', 'agregar socio'],
    'usuarios': ['usuarios', 'gestionar usuarios'],
    'bitacora': ['bitacora', 'auditoria'],
    'inicio': ['inicio', 'principal'],
}
PERMISOS_PANTALLA = {
    'historial-ventas': ('es_administrador',),
    'metodos-pago': ('es_administrador',),
    'configuracion': ('es_administrador',),
    'entrenadores': ('es_administrador',),
    'planes': ('es_administrador',),
    'ventas': ('es_administrador', 'es_recepcionista'),
    'caja': ('es_administrador', 'es_recepcionista'),
    'acceso': ('es_administrador', 'es_recepcionista', 'es_socio'),
    'reportes': ('es_administrador', 'es_recepcionista', 'es_entrenador'),
    'dashboard': ('es_administrador', 'es_recepcionista', 'es_entrenador'),
    'rrhh': ('es_administrador', 'es_recepcionista', 'es_entrenador'),
    'productos': ('es_administrador',),
    'proveedores': ('es_administrador',),
    'compras': ('es_administrador',),
    'categorias': ('es_administrador',),
    'kardex': ('es_administrador',),
    'alertas': ('es_administrador',),
    'entrenamiento': ('es_administrador', 'es_entrenador', 'es_socio'),
    'contrato': ('es_administrador', 'es_recepcionista'),
    'registrar-socio': ('es_administrador', 'es_recepcionista'),
    'usuarios': ('es_administrador',),
    'bitacora': ('es_administrador',),
    'inicio': ('es_administrador', 'es_recepcionista', 'es_entrenador', 'es_socio'),
}


def normalizar(texto):
    t = unicodedata.normalize('NFD', texto.lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9ñ ]', ' ', t)


def tiene(t, *palabras):
    return any(re.search(rf'\b{re.escape(p)}', t) for p in palabras)


def puede(u, pantalla):
    return any(getattr(u, r, False) for r in PERMISOS_PANTALLA.get(pantalla, ()))


def _nombre(u):
    return u.first_name or u.username


def _r(respuesta, sugerencias=None, pantalla=None):
    return {'respuesta': respuesta, 'sugerencias': sugerencias or [],
            'accion': {'tipo': 'navegar', 'pantalla': pantalla} if pantalla else None}


def sugerencias_para(u):
    if u.es_administrador:
        return ['¿Cuánto vendimos hoy?', '¿Qué productos tienen stock bajo?', '¿Qué socios vencen pronto?', '¿Cuántos socios hay?', 'Abrir dashboard']
    if u.es_recepcionista:
        return ['¿Qué socios vencen pronto?', '¿Cuántos ingresaron hoy?', 'Ver planes y precios', '¿Cuántos socios hay?', 'Abrir control de acceso']
    if u.es_entrenador:
        return ['¿Cuántos socios entreno?', 'Mis horarios', 'Ver entrenadores', 'Abrir entrenamiento', 'Horario del gimnasio']
    return [
        '¿Cuándo vence mi membresía?',
        '¿Cuál es mi rutina?',
        '¿Quién es mi entrenador?',
        '¿Cuántas veces vine este mes?',
        'Mis últimas visitas',
        'Reglas del gimnasio',
        '¿Cómo pago o renuevo?',
    ]


def responder(u, mensaje):
    t = normalizar(mensaje)
    socio = Socio.objects.filter(id_socio=u).first() if u.es_socio else None
    hoy = timezone.localdate()

    # 1) Navegación: "abrir / ir a / ver / mostrar <pantalla>"
    if tiene(t, 'abrir', 'abre', 'ir a', 've a', 'llevame', 'mostrar', 'muestrame', 'entrar') \
            and not tiene(t, 'mi rutina', 'mi membresia', 'mi plan', 'mi entrenador', 'mis visitas', 'mis horarios'):
        for pantalla, claves in PANTALLAS.items():
            if any(re.search(rf'\b{re.escape(c)}', t) for c in claves):
                if not puede(u, pantalla):
                    return _r('Su perfil no tiene acceso a esa sección.', sugerencias_para(u))
                return _r(f'Listo, abriendo {pantalla.replace("-", " ")}.', [], pantalla)

    # 2) Saludo / despedida / ayuda
    if tiene(t, 'hola', 'buenas', 'buenos dias', 'buenas tardes', 'buenas noches'):
        return _r(f'¡Hola, {_nombre(u)}! Soy PorkyBot, el asistente de Porky Gym. ¿En qué te ayudo?', sugerencias_para(u))
    if tiene(t, 'gracias', 'muchas gracias', 'adios', 'chau', 'hasta luego', 'nos vemos'):
        return _r(f'¡A ti, {_nombre(u)}! Aquí estaré si necesitas algo más en Porky Gym.', sugerencias_para(u))
    if tiene(t, 'ayuda', 'que puedes', 'que sabes', 'opciones', 'comandos'):
        return _r('Puedo responder sobre membresías, rutinas, ejercicios, horarios, planes, precios, reglas, contacto y métodos de pago'
                  + (', ventas, stock, socios y vencimientos' if (u.es_administrador or u.es_recepcionista) else '')
                  + (', mis asignaciones y horarios' if u.es_entrenador else '')
                  + '. También puedo abrir pantallas: di por ejemplo "abrir reportes". Usa el micrófono para hablarme.',
                  sugerencias_para(u))

    # 3) Horario, reglas, pagos, planes, ejercicios, contacto y entrenadores (cualquier perfil)
    if tiene(t, 'horario del gimnasio', 'a que hora', 'abren', 'cierran', 'atencion', 'horario de atencion', 'feriado', 'domingo') or t.strip() == 'horario':
        return _r(f'Horario de atención: {HORARIO_GIMNASIO}', sugerencias_para(u))

    if tiene(t, 'regla', 'reglas', 'norma', 'normas', 'toalla', 'piscina', 'convivencia', 'requisito'):
        return _r(REGLAS_GIMNASIO, sugerencias_para(u))

    if tiene(t, 'primer dia', 'primera vez', 'que llevo', 'que debo llevar', 'empezar', 'comenzar'):
        return _r(INFO_PRIMER_DIA, sugerencias_para(u))

    if tiene(t, 'como pago', 'donde pago', 'metodo de pago', 'metodos de pago', 'qr', 'transferencia', 'tarjeta', 'efectivo', 'inscribirme'):
        return _r(INFO_PAGO_RENOVACION, sugerencias_para(u))

    if tiene(t, 'contacto', 'soporte', 'recepcion', 'ayuda con mi cuenta', 'telefono', 'ubicacion'):
        return _r(INFO_CONTACTO_SOPORTE, sugerencias_para(u))

    if (re.search(r'\bplan(es)?\b', t) or tiene(t, 'precio', 'precios', 'costo', 'cuesta', 'tarifa')) \
            and not tiene(t, 'vence', 'mi plan', 'vencimiento', 'planilla'):
        planes = PlanMembresia.objects.filter(estado__iexact='Activo').order_by('costo_base_origen')
        if not planes:
            return _r('Por ahora no hay planes activos registrados.')
        lineas = [f'• {p.nombre_plan}: Bs {p.costo_base_origen} por {p.duracion_dias} días'
                  + (' (incluye piscina)' if p.acceso_piscina else '') for p in planes]
        return _r('Planes vigentes:\n' + '\n'.join(lineas), sugerencias_para(u))

    if tiene(t, 'catalogo de ejercicios', 'que ejercicios hay', 'ejercicios disponibles', 'lista de ejercicios') \
            and not tiene(t, 'mi rutina', 'que hago hoy'):
        ejercicios = Ejercicio.objects.order_by('nombre_ejercicio')[:10]
        if not ejercicios:
            return _r('Aún no hay ejercicios cargados en el catálogo.', sugerencias_para(u))
        lineas = [f'• {e.nombre_ejercicio}' + (f' ({e.equipo_requerido})' if getattr(e, 'equipo_requerido', None) else '')
                  for e in ejercicios]
        return _r('Algunos ejercicios registrados:\n' + '\n'.join(lineas), sugerencias_para(u))

    if tiene(t, 'entrenador', 'entrenadores', 'coach', 'instructor') and not tiene(t, 'mi entrenador', 'mi coach'):
        ents = Entrenador.objects.filter(estado='Activo').select_related('id_entrenador')[:8]
        if not ents:
            return _r('No hay entrenadores activos registrados.')
        lineas = []
        for e in ents:
            dias = sorted({h.dia_semana for h in HorarioEntrenador.objects.filter(id_entrenador=e)})
            lineas.append(f'• {_nombre(e.id_entrenador)} {e.id_entrenador.last_name} — {e.especialidad or "General"}'
                          + (f' ({", ".join(dias)})' if dias else ''))
        return _r('Nuestro equipo de entrenadores:\n' + '\n'.join(lineas), sugerencias_para(u))

    # 4) Socio
    if socio:
        if tiene(t, 'membresia', 'vence', 'vencimiento', 'mi plan', 'caduca', 'renovar'):
            m = resumen_membresia(socio)
            if m['tiene_membresia']:
                extra = ' ¡Te recomiendo renovar pronto!' if m['dias_restantes'] <= 3 else ''
                return _r(f"Tu plan {m['plan']} está vigente hasta el {m['fecha_vencimiento']} "
                          f"({m['dias_restantes']} día(s) restantes).{extra}", sugerencias_para(u))
            return _r('No tienes una membresía vigente. Acércate a recepción para renovarla.', sugerencias_para(u))

        if tiene(t, 'mi entrenador', 'mi coach', 'quien me entrena'):
            a = (AsignacionRutina.objects.filter(id_socio=socio, estado='Activa')
                 .select_related('id_entrenador__id_entrenador').order_by('-fecha_asignacion').first())
            if not a or not a.id_entrenador:
                return _r('Aún no tienes un entrenador asignado. Consulta en recepción o en sala.', sugerencias_para(u))
            ent_u = a.id_entrenador.id_entrenador
            return _r(f'Tu entrenador asignado es {_nombre(ent_u)} {ent_u.last_name} (turno {a.turno}).',
                      sugerencias_para(u))

        if tiene(t, 'rutina', 'entrenamiento', 'ejercicio', 'ejercicios', 'que hago hoy', 'que entreno'):
            a = (AsignacionRutina.objects.filter(id_socio=socio, estado='Activa').select_related('id_rutina')
                 .order_by('-fecha_asignacion').first())
            if not a:
                return _r('Aún no tienes una rutina asignada. Pídele a tu entrenador que te asigne una.', sugerencias_para(u))
            ejercicios = DetalleRutina.objects.filter(id_rutina=a.id_rutina).select_related('id_ejercicio')
            lineas = [f'{d.orden}. {d.id_ejercicio.nombre_ejercicio}: {d.series}x{d.repeticiones}' for d in ejercicios]
            return _r(f'Tu rutina "{a.id_rutina.nombre_rutina}" ({a.id_rutina.nivel}, turno {a.turno}):\n' + '\n'.join(lineas),
                      sugerencias_para(u), None)

        if tiene(t, 'mis ultimas visitas', 'ultimas visitas', 'historial de ingresos', 'historial de visitas'):
            visitas = MarcacionAcceso.objects.filter(id_socio=socio, tipo_acceso='PERMITIDO').order_by('-fecha_hora')[:5]
            if not visitas:
                return _r('Aún no tienes ingresos permitidos registrados.', sugerencias_para(u))
            lineas = [f'• {timezone.localtime(v.fecha_hora).strftime("%d/%m/%Y %H:%M")}' for v in visitas]
            return _r('Tus últimos ingresos permitidos:\n' + '\n'.join(lineas), sugerencias_para(u))

        if tiene(t, 'ultimo ingreso', 'ultima vez', 'no pude entrar', 'denegado', 'problema al entrar'):
            ult = MarcacionAcceso.objects.filter(id_socio=socio).order_by('-fecha_hora').first()
            if not ult:
                return _r('Aún no tienes marcaciones de acceso registradas.', sugerencias_para(u))
            fecha_txt = timezone.localtime(ult.fecha_hora).strftime('%d/%m/%Y %H:%M')
            if ult.tipo_acceso == 'PERMITIDO':
                return _r(f'Tu último ingreso registrado fue el {fecha_txt} (Permitido).', sugerencias_para(u))
            return _r(f'Tu último intento de ingreso fue el {fecha_txt} y figura como DENEGADO. '
                      'Verifica si tu membresía está vigente o consulta en recepción.', sugerencias_para(u))

        if tiene(t, 'cuantas veces', 'visitas', 'vine', 'asistencia', 'ingresos', 'racha'):
            n = (MarcacionAcceso.objects.filter(id_socio=socio, tipo_acceso='PERMITIDO', fecha_hora__date__gte=hoy.replace(day=1))
                 .dates('fecha_hora', 'day').count())
            return _r(f'Este mes viniste {n} día(s). ¡Sigue así!' if n else 'Este mes todavía no registras ingresos. ¡Te esperamos!',
                      sugerencias_para(u))

    # 5) Personal
    if u.es_administrador or u.es_recepcionista:
        if tiene(t, 'cuantos socios', 'total de socios', 'socios activos', 'cantidad de socios'):
            activos = ContratoMembresia.objects.filter(
                fecha_inicio__lte=hoy, fecha_vencimiento__gte=hoy
            ).values('id_socio_id').distinct().count()
            socios_qs = Socio.objects.select_related('id_socio').order_by('id_socio__first_name', 'id_socio__username')
            total_socios = socios_qs.count()
            muestra = list(socios_qs[:15])
            if not muestra:
                return _r(
                    f'Hay {total_socios} socio(s) registrados en total, de los cuales {activos} tienen membresía vigente hoy.',
                    sugerencias_para(u)
                )
            lineas = []
            for s in muestra:
                nombre_completo = f'{_nombre(s.id_socio)} {s.id_socio.last_name}'.strip()
                m = resumen_membresia(s, hoy=hoy)
                if m['tiene_membresia']:
                    detalle = f" — {m['plan']} ({m['dias_restantes']}d)"
                elif m['estado'] == 'Vencida':
                    detalle = ' — Vencida'
                else:
                    detalle = ' — Sin membresía'
                lineas.append(f'• {nombre_completo}{detalle}')
            pie = f'\n(Mostrando {len(muestra)} de {total_socios} socios)' if total_socios > len(muestra) else ''
            return _r(
                f'Hay {total_socios} socio(s) registrados en total, de los cuales {activos} tienen membresía vigente hoy:\n'
                + '\n'.join(lineas)
                + pie,
                sugerencias_para(u)
            )

        m_socio = re.search(
            r'\b(?:plan|membresia|vencimiento|vence|tiempo|dias|estado|tiene)\b.*?\b(?:de|del socio|socio|a)\s+([a-zñ0-9]+(?:\s+[a-zñ0-9]+)?)',
            t
        )
        if m_socio and not tiene(t, 'mi plan', 'mi membresia', 'mis dias', 'cuantos socios', 'socios registrados'):
            nombre_buscado = m_socio.group(1).strip()
            if nombre_buscado not in ('los socios', 'socios', 'hoy', 'este mes'):
                coincidencias = list(
                    Socio.objects.select_related('id_socio').filter(
                        Q(id_socio__first_name__icontains=nombre_buscado)
                        | Q(id_socio__last_name__icontains=nombre_buscado)
                        | Q(id_socio__username__icontains=nombre_buscado)
                    )[:5]
                )
                if not coincidencias:
                    return _r(f'No encontré ningún socio que coincida con "{nombre_buscado}".', sugerencias_para(u))
                if len(coincidencias) > 1:
                    nombres = [f'• {_nombre(s.id_socio)} {s.id_socio.last_name}'.strip() for s in coincidencias]
                    return _r(
                        f'Encontré varios socios con "{nombre_buscado}", indica nombre y apellido:\n' + '\n'.join(nombres),
                        sugerencias_para(u)
                    )

                s_obj = coincidencias[0]
                nombre_s = f'{_nombre(s_obj.id_socio)} {s_obj.id_socio.last_name}'.strip()
                m = resumen_membresia(s_obj, hoy=hoy)
                if m['tiene_membresia']:
                    return _r(
                        f"{nombre_s} tiene el plan {m['plan']}, vigente hasta el {m['fecha_vencimiento']} "
                        f"({m['dias_restantes']} día(s) restantes).",
                        sugerencias_para(u)
                    )
                if m['estado'] == 'Vencida':
                    return _r(
                        f"{nombre_s} tiene su membresía vencida (último plan: {m['plan']}, venció el {m['fecha_vencimiento']}).",
                        sugerencias_para(u)
                    )
                return _r(f'{nombre_s} no tiene una membresía registrada actualmente.', sugerencias_para(u))

        if tiene(t, 'socios registrados', 'lista de socios', 'listado de socios', 'quienes son los socios', 'ver socios'):
            socios_qs = Socio.objects.select_related('id_socio').order_by('id_socio__first_name', 'id_socio__username')
            total_socios = socios_qs.count()
            muestra = list(socios_qs[:15])
            if not muestra:
                return _r('No hay socios registrados en el sistema.', sugerencias_para(u))
            lineas = []
            for s in muestra:
                nombre_completo = f'{_nombre(s.id_socio)} {s.id_socio.last_name}'.strip()
                m = resumen_membresia(s, hoy=hoy)
                if m['tiene_membresia']:
                    detalle = f" — {m['plan']} ({m['dias_restantes']}d)"
                elif m['estado'] == 'Vencida':
                    detalle = ' — Vencida'
                else:
                    detalle = ' — Sin membresía'
                lineas.append(f'• {nombre_completo}{detalle}')
            pie = f'\n(Mostrando {len(muestra)} de {total_socios} socios)' if total_socios > len(muestra) else ''
            return _r('Socios registrados:\n' + '\n'.join(lineas) + pie, sugerencias_para(u))

        if tiene(t, 'membresias de hoy', 'contratos de hoy', 'nuevas membresias', 'inscripciones de hoy'):
            contratos = ContratoMembresia.objects.filter(fecha_inicio=hoy)
            monto = contratos.aggregate(t=Sum('monto_pagado_local'))['t'] or 0
            return _r(f'Hoy se registraron {contratos.count()} contrato(s) de membresía por un total de Bs {monto}.',
                      sugerencias_para(u))
        if tiene(t, 'vencen', 'por vencer', 'vencimientos', 'vence pronto', 'vencen pronto'):
            from .extras_views import socios_por_vencer
            lista = socios_por_vencer(hoy)
            if not lista:
                return _r('Ningún socio vence en los próximos 3 días.', sugerencias_para(u))
            return _r('Socios que vencen en los próximos 3 días:\n' + '\n'.join(
                f"• {f['socio']} ({f['plan']}) — {'hoy' if f['dias'] == 0 else str(f['dias']) + ' día(s)'}" for f in lista[:10]),
                sugerencias_para(u))
        if tiene(t, 'ingresaron', 'entraron', 'accesos', 'cuantos vinieron', 'asistieron'):
            qs = MarcacionAcceso.objects.filter(fecha_hora__date=hoy)
            return _r(f"Hoy se registraron {qs.filter(tipo_acceso='PERMITIDO').count()} ingresos permitidos y "
                      f"{qs.filter(tipo_acceso='DENEGADO').count()} denegados.", sugerencias_para(u))
        if tiene(t, 'stock', 'agotado', 'agotados', 'inventario', 'reponer', 'falta'):
            bajos = Producto.objects.filter(estado__iexact='Activo', stock_actual__lte=F('stock_minimo')).order_by('stock_actual')[:10]
            if not bajos:
                return _r('Todos los productos tienen stock suficiente. ', sugerencias_para(u))
            return _r('Productos con stock bajo:\n' + '\n'.join(f'• {p.nombre_producto}: {p.stock_actual} (mín. {p.stock_minimo})' for p in bajos),
                      sugerencias_para(u), 'alertas' if u.es_administrador else None)
        if tiene(t, 'vendimos', 'ventas', 'vendido', 'ingresos de hoy', 'recaudado', 'cuanto se vendio'):
            v = Venta.objects.filter(fecha_hora__date=hoy)
            total = v.aggregate(t=Sum('monto_total_local'))['t'] or 0
            mem = ContratoMembresia.objects.filter(fecha_inicio=hoy).aggregate(t=Sum('monto_pagado_local'))['t'] or 0
            texto = f'Hoy: {v.count()} venta(s) POS por Bs {total} y Bs {mem} en membresías.'
            if u.es_administrador:
                inicio = hoy.replace(day=1)
                vm = Venta.objects.filter(fecha_hora__date__gte=inicio).aggregate(t=Sum('monto_total_local'))['t'] or 0
                texto += f' En el mes van Bs {vm} en ventas POS.'
            return _r(texto, sugerencias_para(u))

    if u.es_entrenador:
        if tiene(t, 'mis horarios', 'que dias trabajo', 'mi turno', 'mi horario'):
            horarios = HorarioEntrenador.objects.filter(id_entrenador__id_entrenador=u).order_by('dia_semana')
            if not horarios:
                return _r('No tienes horarios asignados registrados en el sistema.', sugerencias_para(u))
            lineas = []
            for h in horarios:
                ini = getattr(h, 'hora_inicio', '')
                fin = getattr(h, 'hora_fin', '')
                rango = f' ({ini} - {fin})' if ini and fin else ''
                lineas.append(f'• {h.dia_semana}{rango}')
            return _r('Tus horarios registrados:\n' + '\n'.join(lineas), sugerencias_para(u))
        if tiene(t, 'socios', 'entreno', 'asignaciones', 'alumnos'):
            qs = AsignacionRutina.objects.filter(id_entrenador__id_entrenador=u, estado='Activa')
            return _r(f'Tienes {qs.values("id_socio").distinct().count()} socio(s) con {qs.count()} rutina(s) activa(s).', sugerencias_para(u))

    return _r('No entendí bien la consulta . Prueba con alguna de estas opciones:', sugerencias_para(u))
