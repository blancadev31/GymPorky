# PORKY GYM — Sistema de Información

Sistema web para la gestión de socios, membresías, control de acceso, punto de venta, inventario,
entrenamiento, recursos humanos y reportes del gimnasio **Porky Gym**.
UAGRM — Sistemas de Información I — Grupo N° 1 — Semestre 2-2026.

- **Backend:** Python 3.12 · Django 5.2 · Django REST Framework · JWT (simplejwt) · PostgreSQL
- **Frontend:** React 19 · TypeScript · Vite · Tailwind CSS · Axios
- **Despliegue:** Vercel (frontend) · servidor Django con Gunicorn + WhiteNoise (backend)

## Casos de uso implementados (24/24 + reportes)

| Paquete | Casos de uso | Pantalla / API |
|---|---|---|
| 1. Seguridad y auditoría | CU01 Registrar cuenta de usuario · CU02 Autenticar usuario · CU03 Bitácora | SEGURIDAD · `/api/usuarios/`, `/api/auth/`, `/api/bitacora/` |
| 2. Socios, membresías y acceso | CU04 Expediente de socio · CU05 Planes · CU06 Contrato de membresía · **CU07 Validar acceso** | SEGURIDAD, MEMBRESÍAS, **ACCESO** · `/api/acceso/` |
| 3. POS y caja | CU08 Venta POS · CU09 Métodos de pago · CU10 Arqueo y cierre de caja | VENTAS · `/api/ventas/`, `/api/caja/` |
| 4. Inventario | CU11 Categorías · CU12 Productos · CU13 Proveedores · CU14 Compras · CU15 Kardex · CU16 Alertas | INVENTARIO |
| 5. Entrenamiento | CU17 Ejercicios · CU18 Rutinas · CU19 Asignar rutina · CU20 Perfil de entrenador | ENTRENAMIENTO |
| 6. Recursos humanos | **CU21 Contratos laborales · CU22 Turnos y horarios · CU23 Marcación de asistencia · CU24 Planilla** | **PERSONAL** · `/api/contratos-laborales/`, `/api/turnos-gestion/`, `/api/horarios-laborales/`, `/api/marcaciones-personal/`, `/api/planilla/` |

## Funcionalidades adicionales (valor agregado)

No son casos de uso nuevos: se documentan como extensiones de los existentes (sección 6.4 del documento).

**Reportes y dashboard:** no se consideran un caso de uso, sino una funcionalidad adicional transversal: reportes estáticos, dinámicos y estadísticos exportables a PDF, Excel y CSV (pantalla **REPORTES** · `/api/reportes/`) y dashboard con estadísticas en tiempo real.

| Funcionalidad | Qué hace | Dónde |
|---|---|---|
| Kardex automático | Cada venta POS registra una SALIDA y cada compra un INGRESO en el kardex | `automatizacion.py` |
| Notificaciones de stock | Al quedar en el mínimo o agotarse: alerta de reposición + campana 🔔 + correo a administradores; se cierra sola al reponer | `automatizacion.py`, `NotificacionesCampana.tsx` |
| Recordatorios de vencimiento | A 3, 2, 1 y 0 días: aviso al socio (campana, correo y cartel en su inicio) y a recepción | `automatizacion.py`, comando `enviar_recordatorios` |
| Dashboard | Indicadores y gráficos con datos reales, se actualiza cada 2 min | `/api/dashboard/`, `DashboardScreen.tsx` |
| Panel del socio | Membresía, días restantes, visitas del mes, racha y rutina asignada | `/api/mi-panel/`, `InicioScreen.tsx` |
| PorkyBot | Chatbot con respuestas reales según el perfil (sin servicios externos) | `/api/chatbot/`, `chatbot.py`, `AsistenteVirtual.tsx` |
| Comandos de voz | "abrir ventas", "validar acceso 8765432", "marcar mi ingreso", "marcar asistencia", "cerrar sesión"… (Chrome/Edge) | `AsistenteVirtual.tsx` |

Para que los recordatorios salgan aunque nadie abra el sistema, programar una vez al día en el servidor:
`0 8 * * *  cd /ruta/Backend && venv/bin/python manage.py enviar_recordatorios`

Los correos usan la cuenta de Brevo ya configurada (`BREVO_API_KEY` en `.env`).

## Visualización por perfil

| Perfil | Ve en el menú |
|---|---|
| Administrador | Todo el sistema, incluidos RR. HH. completos y todos los reportes |
| Recepcionista | Socios, membresías, control de acceso, ventas y caja, *Mi asistencia*, reportes de socios/caja/ventas/accesos |
| Entrenador | Entrenamiento, *Mi asistencia*, reportes de rutinas asignadas |
| Socio | Marcar mi ingreso, mis accesos, mi rutina asignada |

La pantalla de inicio también cambia según el perfil (accesos directos e indicadores). Los permisos se
validan en el backend: aunque alguien llame a la API directamente, recibe `403` si su rol no corresponde.

## Cómo ejecutar

```bash
# Backend
cd Backend
python -m venv venv && venv\Scripts\activate      # (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate            # crea la tabla de notificaciones (0009)
python manage.py createsuperuser
python manage.py poblar_ciclo4      # datos de ejemplo de RR. HH. y accesos (opcional)
python manage.py runserver

# Pruebas automatizadas
python manage.py test api

# Frontend
cd Fronted
npm install
npm run dev
```

Los reportes PDF/Excel/CSV se generan con la librería estándar de Python: **no requieren instalar
paquetes nuevos**.
