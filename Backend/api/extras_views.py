# api/extras_views.py
# ==============================================================================
# FUNCIONALIDADES ADICIONALES
#   - Notificaciones (campana): stock bajo/agotado y recordatorios de vencimiento.
#   - Dashboard con estadísticas reales según el perfil.
#   - Panel del socio (membresía, rutina, accesos, avisos).
#   - Asistente virtual "PorkyBot" (chatbot con soporte de voz en el frontend).
# ==============================================================================
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .automatizacion import generar_recordatorios_vencimiento
from .chatbot import responder
from .membresias import resumen_membresia
from .models import (
    AsignacionRutina, ContratoMembresia, DetalleRutina, DetalleVentaProducto, MarcacionAcceso, MarcacionPersonal,
    Notificacion, Producto, Socio, Venta, ArqueoCaja,
)


# ------------------------------------------------------------------------------
# Notificaciones
# ------------------------------------------------------------------------------
class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ['id_notificacion', 'tipo', 'titulo', 'mensaje', 'pantalla', 'leida', 'enviada_correo', 'fecha_creacion']


class NotificacionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    GET  /api/notificaciones/            -> últimas 50 del usuario
    GET  /api/notificaciones/no-leidas/  -> {total}
    POST /api/notificaciones/<id>/leer/  -> marca una como leída
    POST /api/notificaciones/leer-todas/ -> marca todas
    """
    serializer_class = NotificacionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notificacion.objects.filter(id_usuario=self.request.user)

    def list(self, request, *args, **kwargs):
        generar_recordatorios_vencimiento()
        return Response(NotificacionSerializer(self.get_queryset()[:50], many=True).data)

    @action(detail=False, methods=['get'], url_path='no-leidas')
    def no_leidas(self, request):
        generar_recordatorios_vencimiento()
        return Response({'total': self.get_queryset().filter(leida=False).count()})

    @action(detail=True, methods=['post'])
    def leer(self, request, pk=None):
        actualizadas = self.get_queryset().filter(pk=pk).update(leida=True)
        if not actualizadas:
            return Response({'detail': 'Notificación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'ok': True})

    @action(detail=False, methods=['post'], url_path='leer-todas')
    def leer_todas(self, request):
        return Response({'actualizadas': self.get_queryset().filter(leida=False).update(leida=True)})


# ------------------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------------------
def _d(v):
    return str((v or Decimal('0')).quantize(Decimal('0.01')))


def socios_por_vencer(hoy, dias=3):
    filas = []
    contratos = (ContratoMembresia.objects
                 .filter(estado_membresia='Activa', fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=hoy + timedelta(days=dias))
                 .select_related('id_socio__id_socio', 'id_plan_mem').order_by('fecha_vencimiento'))
    vistos = set()
    for c in contratos:
        if c.id_socio_id in vistos:
            continue
        if ContratoMembresia.objects.filter(id_socio=c.id_socio, estado_membresia='Activa',
                                            fecha_vencimiento__gt=c.fecha_vencimiento).exists():
            continue
        vistos.add(c.id_socio_id)
        u = c.id_socio.id_socio
        filas.append({'socio': f'{u.first_name} {u.last_name}'.strip() or u.username, 'ci': u.ci or '',
                      'telefono': u.telefono or '', 'plan': c.id_plan_mem.nombre_plan,
                      'vence': c.fecha_vencimiento.isoformat(), 'dias': (c.fecha_vencimiento - hoy).days})
    return filas


class DashboardView(APIView):
    """GET /api/dashboard/ -> indicadores reales según el perfil del usuario."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        u = request.user
        if not (u.es_administrador or u.es_recepcionista or u.es_entrenador):
            return Response({'detail': 'El dashboard es para el personal del gimnasio.'}, status=status.HTTP_403_FORBIDDEN)
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        datos = {'fecha': hoy.isoformat(), 'perfil': 'Administrador' if u.es_administrador else ('Recepcionista' if u.es_recepcionista else 'Entrenador')}

        if u.es_administrador or u.es_recepcionista:
            ventas_hoy = Venta.objects.filter(fecha_hora__date=hoy)
            membr_hoy = ContratoMembresia.objects.filter(fecha_inicio=hoy)
            vigentes = (ContratoMembresia.objects.filter(estado_membresia='Activa', fecha_inicio__lte=hoy, fecha_vencimiento__gt=hoy)
                        .values('id_socio').distinct().count())
            accesos_hoy = MarcacionAcceso.objects.filter(fecha_hora__date=hoy)
            stock_bajo = Producto.objects.filter(estado__iexact='Activo', stock_actual__lte=F('stock_minimo')).order_by('stock_actual')
            por_vencer = socios_por_vencer(hoy)
            datos['kpis'] = {
                'ingresos_hoy': _d((ventas_hoy.aggregate(t=Sum('monto_total_local'))['t'] or 0) + (membr_hoy.aggregate(t=Sum('monto_pagado_local'))['t'] or 0)),
                'ventas_hoy': ventas_hoy.count(),
                'socios_activos': vigentes,
                'socios_total': Socio.objects.count(),
                'por_vencer': len(por_vencer),
                'accesos_hoy': accesos_hoy.filter(tipo_acceso='PERMITIDO').count(),
                'accesos_denegados_hoy': accesos_hoy.filter(tipo_acceso='DENEGADO').count(),
                'stock_bajo': stock_bajo.count(),
                'nuevos_socios_mes': Socio.objects.filter(fecha_registro__gte=inicio_mes).count(),
                'caja_abierta': ArqueoCaja.objects.filter(estado='ABIERTA').exists(),
                'personal_presente': MarcacionPersonal.objects.filter(fecha_hora__date=hoy, tipo_evento='ENTRADA')
                                     .values('id_contrato_laboral').distinct().count(),
            }
            # Ingresos de los últimos 14 días
            desde = hoy - timedelta(days=13)
            v = dict(Venta.objects.filter(fecha_hora__date__gte=desde).annotate(d=TruncDate('fecha_hora'))
                     .values('d').annotate(t=Sum('monto_total_local')).values_list('d', 't'))
            m = dict(ContratoMembresia.objects.filter(fecha_inicio__gte=desde).values('fecha_inicio')
                     .annotate(t=Sum('monto_pagado_local')).values_list('fecha_inicio', 't'))
            datos['ingresos_14_dias'] = [
                {'etiqueta': (desde + timedelta(days=i)).strftime('%d/%m'),
                 'ventas': float(v.get(desde + timedelta(days=i)) or 0),
                 'membresias': float(m.get(desde + timedelta(days=i)) or 0)} for i in range(14)]
            # Horas pico (últimos 7 días)
            h = dict(MarcacionAcceso.objects.filter(tipo_acceso='PERMITIDO', fecha_hora__date__gte=hoy - timedelta(days=6))
                     .annotate(hh=ExtractHour('fecha_hora')).values('hh').annotate(n=Count('pk')).values_list('hh', 'n'))
            datos['accesos_por_hora'] = [{'etiqueta': f'{x:02d}h', 'accesos': h.get(x, 0)} for x in range(5, 24)]
            datos['top_productos'] = [
                {'etiqueta': d['id_producto__nombre_producto'], 'cantidad': d['c']}
                for d in DetalleVentaProducto.objects.filter(id_venta__fecha_hora__date__gte=inicio_mes)
                .values('id_producto__nombre_producto').annotate(c=Sum('cantidad')).order_by('-c')[:5]]
            datos['membresias_por_plan'] = [
                {'etiqueta': d['id_plan_mem__nombre_plan'], 'socios': d['n']}
                for d in ContratoMembresia.objects.filter(estado_membresia='Activa', fecha_vencimiento__gt=hoy)
                .values('id_plan_mem__nombre_plan').annotate(n=Count('id_socio', distinct=True)).order_by('-n')]
            datos['por_vencer'] = por_vencer[:10]
            datos['stock_bajo'] = [{'producto': p.nombre_producto, 'stock': p.stock_actual, 'minimo': p.stock_minimo}
                                   for p in stock_bajo[:10]]
            if u.es_administrador:
                vm = Venta.objects.filter(fecha_hora__date__gte=inicio_mes).aggregate(t=Sum('monto_total_local'))['t'] or 0
                mm = ContratoMembresia.objects.filter(fecha_inicio__gte=inicio_mes).aggregate(t=Sum('monto_pagado_local'))['t'] or 0
                datos['kpis']['ingresos_mes'] = _d(vm + mm)
                datos['kpis']['ventas_mes'] = _d(vm)
                datos['kpis']['membresias_mes'] = _d(mm)

        if u.es_entrenador or u.es_administrador:
            asign = AsignacionRutina.objects.filter(estado='Activa')
            if not u.es_administrador:
                asign = asign.filter(id_entrenador__id_entrenador=u)
            datos['entrenamiento'] = {
                'asignaciones_activas': asign.count(),
                'socios_entrenados': asign.values('id_socio').distinct().count(),
                'por_nivel': [{'etiqueta': d['id_rutina__nivel'], 'asignaciones': d['n']}
                              for d in asign.values('id_rutina__nivel').annotate(n=Count('pk')).order_by('-n')],
            }
        return Response(datos)


# ------------------------------------------------------------------------------
# Panel del socio
# ------------------------------------------------------------------------------
class MiPanelView(APIView):
    """GET /api/mi-panel/ -> resumen para el socio autenticado."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        socio = Socio.objects.filter(id_socio=request.user).first()
        if socio is None:
            return Response({'detail': 'Solo disponible para socios.'}, status=status.HTTP_403_FORBIDDEN)
        generar_recordatorios_vencimiento()
        hoy = timezone.localdate()
        membresia = resumen_membresia(socio)
        asign = (AsignacionRutina.objects.filter(id_socio=socio, estado='Activa').select_related('id_rutina', 'id_entrenador__id_entrenador')
                 .order_by('-fecha_asignacion').first())
        rutina = None
        if asign:
            ent = asign.id_entrenador.id_entrenador
            rutina = {
                'nombre': asign.id_rutina.nombre_rutina, 'nivel': asign.id_rutina.nivel, 'turno': asign.turno,
                'entrenador': f'{ent.first_name} {ent.last_name}'.strip() or ent.username,
                'ejercicios': [{'orden': d.orden, 'ejercicio': d.id_ejercicio.nombre_ejercicio, 'series': d.series,
                                'repeticiones': d.repeticiones}
                               for d in DetalleRutina.objects.filter(id_rutina=asign.id_rutina).select_related('id_ejercicio')],
            }
        accesos = MarcacionAcceso.objects.filter(id_socio=socio, tipo_acceso='PERMITIDO')
        dias_mes = accesos.filter(fecha_hora__date__gte=hoy.replace(day=1)).dates('fecha_hora', 'day').count()
        # Racha: días consecutivos (hasta hoy o ayer) con al menos un ingreso.
        fechas = set(timezone.localtime(a.fecha_hora).date() for a in accesos.filter(fecha_hora__date__gte=hoy - timedelta(days=60)))
        racha, d = 0, hoy if hoy in fechas else hoy - timedelta(days=1)
        while d in fechas:
            racha += 1
            d -= timedelta(days=1)
        return Response({
            'membresia': membresia,
            'alerta_vencimiento': membresia['tiene_membresia'] and membresia['dias_restantes'] is not None and membresia['dias_restantes'] <= 3,
            'rutina': rutina,
            'visitas_mes': dias_mes,
            'racha_dias': racha,
            'ultimo_ingreso': timezone.localtime(accesos.order_by('-fecha_hora').first().fecha_hora).strftime('%d/%m/%Y %H:%M') if accesos.exists() else None,
            'notificaciones_no_leidas': Notificacion.objects.filter(id_usuario=request.user, leida=False).count(),
        })


# ------------------------------------------------------------------------------
# Chatbot
# ------------------------------------------------------------------------------
class ChatbotView(APIView):
    """POST /api/chatbot/ {mensaje} -> {respuesta, sugerencias, accion}"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mensaje = (request.data.get('mensaje') or '').strip()
        if not mensaje:
            return Response({'detail': 'Escriba un mensaje.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(mensaje) > 500:
            mensaje = mensaje[:500]
        return Response(responder(request.user, mensaje))
