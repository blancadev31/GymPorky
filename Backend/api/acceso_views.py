# api/acceso_views.py
# ==============================================================================
# CU07: VALIDAR ACCESO DE SOCIO
#
# Flujo principal: Recepción (o el propio socio desde su cuenta) ingresa el CI,
# usuario o código del socio -> el sistema verifica cuenta activa y membresía
# vigente -> registra la marcación (PERMITIDO / DENEGADO) -> responde < 500 ms.
# Flujos alternativos: socio con membresía por vencer (<= 3 días) -> permitido
# con aviso. Excepciones: socio inexistente, cuenta inactiva, membresía vencida
# o inexistente, doble ingreso en menos de 2 minutos.
# ==============================================================================
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from .membresias import resumen_membresia
from .models import MarcacionAcceso, Socio, Usuario
from .views import registrar_bitacora, EsAdministradorORecepcionista


class MarcacionAccesoSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.SerializerMethodField()
    socio_ci = serializers.CharField(source='id_socio.id_socio.ci', read_only=True)
    socio_username = serializers.CharField(source='id_socio.id_socio.username', read_only=True)

    class Meta:
        model = MarcacionAcceso
        fields = ['id_marcacion_acceso', 'id_socio', 'socio_nombre', 'socio_ci', 'socio_username',
                  'fecha_hora', 'tipo_acceso', 'observacion']

    def get_socio_nombre(self, obj):
        u = obj.id_socio.id_socio
        nombre = f'{u.first_name} {u.last_name}'.strip()
        return nombre or u.username


def _buscar_socio(termino):
    termino = (termino or '').strip()
    if not termino:
        return None
    filtro = Q(ci=termino) | Q(username__iexact=termino) | Q(email__iexact=termino)
    if termino.isdigit():
        filtro |= Q(id=int(termino))
    usuario = Usuario.objects.filter(filtro, es_socio=True).first()
    if usuario is None:
        return None
    return Socio.objects.filter(id_socio=usuario).select_related('id_socio').first()


def _validar_y_registrar(request, socio):
    """Aplica las reglas de CU07 y deja la marcación registrada."""
    usuario = socio.id_socio
    membresia = resumen_membresia(socio)
    ahora = timezone.now()

    permitido = True
    motivo = 'Membresía vigente'
    aviso = None

    if usuario.estado_cuenta != 'Activo' or not usuario.is_active:
        permitido, motivo = False, 'Cuenta de usuario inactiva o bloqueada'
    elif not membresia['tiene_membresia']:
        permitido = False
        motivo = 'Membresía vencida' if membresia['estado'] == 'Vencida' else 'El socio no tiene membresía'
    else:
        ultimo = (MarcacionAcceso.objects
                  .filter(id_socio=socio, tipo_acceso='PERMITIDO', fecha_hora__gte=ahora - timedelta(minutes=2))
                  .exists())
        if ultimo:
            permitido, motivo = False, 'Ingreso duplicado: ya se registró un acceso hace menos de 2 minutos'
        elif membresia['dias_restantes'] is not None and membresia['dias_restantes'] <= 3:
            aviso = f"La membresía vence en {membresia['dias_restantes']} día(s). Sugiera renovar."

    marcacion = MarcacionAcceso.objects.create(
        id_socio=socio,
        tipo_acceso='PERMITIDO' if permitido else 'DENEGADO',
        observacion=motivo + (f' | {aviso}' if aviso else ''),
    )
    registrar_bitacora(
        request, 'ACCESO', 'marcacion_acceso',
        f"Acceso {'PERMITIDO' if permitido else 'DENEGADO'} al socio '{usuario.username}' ({motivo}).",
        usuario=request.user if request.user.is_authenticated else None,
    )
    return {
        'permitido': permitido,
        'motivo': motivo,
        'aviso': aviso,
        'membresia': membresia,
        'socio': {
            'id': usuario.id,
            'username': usuario.username,
            'nombre': f'{usuario.first_name} {usuario.last_name}'.strip() or usuario.username,
            'ci': usuario.ci,
            'foto_perfil': socio.foto_perfil,
        },
        'marcacion': MarcacionAccesoSerializer(marcacion).data,
    }


class AccesoViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    GET  /api/acceso/                -> historial (Admin/Recepción), filtros: desde, hasta, tipo, q
    POST /api/acceso/validar/        -> valida por {termino} (CI, usuario, correo o ID)
    POST /api/acceso/mi-ingreso/     -> el socio autenticado marca su propio ingreso
    GET  /api/acceso/mis-accesos/    -> historial propio del socio
    GET  /api/acceso/resumen-hoy/    -> métricas del día (Admin/Recepción)
    """
    serializer_class = MarcacionAccesoSerializer

    def get_permissions(self):
        if self.action in ('mi_ingreso', 'mis_accesos'):
            return [permissions.IsAuthenticated()]
        return [EsAdministradorORecepcionista()]

    def get_queryset(self):
        qs = MarcacionAcceso.objects.select_related('id_socio__id_socio').order_by('-fecha_hora')
        p = self.request.query_params
        if p.get('desde'):
            qs = qs.filter(fecha_hora__date__gte=p['desde'])
        if p.get('hasta'):
            qs = qs.filter(fecha_hora__date__lte=p['hasta'])
        if p.get('tipo'):
            qs = qs.filter(tipo_acceso=p['tipo'].upper())
        if p.get('q'):
            q = p['q']
            qs = qs.filter(Q(id_socio__id_socio__username__icontains=q) | Q(id_socio__id_socio__ci__icontains=q)
                           | Q(id_socio__id_socio__first_name__icontains=q) | Q(id_socio__id_socio__last_name__icontains=q))
        return qs[:500]

    @action(detail=False, methods=['post'])
    def validar(self, request):
        socio = _buscar_socio(request.data.get('termino'))
        if socio is None:
            registrar_bitacora(request, 'ACCESO', 'marcacion_acceso',
                               f"Intento de acceso con identificador inexistente: '{request.data.get('termino')}'.",
                               usuario=request.user)
            return Response({'permitido': False, 'motivo': 'Socio no encontrado. Verifique el CI o usuario.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_validar_y_registrar(request, socio))

    @action(detail=False, methods=['post'], url_path='mi-ingreso')
    def mi_ingreso(self, request):
        socio = Socio.objects.filter(id_socio=request.user).first()
        if socio is None:
            return Response({'permitido': False, 'motivo': 'Su cuenta no tiene perfil de socio.'},
                            status=status.HTTP_403_FORBIDDEN)
        return Response(_validar_y_registrar(request, socio))

    @action(detail=False, methods=['get'], url_path='mis-accesos')
    def mis_accesos(self, request):
        qs = MarcacionAcceso.objects.filter(id_socio__id_socio=request.user).order_by('-fecha_hora')[:100]
        return Response(MarcacionAccesoSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='resumen-hoy')
    def resumen_hoy(self, request):
        hoy = timezone.localdate()
        qs = MarcacionAcceso.objects.filter(fecha_hora__date=hoy)
        return Response({
            'fecha': hoy.isoformat(),
            'permitidos': qs.filter(tipo_acceso='PERMITIDO').count(),
            'denegados': qs.filter(tipo_acceso='DENEGADO').count(),
            'socios_unicos': qs.filter(tipo_acceso='PERMITIDO').values('id_socio').distinct().count(),
        })
