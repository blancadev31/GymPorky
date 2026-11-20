# api/automatizacion.py
# ==============================================================================
# FUNCIONALIDADES ADICIONALES — PROCESOS AUTOMÁTICOS
#   1) Kardex automático: toda venta POS y toda compra registran su movimiento
#      en el kardex sin intervención del usuario.
#   2) Control de stock: al bajar del mínimo se abre la alerta de reposición,
#      se notifica a administradores (campana + correo) y se cierra sola cuando
#      el stock se recupera.
#   3) Recordatorios de vencimiento: a los socios que les faltan 3, 2 o 1 día(s)
#      (o vence hoy) se les envía un aviso en la campana y por correo; recepción
#      recibe el mismo aviso para ofrecer la renovación.
# Ninguna de estas tareas debe interrumpir la operación principal: los errores
# se registran en el log y la venta/compra continúa.
# ==============================================================================
import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    Administrador, AlertaReposicion, ContratoMembresia, KardexInventario, Notificacion, Usuario,
)

logger = logging.getLogger(__name__)
DIAS_RECORDATORIO = (3, 2, 1, 0)


# ------------------------------------------------------------------------------
# Notificaciones
# ------------------------------------------------------------------------------
def notificar(usuario, tipo, titulo, mensaje, referencia, pantalla=None, correo=False):
    """Crea la notificación si no existe (idempotente). Devuelve la notificación o None."""
    try:
        with transaction.atomic():
            n, creada = Notificacion.objects.get_or_create(
                id_usuario=usuario, referencia=referencia[:120],
                defaults={'tipo': tipo, 'titulo': titulo[:150], 'mensaje': mensaje, 'pantalla': pantalla},
            )
    except IntegrityError:
        return None
    if creada and correo and usuario.email:
        def _enviar():
            try:
                from .emails import enviar_correo_brevo
                html = (f'<h2 style="color:#ca8a04">Porky Gym</h2><h3>{titulo}</h3><p>{mensaje}</p>'
                        '<p style="color:#666;font-size:12px">Mensaje automático del Sistema Porky Gym.</p>')
                if enviar_correo_brevo(usuario.email, f'Porky Gym - {titulo}', html):
                    Notificacion.objects.filter(pk=n.pk).update(enviada_correo=True)
            except Exception:  # pragma: no cover - el correo nunca debe romper el flujo
                logger.exception('No se pudo enviar el correo de notificación')
        transaction.on_commit(_enviar)
    return n if creada else None


def administradores():
    return Usuario.objects.filter(es_administrador=True, is_active=True)


def personal_recepcion():
    return Usuario.objects.filter(is_active=True).filter(es_recepcionista=True) | administradores()


# ------------------------------------------------------------------------------
# Kardex automático y control de stock
# ------------------------------------------------------------------------------
def registrar_kardex(producto, tipo, cantidad, motivo):
    """Registra el movimiento en el kardex (tipo: INGRESO / SALIDA)."""
    return KardexInventario.objects.create(id_producto=producto, tipo_movimiento=tipo, cantidad=cantidad, motivo=motivo[:100])


def revisar_stock(producto):
    """Abre/actualiza/cierra la alerta de reposición y notifica si corresponde."""
    try:
        producto.refresh_from_db(fields=['stock_actual', 'stock_minimo', 'stock_maximo', 'estado'])
        pendiente = AlertaReposicion.objects.filter(id_producto=producto, estado_alerta='Pendiente').first()
        if producto.stock_actual > producto.stock_minimo:
            if pendiente:
                pendiente.estado_alerta = 'Cerrada'
                pendiente.fecha_cierre = timezone.now()
                pendiente.save(update_fields=['estado_alerta', 'fecha_cierre'])
            return None
        if (producto.estado or '').lower() != 'activo':
            return None

        agotado = producto.stock_actual <= 0
        urgencia = 'Agotado' if agotado else 'Bajo'
        sugerida = max(1, (producto.stock_maximo or producto.stock_minimo * 2) - producto.stock_actual)
        if pendiente:
            pendiente.nivel_urgencia = urgencia
            pendiente.cantidad_sugerida = sugerida
            pendiente.save(update_fields=['nivel_urgencia', 'cantidad_sugerida'])
        else:
            admin_usuario = administradores().first()
            if admin_usuario:
                admin, _ = Administrador.objects.get_or_create(id_administrador=admin_usuario)
                pendiente = AlertaReposicion.objects.create(
                    id_admin=admin, id_producto=producto, nivel_urgencia=urgencia, cantidad_sugerida=sugerida,
                    codigo_evento_global='AUTO')

        tipo = 'STOCK_AGOTADO' if agotado else 'STOCK_BAJO'
        titulo = f"{'Producto agotado' if agotado else 'Stock bajo'}: {producto.nombre_producto}"
        mensaje = (f"Quedan {producto.stock_actual} unidad(es) de {producto.nombre_producto} "
                   f"(mínimo {producto.stock_minimo}). Se sugiere comprar {sugerida} unidad(es).")
        # Una notificación por producto, nivel y día: evita saturar la campana.
        ref = f'stock-{producto.pk}-{tipo}-{timezone.localdate().isoformat()}'
        for u in administradores():
            notificar(u, tipo, titulo, mensaje, ref, pantalla='alertas', correo=True)
        return pendiente
    except Exception:  # pragma: no cover
        logger.exception('Error al revisar el stock del producto %s', getattr(producto, 'pk', None))
        return None


def procesar_venta(venta):
    """Kardex automático de una venta POS + control de stock."""
    for det in venta.detalleventaproducto_set.select_related('id_producto'):
        registrar_kardex(det.id_producto, 'SALIDA', det.cantidad, f'Venta POS #{venta.pk}')
        revisar_stock(det.id_producto)


def procesar_compra(compra):
    """Kardex automático de una compra + cierre de alertas si el stock se recuperó."""
    for det in compra.detallecompra_set.select_related('id_producto'):
        registrar_kardex(det.id_producto, 'INGRESO', det.cantidad, f'Compra #{compra.pk}')
        revisar_stock(det.id_producto)


# ------------------------------------------------------------------------------
# Recordatorios de vencimiento de membresía
# ------------------------------------------------------------------------------
_ultima_ejecucion = {'fecha': None}


def generar_recordatorios_vencimiento(forzar=False):
    """Avisa a socios (y a recepción) cuando faltan 3, 2, 1 o 0 días para el vencimiento.

    Es idempotente: cada aviso tiene una referencia única por contrato y día.
    Se ejecuta como máximo una vez por día y proceso, salvo ``forzar=True``
    (comando ``python manage.py enviar_recordatorios``).
    """
    hoy = timezone.localdate()
    if not forzar and _ultima_ejecucion['fecha'] == hoy:
        return 0
    _ultima_ejecucion['fecha'] = hoy
    creadas = 0
    limite = hoy + timedelta(days=max(DIAS_RECORDATORIO))
    contratos = (ContratoMembresia.objects
                 .filter(estado_membresia='Activa', fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=limite)
                 .select_related('id_socio__id_socio', 'id_plan_mem'))
    staff = list(personal_recepcion().distinct())
    for c in contratos:
        socio = c.id_socio
        # Si el socio ya renovó (tiene otro contrato que vence después), no se le avisa.
        if ContratoMembresia.objects.filter(id_socio=socio, estado_membresia='Activa',
                                            fecha_vencimiento__gt=c.fecha_vencimiento).exists():
            continue
        dias = (c.fecha_vencimiento - hoy).days
        if dias not in DIAS_RECORDATORIO:
            continue
        u = socio.id_socio
        nombre = f'{u.first_name} {u.last_name}'.strip() or u.username
        cuando = 'hoy' if dias == 0 else ('mañana' if dias == 1 else f'en {dias} días')
        titulo = f'Tu membresía vence {cuando}'
        mensaje = (f'Hola {nombre}, tu plan {c.id_plan_mem.nombre_plan} vence el '
                   f'{c.fecha_vencimiento.strftime("%d/%m/%Y")}. Renueva en recepción o en línea para no perder tu acceso.')
        if notificar(u, 'VENCIMIENTO', titulo, mensaje, f'venc-{c.pk}-{dias}', pantalla='inicio', correo=True):
            creadas += 1
        for s in staff:
            notificar(s, 'VENCIMIENTO', f'Membresía por vencer: {nombre}',
                      f'El plan {c.id_plan_mem.nombre_plan} de {nombre} (CI {u.ci or "-"}) vence {cuando} '
                      f'({c.fecha_vencimiento.strftime("%d/%m/%Y")}). Ofrézcale la renovación.',
                      f'venc-staff-{c.pk}-{dias}', pantalla='contrato')
    return creadas
