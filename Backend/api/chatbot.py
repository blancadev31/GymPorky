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

from django.db.models import F, Sum
from django.utils import timezone

from .membresias import resumen_membresia
from .models import (
    AsignacionRutina, ContratoMembresia, DetalleRutina, Entrenador, HorarioEntrenador, MarcacionAcceso,
    PlanMembresia, Producto, Socio, Venta,
)

# Horario de atención del gimnasio (editable aquí).
HORARIO_GIMNASIO = 'Lunes a viernes de 06:00 a 22:00 y sábados de 07:00 a 14:00. Domingos y feriados cerrado.'

PANTALLAS = {
    'ventas': ['venta', 'ventas', 'pos', 'punto de venta', 'vender'],
    'caja': ['caja', 'arqueo'],
    'acceso': ['acceso', 'ingreso', 'validar', 'entrada de socio'],
    'reportes': ['reporte', 'reportes'],
    'dashboard': ['dashboard', 'tablero', 'estadistica', 'estadisticas', 'panel'],
    'rrhh': ['personal', 'recursos humanos', 'planilla', 'asistencia', 'contrato laboral', 'turnos'],
    'productos': ['producto', 'productos', 'inventario'],
    'kardex': ['kardex'],
    'alertas': ['alerta', 'alertas'],
    'entrenamiento': ['entrenamiento', 'rutina', 'rutinas', 'ejercicio', 'ejercicios'],
    'contrato': ['membresia', 'membresias', 'renovar', 'contrato'],
    'registrar-socio': ['nuevo socio', 'registrar socio'],
    'usuarios': ['usuarios'],
    'bitacora': ['bitacora', 'auditoria'],
    'inicio': ['inicio', 'principal'],
}
PERMISOS_PANTALLA = {
    'ventas': ('es_administrador', 'es_recepcionista'), 'caja': ('es_administrador', 'es_recepcionista'),
    'acceso': ('es_administrador', 'es_recepcionista', 'es_socio'), 'reportes': ('es_administrador', 'es_recepcionista', 'es_entrenador'),
    'dashboard': ('es_administrador', 'es_recepcionista', 'es_entrenador'), 'rrhh': ('es_administrador', 'es_recepcionista', 'es_entrenador'),
    'productos': ('es_administrador',), 'kardex': ('es_administrador',), 'alertas': ('es_administrador',),
    'entrenamiento': ('es_administrador', 'es_entrenador', 'es_socio'), 'contrato': ('es_administrador', 'es_recepcionista'),
    'registrar-socio': ('es_administrador', 'es_recepcionista'), 'usuarios': ('es_administrador',), 'bitacora': ('es_administrador',),
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
        return ['¿Cuánto vendimos hoy?', '¿Qué productos tienen stock bajo?', '¿Qué socios vencen pronto?', 'Abrir dashboard']
    if u.es_recepcionista:
        return ['¿Qué socios vencen pronto?', '¿Cuántos ingresaron hoy?', 'Ver planes y precios', 'Abrir control de acceso']
    if u.es_entrenador:
        return ['¿Cuántos socios entreno?', 'Ver entrenadores', 'Abrir entrenamiento', 'Horario del gimnasio']
    return ['¿Cuándo vence mi membresía?', '¿Cuál es mi rutina?', '¿Cuántas veces vine este mes?', 'Horario del gimnasio']


def responder(u, mensaje):
    t = normalizar(mensaje)
    socio = Socio.objects.filter(id_socio=u).first() if u.es_socio else None
    hoy = timezone.localdate()

    # 1) Navegación: "abrir / ir a / ver / mostrar <pantalla>"
    if tiene(t, 'abrir', 'abre', 'ir a', 've a', 'llevame', 'mostrar', 'muestrame', 'entrar'):
        for pantalla, claves in PANTALLAS.items():
            if any(re.search(rf'\b{re.escape(c)}', t) for c in claves):
                if not puede(u, pantalla):
                    return _r('Su perfil no tiene acceso a esa sección.', sugerencias_para(u))
                return _r(f'Listo, abriendo {pantalla.replace("-", " ")}.', [], pantalla)

    # 2) Saludo / ayuda
    if tiene(t, 'hola', 'buenas', 'buenos dias', 'buenas tardes'):
        return _r(f'¡Hola, {_nombre(u)}! Soy PorkyBot, el asistente de Porky Gym. ¿En qué te ayudo?', sugerencias_para(u))
    if tiene(t, 'ayuda', 'que puedes', 'que sabes', 'opciones', 'comandos'):
        return _r('Puedo responder sobre membresías, rutinas, horarios, planes y precios'
                  + (', ventas, stock y socios por vencer' if (u.es_administrador or u.es_recepcionista) else '')
                  + '. También puedo abrir pantallas: di por ejemplo "abrir reportes". Usa el micrófono para hablarme.',
                  sugerencias_para(u))

    # 3) Horario y planes (cualquier perfil)
    if tiene(t, 'horario del gimnasio', 'a que hora', 'abren', 'cierran', 'atencion', 'horario de atencion') or t.strip() == 'horario':
        return _r(f'Horario de atención: {HORARIO_GIMNASIO}', sugerencias_para(u))
    if (re.search(r'\bplan(es)?\b', t) or tiene(t, 'precio', 'precios', 'costo', 'cuesta', 'tarifa')) \
            and not tiene(t, 'vence', 'mi plan', 'vencimiento', 'planilla'):
        planes = PlanMembresia.objects.filter(estado__iexact='Activo').order_by('costo_base_origen')
        if not planes:
            return _r('Por ahora no hay planes activos registrados.')
        lineas = [f'• {p.nombre_plan}: Bs {p.costo_base_origen} por {p.duracion_dias} días'
                  + (' (incluye piscina)' if p.acceso_piscina else '') for p in planes]
        return _r('Planes vigentes:\n' + '\n'.join(lineas), sugerencias_para(u))
    if tiene(t, 'entrenador', 'entrenadores', 'coach', 'instructor'):
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
        if tiene(t, 'rutina', 'entrenamiento', 'ejercicio', 'ejercicios', 'que hago hoy', 'que entreno'):
            a = (AsignacionRutina.objects.filter(id_socio=socio, estado='Activa').select_related('id_rutina')
                 .order_by('-fecha_asignacion').first())
            if not a:
                return _r('Aún no tienes una rutina asignada. Pídele a tu entrenador que te asigne una.', sugerencias_para(u))
            ejercicios = DetalleRutina.objects.filter(id_rutina=a.id_rutina).select_related('id_ejercicio')
            lineas = [f'{d.orden}. {d.id_ejercicio.nombre_ejercicio}: {d.series}x{d.repeticiones}' for d in ejercicios]
            return _r(f'Tu rutina "{a.id_rutina.nombre_rutina}" ({a.id_rutina.nivel}, turno {a.turno}):\n' + '\n'.join(lineas),
                      sugerencias_para(u), None)
        if tiene(t, 'cuantas veces', 'visitas', 'vine', 'asistencia', 'ingresos', 'racha'):
            n = (MarcacionAcceso.objects.filter(id_socio=socio, tipo_acceso='PERMITIDO', fecha_hora__date__gte=hoy.replace(day=1))
                 .dates('fecha_hora', 'day').count())
            return _r(f'Este mes viniste {n} día(s). ¡Sigue así!' if n else 'Este mes todavía no registras ingresos. ¡Te esperamos!',
                      sugerencias_para(u))

    # 5) Personal
    if u.es_administrador or u.es_recepcionista:
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

    if u.es_entrenador and tiene(t, 'socios', 'entreno', 'asignaciones', 'alumnos'):
        qs = AsignacionRutina.objects.filter(id_entrenador__id_entrenador=u, estado='Activa')
        return _r(f'Tienes {qs.values("id_socio").distinct().count()} socio(s) con {qs.count()} rutina(s) activa(s).', sugerencias_para(u))

    return _r('No entendí bien la consulta . Prueba con alguna de estas opciones:', sugerencias_para(u))
