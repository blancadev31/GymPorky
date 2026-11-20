# api/rrhh_views.py
# ==============================================================================
# PAQUETE 6: RECURSOS HUMANOS, CONTROL DE ASISTENCIA Y PLANILLA DE SUELDOS
#   CU21: Administrar Contratos Laborales
#   CU22: Configurar Turnos y Horarios
#   CU23: Registrar Marcación de Asistencia de Personal
#   CU24: Liquidar Planilla de Pagos
# ==============================================================================
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    ContratoLaboral, HorarioLaboral, MarcacionPersonal, PagoPlanilla, Turno, Usuario, DIAS_SEMANA,
)
from .views import registrar_bitacora, EsAdministrador, _roles_texto

DIAS_POR_INDICE = [d[0] for d in DIAS_SEMANA]  # 0=Lunes ... 6=Domingo
DOS = Decimal('0.01')


def _nombre(usuario):
    return f'{usuario.first_name} {usuario.last_name}'.strip() or usuario.username


def contrato_activo(usuario, fecha=None):
    fecha = fecha or timezone.localdate()
    return (ContratoLaboral.objects
            .filter(id_usuario=usuario, estado='Activo', fecha_inicio__lte=fecha)
            .filter(Q(fecha_finalizacion__isnull=True) | Q(fecha_finalizacion__gte=fecha))
            .order_by('-fecha_inicio').first())


# ------------------------------------------------------------------------------
# SERIALIZERS
# ------------------------------------------------------------------------------
class ContratoLaboralSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.SerializerMethodField()
    empleado_username = serializers.CharField(source='id_usuario.username', read_only=True)
    empleado_roles = serializers.SerializerMethodField()

    class Meta:
        model = ContratoLaboral
        fields = ['id_contrato_laboral', 'id_usuario', 'empleado_nombre', 'empleado_username', 'empleado_roles',
                  'cargo', 'salario_mensual', 'fecha_inicio', 'fecha_finalizacion', 'estado']
        read_only_fields = ['estado']

    def get_empleado_nombre(self, obj):
        return _nombre(obj.id_usuario)

    def get_empleado_roles(self, obj):
        return _roles_texto(obj.id_usuario)

    def validate(self, attrs):
        usuario = attrs.get('id_usuario', getattr(self.instance, 'id_usuario', None))
        inicio = attrs.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        fin = attrs.get('fecha_finalizacion', getattr(self.instance, 'fecha_finalizacion', None))
        if usuario and not (usuario.es_administrador or usuario.es_recepcionista or usuario.es_entrenador):
            raise serializers.ValidationError(
                {'id_usuario': 'Solo se pueden contratar usuarios con rol de personal (Administrador, Recepcionista o Entrenador).'})
        if fin and inicio and fin < inicio:
            raise serializers.ValidationError({'fecha_finalizacion': 'La fecha de finalización no puede ser anterior a la de inicio.'})
        if attrs.get('salario_mensual') is not None and attrs['salario_mensual'] <= 0:
            raise serializers.ValidationError({'salario_mensual': 'El salario debe ser mayor a cero.'})
        if usuario:
            otros = ContratoLaboral.objects.filter(id_usuario=usuario, estado='Activo')
            if self.instance:
                otros = otros.exclude(pk=self.instance.pk)
            if otros.exists():
                raise serializers.ValidationError({'id_usuario': 'El empleado ya tiene un contrato laboral activo.'})
        return attrs


class TurnoGestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Turno
        fields = ['id_turno', 'nombre_turno', 'hora_inicio', 'hora_fin']

    def validate(self, attrs):
        ini = attrs.get('hora_inicio', getattr(self.instance, 'hora_inicio', None))
        fin = attrs.get('hora_fin', getattr(self.instance, 'hora_fin', None))
        if ini and fin and fin <= ini:
            raise serializers.ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la hora de inicio.'})
        return attrs


class HorarioLaboralSerializer(serializers.ModelSerializer):
    turno_nombre = serializers.CharField(source='id_turno.nombre_turno', read_only=True)
    hora_inicio = serializers.TimeField(source='id_turno.hora_inicio', read_only=True)
    hora_fin = serializers.TimeField(source='id_turno.hora_fin', read_only=True)
    empleado_nombre = serializers.SerializerMethodField()
    cargo = serializers.CharField(source='id_contrato_laboral.cargo', read_only=True)

    class Meta:
        model = HorarioLaboral
        fields = ['id', 'id_contrato_laboral', 'empleado_nombre', 'cargo', 'id_turno', 'turno_nombre',
                  'hora_inicio', 'hora_fin', 'dia_semana', 'tolerancia_minutos']

    def get_empleado_nombre(self, obj):
        return _nombre(obj.id_contrato_laboral.id_usuario)

    def validate(self, attrs):
        dia = attrs.get('dia_semana', getattr(self.instance, 'dia_semana', None))
        if dia not in DIAS_POR_INDICE:
            raise serializers.ValidationError({'dia_semana': f'Día inválido. Use: {", ".join(DIAS_POR_INDICE)}.'})
        contrato = attrs.get('id_contrato_laboral', getattr(self.instance, 'id_contrato_laboral', None))
        turno = attrs.get('id_turno', getattr(self.instance, 'id_turno', None))
        if contrato and contrato.estado != 'Activo':
            raise serializers.ValidationError({'id_contrato_laboral': 'Solo se asignan horarios a contratos activos.'})
        if contrato and turno and dia:
            cruces = HorarioLaboral.objects.filter(id_contrato_laboral=contrato, dia_semana=dia).select_related('id_turno')
            if self.instance:
                cruces = cruces.exclude(pk=self.instance.pk)
            for h in cruces:
                if turno.hora_inicio < h.id_turno.hora_fin and h.id_turno.hora_inicio < turno.hora_fin:
                    raise serializers.ValidationError(
                        {'id_turno': f'El turno se cruza con "{h.id_turno.nombre_turno}" el día {dia}.'})
        return attrs


def _evaluar_marcacion(marcacion):
    """Devuelve (estado, minutos_atraso) comparando contra el horario del día."""
    if marcacion.tipo_evento != 'ENTRADA':
        return 'Registrado', 0
    local = timezone.localtime(marcacion.fecha_hora)
    dia = DIAS_POR_INDICE[local.weekday()]
    horarios = (HorarioLaboral.objects.filter(id_contrato_laboral=marcacion.id_contrato_laboral, dia_semana=dia)
                .select_related('id_turno').order_by('id_turno__hora_inicio'))
    if not horarios:
        return 'Fuera de horario', 0
    # Se toma el turno cuya hora de inicio esté más cerca de la marcación.
    def distancia(h):
        ini = datetime.combine(local.date(), h.id_turno.hora_inicio)
        return abs((local.replace(tzinfo=None) - ini).total_seconds())
    h = min(horarios, key=distancia)
    inicio = datetime.combine(local.date(), h.id_turno.hora_inicio)
    minutos = int((local.replace(tzinfo=None) - inicio).total_seconds() // 60)
    if minutos > h.tolerancia_minutos:
        return 'Atraso', minutos
    return 'Puntual', 0


class MarcacionPersonalSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.SerializerMethodField()
    cargo = serializers.CharField(source='id_contrato_laboral.cargo', read_only=True)
    estado = serializers.SerializerMethodField()
    minutos_atraso = serializers.SerializerMethodField()

    class Meta:
        model = MarcacionPersonal
        fields = ['id_marcacion_personal', 'id_contrato_laboral', 'empleado_nombre', 'cargo', 'fecha_hora',
                  'tipo_evento', 'metodo', 'estado', 'minutos_atraso']
        read_only_fields = ['fecha_hora']

    def get_empleado_nombre(self, obj):
        return _nombre(obj.id_contrato_laboral.id_usuario)

    def get_estado(self, obj):
        return _evaluar_marcacion(obj)[0]

    def get_minutos_atraso(self, obj):
        return _evaluar_marcacion(obj)[1]


class PagoPlanillaSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.SerializerMethodField()
    cargo = serializers.CharField(source='id_contrato_laboral.cargo', read_only=True)

    class Meta:
        model = PagoPlanilla
        fields = ['id_pago_planilla', 'id_contrato_laboral', 'empleado_nombre', 'cargo', 'periodo_mes',
                  'periodo_anio', 'salario_base', 'bonos', 'descuentos', 'total_pagado', 'fecha_pagada']

    def get_empleado_nombre(self, obj):
        return _nombre(obj.id_contrato_laboral.id_usuario)


# ------------------------------------------------------------------------------
# CU21: ADMINISTRAR CONTRATOS LABORALES
# ------------------------------------------------------------------------------
class ContratoLaboralViewSet(viewsets.ModelViewSet):
    serializer_class = ContratoLaboralSerializer
    permission_classes = [EsAdministrador]

    def get_queryset(self):
        qs = ContratoLaboral.objects.select_related('id_usuario').order_by('-estado', '-fecha_inicio')
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def perform_create(self, serializer):
        c = serializer.save(estado='Activo')
        registrar_bitacora(self.request, 'CREATE', 'contrato_laboral',
                           f"Contrato laboral #{c.pk} para '{c.id_usuario.username}' ({c.cargo}, Bs {c.salario_mensual}).",
                           usuario=self.request.user)

    def perform_update(self, serializer):
        c = serializer.save()
        registrar_bitacora(self.request, 'UPDATE', 'contrato_laboral',
                           f"Se modificó el contrato laboral #{c.pk} de '{c.id_usuario.username}'.",
                           usuario=self.request.user)

    def destroy(self, request, *args, **kwargs):
        contrato = self.get_object()
        if contrato.pagoplanilla_set.exists() or contrato.marcacionpersonal_set.exists():
            return Response({'detail': 'El contrato tiene marcaciones o pagos registrados; finalícelo en lugar de eliminarlo.'},
                            status=status.HTTP_400_BAD_REQUEST)
        registrar_bitacora(request, 'DELETE', 'contrato_laboral',
                           f"Se eliminó el contrato laboral #{contrato.pk}.", usuario=request.user)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        contrato = self.get_object()
        if contrato.estado != 'Activo':
            return Response({'detail': 'El contrato ya está finalizado.'}, status=status.HTTP_400_BAD_REQUEST)
        fecha = request.data.get('fecha_finalizacion') or timezone.localdate().isoformat()
        contrato.fecha_finalizacion = fecha
        contrato.estado = 'Finalizado'
        contrato.save(update_fields=['fecha_finalizacion', 'estado'])
        registrar_bitacora(request, 'UPDATE', 'contrato_laboral',
                           f"Se finalizó el contrato laboral #{contrato.pk} ({fecha}).", usuario=request.user)
        return Response(ContratoLaboralSerializer(contrato).data)

    @action(detail=False, methods=['get'], url_path='empleados-disponibles')
    def empleados_disponibles(self, request):
        usuarios = Usuario.objects.filter(Q(es_administrador=True) | Q(es_recepcionista=True) | Q(es_entrenador=True))
        con_contrato = set(ContratoLaboral.objects.filter(estado='Activo').values_list('id_usuario', flat=True))
        return Response([
            {'id': u.id, 'username': u.username, 'nombre': _nombre(u), 'roles': _roles_texto(u),
             'tiene_contrato_activo': u.id in con_contrato}
            for u in usuarios.order_by('username')
        ])


# ------------------------------------------------------------------------------
# CU22: CONFIGURAR TURNOS Y HORARIOS
# ------------------------------------------------------------------------------
class TurnoGestionViewSet(viewsets.ModelViewSet):
    queryset = Turno.objects.all().order_by('hora_inicio')
    serializer_class = TurnoGestionSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.IsAuthenticated()]
        return [EsAdministrador()]

    def perform_create(self, serializer):
        t = serializer.save()
        registrar_bitacora(self.request, 'CREATE', 'turno', f"Turno '{t.nombre_turno}' creado.", usuario=self.request.user)

    def perform_update(self, serializer):
        t = serializer.save()
        registrar_bitacora(self.request, 'UPDATE', 'turno', f"Turno '{t.nombre_turno}' modificado.", usuario=self.request.user)

    def destroy(self, request, *args, **kwargs):
        turno = self.get_object()
        if HorarioLaboral.objects.filter(id_turno=turno).exists() or turno.horarioentrenador_set.exists():
            return Response({'detail': 'El turno está asignado a horarios; no puede eliminarse.'},
                            status=status.HTTP_400_BAD_REQUEST)
        nombre = turno.nombre_turno
        try:
            respuesta = super().destroy(request, *args, **kwargs)
        except (ProtectedError, RestrictedError):
            return Response({'detail': 'El turno está en uso (cajas u horarios); no puede eliminarse.'},
                            status=status.HTTP_400_BAD_REQUEST)
        registrar_bitacora(request, 'DELETE', 'turno', f"Turno '{nombre}' eliminado.", usuario=request.user)
        return respuesta


class HorarioLaboralViewSet(viewsets.ModelViewSet):
    serializer_class = HorarioLaboralSerializer

    def get_permissions(self):
        if self.action == 'mi_horario':
            return [permissions.IsAuthenticated()]
        return [EsAdministrador()]

    def get_queryset(self):
        qs = HorarioLaboral.objects.select_related('id_turno', 'id_contrato_laboral__id_usuario')
        contrato = self.request.query_params.get('contrato')
        if contrato:
            qs = qs.filter(id_contrato_laboral=contrato)
        return qs.order_by('id_contrato_laboral', 'dia_semana', 'id_turno__hora_inicio')

    def perform_create(self, serializer):
        h = serializer.save()
        registrar_bitacora(self.request, 'CREATE', 'horario_laboral',
                           f"Horario {h.dia_semana} / {h.id_turno.nombre_turno} asignado al contrato #{h.id_contrato_laboral_id}.",
                           usuario=self.request.user)

    def perform_update(self, serializer):
        h = serializer.save()
        registrar_bitacora(self.request, 'UPDATE', 'horario_laboral',
                           f"Horario #{h.pk} modificado.", usuario=self.request.user)

    def perform_destroy(self, instance):
        registrar_bitacora(self.request, 'DELETE', 'horario_laboral',
                           f"Horario #{instance.pk} eliminado.", usuario=self.request.user)
        instance.delete()

    @action(detail=False, methods=['get'], url_path='mi-horario')
    def mi_horario(self, request):
        contrato = contrato_activo(request.user)
        if not contrato:
            return Response([])
        qs = HorarioLaboral.objects.filter(id_contrato_laboral=contrato).select_related('id_turno', 'id_contrato_laboral__id_usuario')
        return Response(HorarioLaboralSerializer(qs, many=True).data)


# ------------------------------------------------------------------------------
# CU23: REGISTRAR MARCACIÓN DE ASISTENCIA DE PERSONAL
# ------------------------------------------------------------------------------
class EsPersonal(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.es_administrador or u.es_recepcionista or u.es_entrenador))


class MarcacionPersonalViewSet(viewsets.ModelViewSet):
    serializer_class = MarcacionPersonalSerializer
    http_method_names = ['get', 'post', 'delete']

    def get_permissions(self):
        if self.action in ('marcar', 'mis_marcaciones'):
            return [EsPersonal()]
        return [EsAdministrador()]

    def get_queryset(self):
        qs = MarcacionPersonal.objects.select_related('id_contrato_laboral__id_usuario').order_by('-fecha_hora')
        p = self.request.query_params
        if p.get('contrato'):
            qs = qs.filter(id_contrato_laboral=p['contrato'])
        if p.get('desde'):
            qs = qs.filter(fecha_hora__date__gte=p['desde'])
        if p.get('hasta'):
            qs = qs.filter(fecha_hora__date__lte=p['hasta'])
        return qs[:1000]

    def _siguiente_evento(self, contrato):
        hoy = timezone.localdate()
        ultimo = (MarcacionPersonal.objects.filter(id_contrato_laboral=contrato, fecha_hora__date=hoy)
                  .order_by('-fecha_hora').first())
        return 'SALIDA' if ultimo and ultimo.tipo_evento == 'ENTRADA' else 'ENTRADA', ultimo

    def _registrar(self, request, contrato, metodo):
        evento, ultimo = self._siguiente_evento(contrato)
        if ultimo and (timezone.now() - ultimo.fecha_hora) < timedelta(minutes=1):
            return Response({'detail': 'Marcación duplicada: espere al menos 1 minuto entre marcaciones.'},
                            status=status.HTTP_400_BAD_REQUEST)
        m = MarcacionPersonal.objects.create(id_contrato_laboral=contrato, tipo_evento=evento, metodo=metodo)
        datos = MarcacionPersonalSerializer(m).data
        registrar_bitacora(request, 'CREATE', 'marcacion_personal',
                           f"Marcación de {evento} de '{contrato.id_usuario.username}' ({datos['estado']}).",
                           usuario=request.user)
        return Response(datos, status=status.HTTP_201_CREATED)

    def create(self, request, *args, **kwargs):
        """El administrador registra una marcación manual para un contrato."""
        try:
            contrato = ContratoLaboral.objects.get(pk=request.data.get('id_contrato_laboral'), estado='Activo')
        except (ContratoLaboral.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Contrato laboral activo no encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
        return self._registrar(request, contrato, request.data.get('metodo') or 'Manual (Administrador)')

    @action(detail=False, methods=['post'])
    def marcar(self, request):
        """El empleado autenticado marca su propia entrada/salida."""
        contrato = contrato_activo(request.user)
        if not contrato:
            return Response({'detail': 'No tiene un contrato laboral activo. Consulte con administración.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return self._registrar(request, contrato, 'Sistema Web')

    @action(detail=False, methods=['get'], url_path='mis-marcaciones')
    def mis_marcaciones(self, request):
        qs = (MarcacionPersonal.objects.filter(id_contrato_laboral__id_usuario=request.user)
              .select_related('id_contrato_laboral__id_usuario').order_by('-fecha_hora')[:60])
        contrato = contrato_activo(request.user)
        siguiente = self._siguiente_evento(contrato)[0] if contrato else None
        return Response({'siguiente_evento': siguiente, 'tiene_contrato': bool(contrato),
                         'marcaciones': MarcacionPersonalSerializer(qs, many=True).data})

    def perform_destroy(self, instance):
        registrar_bitacora(self.request, 'DELETE', 'marcacion_personal',
                           f"Marcación #{instance.pk} anulada.", usuario=self.request.user)
        instance.delete()


# ------------------------------------------------------------------------------
# CU24: LIQUIDAR PLANILLA DE PAGOS
# ------------------------------------------------------------------------------
def calcular_liquidacion(contrato, mes, anio):
    """Calcula salario, descuentos por faltas/atrasos para un periodo."""
    _, dias_mes = calendar.monthrange(anio, mes)
    inicio_periodo = date(anio, mes, 1)
    fin_periodo = date(anio, mes, dias_mes)
    hoy = timezone.localdate()
    fin_eval = min(fin_periodo, hoy)
    desde = max(inicio_periodo, contrato.fecha_inicio)
    hasta = min(fin_eval, contrato.fecha_finalizacion) if contrato.fecha_finalizacion else fin_eval

    dias_horario = set(HorarioLaboral.objects.filter(id_contrato_laboral=contrato).values_list('dia_semana', flat=True))
    marcaciones = list(MarcacionPersonal.objects.filter(
        id_contrato_laboral=contrato, tipo_evento='ENTRADA',
        fecha_hora__date__gte=inicio_periodo, fecha_hora__date__lte=fin_periodo))
    dias_con_entrada = {timezone.localtime(m.fecha_hora).date() for m in marcaciones}

    dias_programados = faltas = 0
    d = desde
    while d <= hasta:
        if DIAS_POR_INDICE[d.weekday()] in dias_horario:
            dias_programados += 1
            if d not in dias_con_entrada:
                faltas += 1
        d += timedelta(days=1)

    minutos_atraso = sum(_evaluar_marcacion(m)[1] for m in marcaciones)
    salario = Decimal(contrato.salario_mensual)
    # Proporcional si el contrato inició o terminó dentro del mes.
    dias_trabajables = (min(fin_periodo, contrato.fecha_finalizacion or fin_periodo) - max(inicio_periodo, contrato.fecha_inicio)).days + 1
    salario_base = (salario * Decimal(max(0, dias_trabajables)) / Decimal(dias_mes)).quantize(DOS, ROUND_HALF_UP)
    valor_dia = salario / Decimal(30)
    valor_minuto = valor_dia / Decimal(8 * 60)
    desc_faltas = (valor_dia * faltas).quantize(DOS, ROUND_HALF_UP)
    desc_atrasos = (valor_minuto * minutos_atraso).quantize(DOS, ROUND_HALF_UP)
    return {
        'salario_base': salario_base,
        'dias_programados': dias_programados,
        'faltas': faltas,
        'minutos_atraso': minutos_atraso,
        'descuento_faltas': desc_faltas,
        'descuento_atrasos': desc_atrasos,
    }


class PagoPlanillaViewSet(viewsets.ModelViewSet):
    serializer_class = PagoPlanillaSerializer
    permission_classes = [EsAdministrador]
    http_method_names = ['get', 'post', 'delete']

    def get_permissions(self):
        if self.action == 'mis_pagos':
            return [EsPersonal()]
        return [EsAdministrador()]

    def get_queryset(self):
        qs = PagoPlanilla.objects.select_related('id_contrato_laboral__id_usuario').order_by('-periodo_anio', '-periodo_mes')
        p = self.request.query_params
        if p.get('mes'):
            qs = qs.filter(periodo_mes=p['mes'])
        if p.get('anio'):
            qs = qs.filter(periodo_anio=p['anio'])
        return qs

    def create(self, request, *args, **kwargs):
        return Response({'detail': 'Use /planilla/previsualizar/ y /planilla/liquidar/.'},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def _periodo(self, request):
        try:
            mes = int(request.data.get('mes') or request.query_params.get('mes'))
            anio = int(request.data.get('anio') or request.query_params.get('anio'))
            if not 1 <= mes <= 12 or anio < 2000:
                raise ValueError
            return mes, anio
        except (TypeError, ValueError):
            return None

    def _contratos_del_periodo(self, mes, anio):
        _, dias = calendar.monthrange(anio, mes)
        ini, fin = date(anio, mes, 1), date(anio, mes, dias)
        return (ContratoLaboral.objects.select_related('id_usuario')
                .filter(fecha_inicio__lte=fin)
                .filter(Q(fecha_finalizacion__isnull=True) | Q(fecha_finalizacion__gte=ini))
                .exclude(estado='Anulado'))

    @action(detail=False, methods=['get'])
    def previsualizar(self, request):
        periodo = self._periodo(request)
        if not periodo:
            return Response({'detail': 'Indique mes (1-12) y año válidos.'}, status=status.HTTP_400_BAD_REQUEST)
        mes, anio = periodo
        filas = []
        for c in self._contratos_del_periodo(mes, anio):
            calc = calcular_liquidacion(c, mes, anio)
            descuentos = calc['descuento_faltas'] + calc['descuento_atrasos']
            ya = PagoPlanilla.objects.filter(id_contrato_laboral=c, periodo_mes=mes, periodo_anio=anio).exists()
            filas.append({
                'id_contrato_laboral': c.pk, 'empleado_nombre': _nombre(c.id_usuario), 'cargo': c.cargo,
                **{k: str(v) if isinstance(v, Decimal) else v for k, v in calc.items()},
                'descuentos': str(descuentos),
                'total_estimado': str(max(Decimal('0'), calc['salario_base'] - descuentos)),
                'ya_liquidado': ya,
            })
        return Response({'mes': mes, 'anio': anio, 'empleados': filas})

    @action(detail=False, methods=['post'])
    def liquidar(self, request):
        """Body: {mes, anio, bonos: {id_contrato: monto}} -> genera los pagos del periodo."""
        periodo = self._periodo(request)
        if not periodo:
            return Response({'detail': 'Indique mes (1-12) y año válidos.'}, status=status.HTTP_400_BAD_REQUEST)
        mes, anio = periodo
        if date(anio, mes, 1) > timezone.localdate():
            return Response({'detail': 'No se puede liquidar un periodo futuro.'}, status=status.HTTP_400_BAD_REQUEST)
        bonos = request.data.get('bonos') or {}
        creados, omitidos = [], []
        with transaction.atomic():
            for c in self._contratos_del_periodo(mes, anio):
                if PagoPlanilla.objects.filter(id_contrato_laboral=c, periodo_mes=mes, periodo_anio=anio).exists():
                    omitidos.append(_nombre(c.id_usuario))
                    continue
                calc = calcular_liquidacion(c, mes, anio)
                try:
                    bono = Decimal(str(bonos.get(str(c.pk), 0) or 0)).quantize(DOS)
                except Exception:
                    bono = Decimal('0')
                if bono < 0:
                    bono = Decimal('0')
                descuentos = calc['descuento_faltas'] + calc['descuento_atrasos']
                total = max(Decimal('0'), calc['salario_base'] + bono - descuentos)
                creados.append(PagoPlanilla.objects.create(
                    id_contrato_laboral=c, periodo_mes=mes, periodo_anio=anio,
                    salario_base=calc['salario_base'], bonos=bono, descuentos=descuentos,
                    total_pagado=total, fecha_pagada=timezone.localdate()))
        if not creados and not omitidos:
            return Response({'detail': 'No hay contratos laborales vigentes en el periodo.'}, status=status.HTTP_400_BAD_REQUEST)
        registrar_bitacora(request, 'CREATE', 'pago_planilla',
                           f"Planilla {mes:02d}/{anio} liquidada: {len(creados)} pago(s), "
                           f"total Bs {sum(p.total_pagado for p in creados)}.", usuario=request.user)
        return Response({'creados': PagoPlanillaSerializer(creados, many=True).data, 'omitidos': omitidos},
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='mis-pagos')
    def mis_pagos(self, request):
        qs = PagoPlanilla.objects.filter(id_contrato_laboral__id_usuario=request.user).order_by('-periodo_anio', '-periodo_mes')
        return Response(PagoPlanillaSerializer(qs, many=True).data)

    def perform_destroy(self, instance):
        registrar_bitacora(self.request, 'DELETE', 'pago_planilla',
                           f"Pago de planilla #{instance.pk} ({instance.periodo_mes}/{instance.periodo_anio}) anulado.",
                           usuario=self.request.user)
        instance.delete()
