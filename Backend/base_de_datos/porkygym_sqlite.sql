-- =====================================================================
-- PORKY GYM - MODELO RELACIONAL (35 TABLAS DEL DOMINIO)
-- MOTOR: SQLite 3  (archivo Backend/db.sqlite3, USE_SQLITE=True)
-- Fuente: Backend/api/models.py y migraciones 0001 a 0009.
-- Las tablas internas de Django (auth_*, django_*, axes_*,
-- usuario_groups, usuario_user_permissions) las crea "migrate" y no
-- forman parte del modelo del dominio.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- FASE 1: TABLAS CATÁLOGO / INDEPENDIENTES
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    password          VARCHAR(128) NOT NULL,
    last_login        DATETIME NULL,
    is_superuser      BOOLEAN NOT NULL DEFAULT 0,
    username          VARCHAR(150) NOT NULL UNIQUE,
    first_name        VARCHAR(150) NOT NULL DEFAULT '',
    last_name         VARCHAR(150) NOT NULL DEFAULT '',
    email             VARCHAR(254) NOT NULL DEFAULT '',
    is_staff          BOOLEAN NOT NULL DEFAULT 0,
    is_active         BOOLEAN NOT NULL DEFAULT 1,
    date_joined       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ci                VARCHAR(20) NULL UNIQUE,
    telefono          VARCHAR(20) NULL,
    estado_cuenta     VARCHAR(20) NOT NULL DEFAULT 'Activo',
    es_socio          BOOLEAN NOT NULL DEFAULT 0,
    es_entrenador     BOOLEAN NOT NULL DEFAULT 0,
    es_recepcionista  BOOLEAN NOT NULL DEFAULT 0,
    es_administrador  BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE metodo_pago (
    id_metodo_pago  INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion     VARCHAR(100) NOT NULL UNIQUE,
    activo          BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE proveedor (
    id_proveedor        INTEGER PRIMARY KEY AUTOINCREMENT,
    razon_social        VARCHAR(150) NOT NULL,
    nit                 VARCHAR(50) NOT NULL UNIQUE,
    moneda_facturacion  VARCHAR(10) NOT NULL DEFAULT 'BOB',
    telefono            VARCHAR(20) NULL,
    email               VARCHAR(100) NULL,
    direccion           TEXT NULL
);

CREATE TABLE categoria_producto (
    id_categoria      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_categoria  VARCHAR(100) NOT NULL,
    id_subcategoria   INTEGER NULL REFERENCES categoria_producto(id_categoria) ON DELETE SET NULL
);

CREATE TABLE plan_membresia (
    id_plan_membresia  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_plan        VARCHAR(100) NOT NULL,
    moneda_origen      VARCHAR(10) NOT NULL DEFAULT 'BOB',
    costo_base_origen  DECIMAL(12,2) NOT NULL CHECK (costo_base_origen >= 0),
    duracion_dias      INTEGER NOT NULL CHECK (duracion_dias >= 1),
    acceso_piscina     BOOLEAN NOT NULL DEFAULT 0,
    clases_grupales    BOOLEAN NOT NULL DEFAULT 0,
    estado             VARCHAR(20) NOT NULL DEFAULT 'Activo'
);

CREATE TABLE rutina (
    id_rutina               INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_rutina           VARCHAR(100) NOT NULL,
    nivel                   VARCHAR(50) NOT NULL DEFAULT 'Principiante'
                            CHECK (nivel IN ('Principiante','Intermedio','Avanzado')),
    descripcion             TEXT NULL,
    calorias_estimadas      INTEGER NULL CHECK (calorias_estimadas >= 1),
    duracion_estimada_mins  INTEGER NULL CHECK (duracion_estimada_mins >= 1),
    estado                  VARCHAR(20) NOT NULL DEFAULT 'Activo'
);

CREATE TABLE ejercicio (
    id_ejercicio         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_ejercicio     VARCHAR(100) NOT NULL,
    equipo_requerido     VARCHAR(100) NULL,
    grupo_muscular       VARCHAR(100) NULL CHECK (grupo_muscular IN
                         ('Pecho','Espalda','Hombros','Brazos','Piernas','Gluteos','Abdomen','Cuerpo completo')),
    zona_ubicacion       VARCHAR(100) NULL,
    url_video_tecnica    VARCHAR(255) NULL,
    descripcion_tecnica  TEXT NULL,
    estado               VARCHAR(20) NOT NULL DEFAULT 'Activo'
);

CREATE TABLE turno (
    id_turno      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_turno  VARCHAR(50) NOT NULL,
    hora_inicio   TIME NOT NULL,
    hora_fin      TIME NOT NULL
);

-- ---------------------------------------------------------------------
-- FASE 2: TABLAS DE HERENCIA Y CATÁLOGOS DEPENDIENTES
-- ---------------------------------------------------------------------
CREATE TABLE administrador (
    id_administrador INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE
);

CREATE TABLE recepcionista (
    id_recepcionista INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE
);

CREATE TABLE entrenador (
    id_entrenador          INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
    certificado            VARCHAR(100) NULL,
    especialidad           VARCHAR(100) NULL,
    biografia_profesional  TEXT NULL,
    anios_experiencia      INTEGER NULL CHECK (anios_experiencia >= 0),
    red_social_link        VARCHAR(255) NULL,
    estado                 VARCHAR(20) NOT NULL DEFAULT 'Activo'
);

CREATE TABLE horario_entrenador (
    id_horario_entrenador  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_entrenador          INTEGER NOT NULL REFERENCES entrenador(id_entrenador) ON DELETE CASCADE,
    id_turno               INTEGER NOT NULL REFERENCES turno(id_turno) ON DELETE RESTRICT,
    dia_semana             VARCHAR(15) NOT NULL CHECK (dia_semana IN
                           ('Lunes','Martes','Miercoles','Jueves','Viernes','Sabado','Domingo')),
    UNIQUE (id_entrenador, id_turno, dia_semana)
);

CREATE TABLE socio (
    id_socio               INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
    foto_perfil            VARCHAR(255) NULL,
    fecha_registro         DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_nacimiento       DATE NOT NULL,
    peso_inicial_kg        DECIMAL(5,2) NULL CHECK (peso_inicial_kg >= 0.01),
    contacto_emerg_nombre  VARCHAR(150) NULL
);

CREATE TABLE bitacora (
    id_bitacora        INTEGER PRIMARY KEY AUTOINCREMENT,
    direccion_ip       VARCHAR(45) NULL,
    nombre_usuario_db  VARCHAR(100) NULL,
    accion             VARCHAR(50) NOT NULL,
    tabla_afectada     VARCHAR(50) NOT NULL,
    descripcion        TEXT NULL,
    fecha_hora         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_usuario         INTEGER NULL REFERENCES usuario(id) ON DELETE SET NULL
);

CREATE TABLE contrato_laboral (
    id_contrato_laboral  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario           INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    cargo                VARCHAR(100) NOT NULL,
    salario_mensual      DECIMAL(12,2) NOT NULL CHECK (salario_mensual >= 0),
    fecha_inicio         DATE NOT NULL,
    fecha_finalizacion   DATE NULL,
    estado               VARCHAR(20) NOT NULL DEFAULT 'Activo'
);

CREATE TABLE producto (
    id_producto           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_categoria          INTEGER NOT NULL REFERENCES categoria_producto(id_categoria) ON DELETE RESTRICT,
    nombre_producto       VARCHAR(150) NOT NULL,
    moneda_origen         VARCHAR(10) NOT NULL DEFAULT 'BOB',
    precio_base_original  DECIMAL(12,2) NOT NULL CHECK (precio_base_original >= 0),
    precio_venta_local    DECIMAL(12,2) NOT NULL CHECK (precio_venta_local >= 0),
    costo_promedio_local  DECIMAL(12,2) NOT NULL DEFAULT 0 CHECK (costo_promedio_local >= 0),
    stock_actual          INTEGER NOT NULL DEFAULT 0,
    stock_minimo          INTEGER NOT NULL DEFAULT 0,
    stock_maximo          INTEGER NULL,
    clasificacion_abc     VARCHAR(2) NULL,
    estado                VARCHAR(20) NOT NULL DEFAULT 'Activo'
);

-- ---------------------------------------------------------------------
-- FASE 3: TRANSACCIONES OPERATIVAS
-- ---------------------------------------------------------------------
CREATE TABLE arqueo_caja (
    id_caja           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_administrador  INTEGER NULL REFERENCES administrador(id_administrador) ON DELETE RESTRICT,
    responsable_id    INTEGER NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    turno_id          INTEGER NULL REFERENCES turno(id_turno) ON DELETE RESTRICT,
    fecha_apertura    DATETIME NOT NULL,
    fecha_cierre      DATETIME NULL,
    monto_inicial     DECIMAL(12,2) NOT NULL CHECK (monto_inicial >= 0),
    monto_final       DECIMAL(12,2) NULL CHECK (monto_final >= 0),
    efectivo_contado  DECIMAL(12,2) NULL CHECK (efectivo_contado >= 0),
    diferencia        DECIMAL(12,2) NULL,
    estado            VARCHAR(10) NOT NULL DEFAULT 'CERRADA' CHECK (estado IN ('ABIERTA','CERRADA'))
);
-- Restricción "una_sola_caja_abierta_global" (UniqueConstraint condicional del modelo)
CREATE UNIQUE INDEX una_sola_caja_abierta_global ON arqueo_caja(estado) WHERE estado = 'ABIERTA';

CREATE TABLE egreso_caja (
    id_egreso    INTEGER PRIMARY KEY AUTOINCREMENT,
    caja_id      INTEGER NOT NULL REFERENCES arqueo_caja(id_caja) ON DELETE RESTRICT,
    usuario_id   INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    fecha_hora   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    concepto     VARCHAR(180) NOT NULL,
    monto        DECIMAL(12,2) NOT NULL CHECK (monto >= 0.01),
    observacion  TEXT NULL
);

CREATE TABLE compra (
    id_compra              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_administrador       INTEGER NOT NULL REFERENCES administrador(id_administrador) ON DELETE RESTRICT,
    id_proveedor           INTEGER NOT NULL REFERENCES proveedor(id_proveedor) ON DELETE RESTRICT,
    fecha_hora             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    nro_factura_proveedor  VARCHAR(50) NULL,
    tasa_cambio_aplicada   DECIMAL(10,4) NOT NULL DEFAULT 1.0000,
    monto_total_origen     DECIMAL(12,2) NOT NULL CHECK (monto_total_origen >= 0),
    monto_total_local      DECIMAL(12,2) NOT NULL CHECK (monto_total_local >= 0),
    estado_compra          VARCHAR(20) NOT NULL DEFAULT 'Completada'
);

CREATE TABLE horario_laboral (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_turno             INTEGER NOT NULL REFERENCES turno(id_turno) ON DELETE CASCADE,
    id_contrato_laboral  INTEGER NOT NULL REFERENCES contrato_laboral(id_contrato_laboral) ON DELETE CASCADE,
    dia_semana           VARCHAR(15) NOT NULL,
    tolerancia_minutos   INTEGER NOT NULL DEFAULT 0 CHECK (tolerancia_minutos >= 0),
    UNIQUE (id_turno, id_contrato_laboral, dia_semana)
);

CREATE TABLE pago_planilla (
    id_pago_planilla     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_contrato_laboral  INTEGER NOT NULL REFERENCES contrato_laboral(id_contrato_laboral) ON DELETE RESTRICT,
    periodo_mes          INTEGER NOT NULL CHECK (periodo_mes BETWEEN 1 AND 12),
    periodo_anio         INTEGER NOT NULL,
    salario_base         DECIMAL(12,2) NOT NULL,
    bonos                DECIMAL(12,2) NOT NULL DEFAULT 0,
    descuentos           DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_pagado         DECIMAL(12,2) NOT NULL,
    fecha_pagada         DATE NOT NULL
);

CREATE TABLE marcacion_personal (
    id_marcacion_personal  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_contrato_laboral    INTEGER NOT NULL REFERENCES contrato_laboral(id_contrato_laboral) ON DELETE CASCADE,
    fecha_hora             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo_evento            VARCHAR(20) NOT NULL,      -- 'ENTRADA' / 'SALIDA'
    metodo                 VARCHAR(50) NULL           -- 'Sistema Web', 'Voz', ...
);

CREATE TABLE contrato_membresia (
    id_contrato_mem       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_socio              INTEGER NOT NULL REFERENCES socio(id_socio) ON DELETE RESTRICT,
    id_metodo_pago        INTEGER NOT NULL REFERENCES metodo_pago(id_metodo_pago) ON DELETE RESTRICT,
    id_plan_mem           INTEGER NOT NULL REFERENCES plan_membresia(id_plan_membresia) ON DELETE RESTRICT,
    id_renovacion         INTEGER NULL REFERENCES contrato_membresia(id_contrato_mem) ON DELETE SET NULL,
    tipo_operacion        VARCHAR(50) NOT NULL,       -- 'Alta' / 'Renovacion'
    fecha_inicio          DATE NOT NULL,
    fecha_vencimiento     DATE NOT NULL,
    tasa_cambio_aplicada  DECIMAL(10,4) NOT NULL DEFAULT 1.0000,
    monto_pagado_local    DECIMAL(12,2) NOT NULL CHECK (monto_pagado_local >= 0),
    estado_membresia      VARCHAR(20) NOT NULL DEFAULT 'Activa'
);

CREATE TABLE marcacion_acceso (
    id_marcacion_acceso  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_socio             INTEGER NOT NULL REFERENCES socio(id_socio) ON DELETE CASCADE,
    fecha_hora           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo_acceso          VARCHAR(20) NULL,            -- 'PERMITIDO' / 'DENEGADO'
    observacion          TEXT NULL
);

CREATE TABLE asignacion_rutina (
    id_asignacion_rutina  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_entrenador         INTEGER NOT NULL REFERENCES entrenador(id_entrenador) ON DELETE RESTRICT,
    id_socio              INTEGER NOT NULL REFERENCES socio(id_socio) ON DELETE CASCADE,
    id_rutina             INTEGER NOT NULL REFERENCES rutina(id_rutina) ON DELETE RESTRICT,
    fecha_asignacion      DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_inicio          DATE NULL,
    fecha_fin             DATE NULL,
    observaciones         TEXT NULL,
    estado                VARCHAR(20) NOT NULL DEFAULT 'Activa',
    turno                 VARCHAR(20) NOT NULL DEFAULT 'mañana'
                          CHECK (turno IN ('mañana','mediodia','tarde','noche'))
);

CREATE TABLE detalle_rutina (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    id_rutina         INTEGER NOT NULL REFERENCES rutina(id_rutina) ON DELETE CASCADE,
    id_ejercicio      INTEGER NOT NULL REFERENCES ejercicio(id_ejercicio) ON DELETE CASCADE,
    orden             INTEGER NOT NULL DEFAULT 1 CHECK (orden >= 1),
    series            INTEGER NOT NULL CHECK (series >= 1),
    repeticiones      INTEGER NOT NULL CHECK (repeticiones >= 1),
    descanso_minutos  DECIMAL(5,2) NULL CHECK (descanso_minutos >= 0),
    UNIQUE (id_rutina, id_ejercicio)
);

CREATE TABLE venta (
    id_venta              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario            INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    id_metodo_pago        INTEGER NOT NULL REFERENCES metodo_pago(id_metodo_pago) ON DELETE RESTRICT,
    id_socio              INTEGER NOT NULL REFERENCES socio(id_socio) ON DELETE RESTRICT,
    caja_id               INTEGER NULL REFERENCES arqueo_caja(id_caja) ON DELETE RESTRICT,
    fecha_hora            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    nro_factura           VARCHAR(50) NULL,
    tasa_cambio_aplicada  DECIMAL(10,4) NOT NULL DEFAULT 1.0000,
    monto_total_local     DECIMAL(12,2) NOT NULL CHECK (monto_total_local >= 0),
    estado_venta          VARCHAR(20) NOT NULL DEFAULT 'Completada'
);

-- ---------------------------------------------------------------------
-- FASE 4: DETALLES DE TRANSACCIONES Y LOGÍSTICA
-- ---------------------------------------------------------------------
CREATE TABLE detalle_compra (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_compra              INTEGER NOT NULL REFERENCES compra(id_compra) ON DELETE CASCADE,
    id_producto            INTEGER NOT NULL REFERENCES producto(id_producto) ON DELETE RESTRICT,
    cantidad               INTEGER NOT NULL CHECK (cantidad >= 1),
    costo_unitario_origen  DECIMAL(12,2) NOT NULL CHECK (costo_unitario_origen >= 0),
    costo_unitario_local   DECIMAL(12,2) NOT NULL CHECK (costo_unitario_local >= 0),
    subtotal_origen        DECIMAL(12,2) NOT NULL CHECK (subtotal_origen >= 0),
    subtotal_local         DECIMAL(12,2) NOT NULL CHECK (subtotal_local >= 0),
    UNIQUE (id_compra, id_producto)
);

CREATE TABLE kardex_inventario (
    id_kardex         INTEGER PRIMARY KEY AUTOINCREMENT,
    id_producto       INTEGER NOT NULL REFERENCES producto(id_producto) ON DELETE RESTRICT,
    fecha_movimiento  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo_movimiento   VARCHAR(20) NOT NULL,  -- INGRESO, SALIDA, AJUSTE_POSITIVO, AJUSTE_NEGATIVO, RETIRO
    cantidad          INTEGER NOT NULL,
    motivo            VARCHAR(100) NOT NULL
);

CREATE TABLE alerta_reposicion (
    id_alerta_repo        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_admin              INTEGER NOT NULL REFERENCES administrador(id_administrador) ON DELETE RESTRICT,
    id_producto           INTEGER NOT NULL REFERENCES producto(id_producto) ON DELETE CASCADE,
    codigo_evento_global  VARCHAR(50) NULL,
    nivel_urgencia        VARCHAR(20) NULL,       -- 'Bajo' / 'Agotado'
    cantidad_sugerida     INTEGER NULL CHECK (cantidad_sugerida >= 1),
    estado_alerta         VARCHAR(20) NOT NULL DEFAULT 'Pendiente',  -- 'Pendiente' / 'Cerrada'
    orden_compra_erp      VARCHAR(50) NULL,
    fecha_generacion      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre          DATETIME NULL
);

CREATE TABLE detalle_venta_producto (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venta                INTEGER NOT NULL REFERENCES venta(id_venta) ON DELETE CASCADE,
    id_producto             INTEGER NOT NULL REFERENCES producto(id_producto) ON DELETE RESTRICT,
    cantidad                INTEGER NOT NULL CHECK (cantidad >= 1),
    precio_unitario_origen  DECIMAL(12,2) NOT NULL CHECK (precio_unitario_origen >= 0),
    precio_unitario_local   DECIMAL(12,2) NOT NULL CHECK (precio_unitario_local >= 0),
    subtotal_origen         DECIMAL(12,2) NOT NULL CHECK (subtotal_origen >= 0),
    subtotal_local          DECIMAL(12,2) NOT NULL CHECK (subtotal_local >= 0),
    UNIQUE (id_venta, id_producto)
);

CREATE TABLE detalle_venta_servicio (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venta                INTEGER NOT NULL REFERENCES venta(id_venta) ON DELETE CASCADE,
    id_plan_membresia       INTEGER NOT NULL REFERENCES plan_membresia(id_plan_membresia) ON DELETE RESTRICT,
    cantidad                INTEGER NOT NULL CHECK (cantidad >= 1),
    precio_unitario_origen  DECIMAL(12,2) NOT NULL CHECK (precio_unitario_origen >= 0),
    precio_unitario_local   DECIMAL(12,2) NOT NULL CHECK (precio_unitario_local >= 0),
    subtotal_origen         DECIMAL(12,2) NOT NULL CHECK (subtotal_origen >= 0),
    subtotal_local          DECIMAL(12,2) NOT NULL CHECK (subtotal_local >= 0),
    UNIQUE (id_venta, id_plan_membresia)
);

-- ---------------------------------------------------------------------
-- FASE 5: PAGOS EN LÍNEA, CONFIGURACIÓN Y NOTIFICACIONES
-- ---------------------------------------------------------------------
CREATE TABLE pago_pasarela (
    id_pago              INTEGER PRIMARY KEY AUTOINCREMENT,
    proveedor            VARCHAR(20) NOT NULL DEFAULT 'PAYPAL',
    id_orden_externa     VARCHAR(100) NOT NULL UNIQUE,
    id_captura_externa   VARCHAR(100) NULL UNIQUE,
    tipo_operacion       VARCHAR(20) NOT NULL DEFAULT 'MEMBRESIA',
    id_usuario           INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    id_socio             INTEGER NOT NULL REFERENCES socio(id_socio) ON DELETE RESTRICT,
    id_plan_mem          INTEGER NOT NULL REFERENCES plan_membresia(id_plan_membresia) ON DELETE RESTRICT,
    id_contrato_mem      INTEGER NULL REFERENCES contrato_membresia(id_contrato_mem) ON DELETE RESTRICT,
    monto_local          DECIMAL(12,2) NOT NULL,
    monto_usd            DECIMAL(12,2) NOT NULL,
    tasa_cambio          DECIMAL(10,4) NOT NULL,
    estado               VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
                         CHECK (estado IN ('PENDIENTE','COMPLETADO','CANCELADO','FALLIDO')),
    fecha_creacion       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE configuracion_sistema (
    id_configuracion     INTEGER PRIMARY KEY AUTOINCREMENT,
    clave                VARCHAR(60) NOT NULL UNIQUE,
    valor                DECIMAL(10,4) NOT NULL,
    fecha_actualizacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_por      INTEGER NULL REFERENCES usuario(id) ON DELETE SET NULL
);

CREATE TABLE notificacion (
    id_notificacion  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario       INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    tipo             VARCHAR(30) NOT NULL,     -- STOCK_BAJO, STOCK_AGOTADO, VENCIMIENTO, SISTEMA
    titulo           VARCHAR(150) NOT NULL,
    mensaje          TEXT NOT NULL,
    pantalla         VARCHAR(40) NULL,
    referencia       VARCHAR(120) NOT NULL,
    leida            BOOLEAN NOT NULL DEFAULT 0,
    enviada_correo   BOOLEAN NOT NULL DEFAULT 0,
    fecha_creacion   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_usuario, referencia)
);

-- ==============================================================================
-- POBLACIÓN DE DATOS (INSERT)
-- ==============================================================================
-- FASE 1: TABLAS INDEPENDIENTES Y CATÁLOGOS BASE
INSERT INTO metodo_pago (id_metodo_pago, descripcion, activo) VALUES
(1, 'Efectivo', 1),
(2, 'Tarjeta de Débito / Crédito', 1),
(3, 'Transferencia Bancaria', 1),
(4, 'Pago QR', 1),
(5, 'PayPal', 1);

INSERT INTO proveedor (id_proveedor, razon_social, nit, moneda_facturacion, telefono, email, direccion) VALUES
(1, 'Nutrición Deportiva Global S.A.', '1028492021', 'BOB', '67425500', 'ventas@nutricionglobal.bo', 'Av. Cristóbal de Mendoza #3100, Equipetrol'),
(2, 'Equipamiento Fitness Pro International', '1259402019', 'USD', '73538890', 'corporate@fitnesspro.com', 'Parque Industrial, 4to Anillo'),
(3, 'Indumentaria y Accesorios GymCorp', '1183928012', 'BOB', '65312200', 'logistica@gymcorp.bo', 'Av. San Martín, C.C. Las Brisas');

INSERT INTO categoria_producto (id_categoria, nombre_categoria, id_subcategoria) VALUES
(1, 'Suplementos y Nutrición', NULL),
(2, 'Indumentaria Deportiva', NULL),
(3, 'Bebidas e Hidratación', NULL),
(4, 'Snacks y Alimentos', NULL),
(5, 'Accesorios y Varios', NULL),
(6, 'Pastillas y Vitaminas', 1),
(7, 'Poleras y Tops', 2),
(8, 'Shorts y Ropa Inferior', 2),
(9, 'Aguas Minerales', 3),
(10, 'Energizantes e Isotónicas', 3),
(11, 'Barras y Alfajores', 4),
(12, 'Dulces y Gomas', 4),
(13, 'Bolsos y Mochilas', 5),
(14, 'Higiene Deportiva', 5),
(15, 'Premiaciones', 5),
(16, 'Promociones de Temporada', 5);

INSERT INTO plan_membresia (id_plan_membresia, nombre_plan, moneda_origen, costo_base_origen, duracion_dias, acceso_piscina, clases_grupales, estado) VALUES
(1, 'Plan Mensual Estándar', 'BOB', 250, 30, 0, 1, 'Activo'),
(2, 'Plan Trimestral Pro', 'BOB', 650, 90, 1, 1, 'Activo'),
(3, 'Plan Anual VIP', 'BOB', 2200, 365, 1, 1, 'Activo'),
(4, 'Plan Semestral Fit', 'BOB', 1200, 180, 1, 1, 'Activo'),
(5, 'Pase Diario (Day Pass)', 'BOB', 35, 1, 0, 0, 'Activo');

INSERT INTO rutina (id_rutina, nombre_rutina, nivel, descripcion, calorias_estimadas, duracion_estimada_mins, estado) VALUES
(1, 'Rutina Full Body Inicial', 'Principiante', 'Adaptación general de todo el cuerpo', 320, 45, 'Activo'),
(2, 'Hipertrofia Torso-Pierna', 'Intermedio', 'División torso/pierna 4 días', 480, 90, 'Activo'),
(3, 'Fuerza Máxima / Powerlifting', 'Avanzado', 'Básicos con cargas altas', 420, 90, 'Activo'),
(4, 'Push - Pull - Legs (PPL)', 'Avanzado', 'Empuje, tracción y pierna', 580, 75, 'Activo'),
(5, 'Acondicionamiento Físico y HIIT', 'Principiante', 'Circuitos de alta intensidad', 450, 40, 'Activo'),
(6, 'Recomposición Corporal Pro', 'Intermedio', 'Fuerza + cardio moderado', 500, 90, 'Activo');

INSERT INTO ejercicio (id_ejercicio, nombre_ejercicio, equipo_requerido, grupo_muscular, zona_ubicacion, url_video_tecnica, descripcion_tecnica, estado) VALUES
(1, 'Press de Banca Plano', 'Barra y banco plano', 'Pecho', 'Zona Pesos Libres', 'https://fit.com/v/press-banca', 'Bajar la barra al pecho controlando', 'Activo'),
(2, 'Sentadilla con Barra', 'Rack y barra', 'Piernas', 'Zona Racks', 'https://fit.com/v/sentadilla', 'Cadera por debajo de la rodilla', 'Activo'),
(3, 'Peso Muerto Convencional', 'Barra y discos', 'Espalda', 'Zona Racks', 'https://fit.com/v/peso-muerto', 'Espalda neutra durante todo el recorrido', 'Activo'),
(4, 'Press Militar con Barra', 'Barra', 'Hombros', 'Zona Pesos Libres', 'https://fit.com/v/press-militar', 'Empuje vertical sin arquear la espalda', 'Activo'),
(5, 'Jalón al Pecho con Polea', 'Polea alta', 'Espalda', 'Zona Poleas', 'https://fit.com/v/jalon-pecho', 'Llevar la barra a la parte alta del pecho', 'Activo'),
(6, 'Prensa de Piernas 45°', 'Prensa 45°', 'Piernas', 'Zona Máquinas', 'https://fit.com/v/prensa-45', 'No bloquear las rodillas', 'Activo'),
(7, 'Curl de Bíceps con Barra W', 'Barra W', 'Brazos', 'Zona Pesos Libres', 'https://fit.com/v/curl-barra-w', 'Codos fijos al costado', 'Activo'),
(8, 'Extensión de Tríceps en Polea Alta', 'Polea alta', 'Brazos', 'Zona Poleas', 'https://fit.com/v/extension-triceps', 'Extender completamente el codo', 'Activo'),
(9, 'Elevaciones Laterales con Mancuernas', 'Mancuernas', 'Hombros', 'Zona Pesos Libres', 'https://fit.com/v/elevaciones-laterales', 'Subir hasta la altura del hombro', 'Activo'),
(10, 'Rueda Abdominal', 'Rueda abdominal', 'Abdomen', 'Zona Funcional', 'https://fit.com/v/rueda-abdominal', 'Mantener el abdomen contraído', 'Activo'),
(11, 'Hip Thrust con Barra', 'Barra y banco', 'Gluteos', 'Zona Funcional', 'https://fit.com/v/hip-thrust', 'Extensión completa de cadera', 'Activo');

INSERT INTO turno (id_turno, nombre_turno, hora_inicio, hora_fin) VALUES
(1, 'Mañana', '07:00:00', '12:00:00'),
(2, 'Mediodía', '12:00:00', '14:00:00'),
(3, 'Tarde', '14:00:00', '19:00:00'),
(4, 'Noche', '19:00:00', '22:00:00');

-- Contraseñas almacenadas con el hash PBKDF2-SHA256 de Django (valor abreviado).
INSERT INTO usuario (id, password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, ci, telefono, estado_cuenta, es_socio, es_entrenador, es_recepcionista, es_administrador) VALUES
(1, 'pbkdf2_sha256$1000000$demo$hash01', 0, 'ctaborga', 'Cristhian Alexander', 'Taborga Coca', 'ctaborga@gmail.com', 0, 1, '2026-01-15 10:30:00', '78541234', '75389376', 'Activo', 1, 1, 0, 0),
(2, 'pbkdf2_sha256$1000000$demo$hash02', 0, 'scastro', 'Sofia', 'Castro Rodriguez', 'scastro.r@hotmail.com', 0, 1, '2026-01-20 09:00:00', '13294128', '76029410', 'Activo', 1, 0, 0, 0),
(3, 'pbkdf2_sha256$1000000$demo$hash03', 0, 'mjustiniano', 'María René', 'Justiniano Vaca', 'mjustiniano_v@yahoo.com', 0, 1, '2026-02-10 09:15:00', '54321098', '77011223', 'Activo', 1, 0, 1, 0),
(4, 'pbkdf2_sha256$1000000$demo$hash04', 1, 'lcuellar', 'Luis Fernando', 'Cuéllar Saucedo', 'lfcuellar@gmail.com', 1, 1, '2026-02-18 18:40:00', '7345678', '71233445', 'Activo', 1, 0, 0, 1),
(5, 'pbkdf2_sha256$1000000$demo$hash05', 0, 'rmontero', 'Rodrigo', 'Montero Gutiérrez', 'rmontero.g@gmail.com', 0, 1, '2026-03-01 11:00:00', '12345763', '69177889', 'Activo', 1, 0, 0, 0),
(6, 'pbkdf2_sha256$1000000$demo$hash06', 0, 'csuarez', 'Carlos Eduardo', 'Suárez Rojas', 'csuarez.r@hotmail.com', 0, 1, '2026-03-05 08:00:00', '8765432', '67100112', 'Activo', 1, 1, 0, 0),
(7, 'pbkdf2_sha256$1000000$demo$hash07', 0, 'nrivero', 'Natalia', 'Rivero Parada', 'nriverop@gmail.com', 0, 1, '2026-03-12 08:30:00', '8234567', '69022334', 'Activo', 1, 0, 1, 0),
(8, 'pbkdf2_sha256$1000000$demo$hash08', 0, 'cardaya', 'Carla Fernanda', 'Ardaya Paz', 'cardaya.paz@yahoo.com', 0, 1, '2026-03-20 19:10:00', '6543210', '65055667', 'Activo', 1, 1, 0, 0),
(9, 'pbkdf2_sha256$1000000$demo$hash09', 0, 'jaguilera', 'Juan Pablo', 'Aguilera Castedo', 'jp.aguilera@gmail.com', 0, 1, '2026-04-02 12:00:00', '6456789', '71088990', 'Activo', 1, 0, 0, 0),
(10, 'pbkdf2_sha256$1000000$demo$hash10', 0, 'mvaca', 'Marcelo', 'Vaca Zeballos', 'mvaca.z@gmail.com', 0, 1, '2026-04-10 17:25:00', '91234567', '78944556', 'Activo', 1, 0, 0, 0),
(11, 'pbkdf2_sha256$1000000$demo$hash11', 0, 'rblanco', 'Ruddy Orlando', 'Blanco Aruquipa', 'rblanco.a@gmail.com', 0, 1, '2026-04-12 10:00:00', '83456789', '77123456', 'Activo', 0, 1, 1, 0),
(12, 'pbkdf2_sha256$1000000$demo$hash12', 0, 'portiz', 'Patricia', 'Ortiz Mujica', 'patricia.ortiz@gmail.com', 1, 1, '2026-04-02 12:00:00', '37453282', '66584475', 'Activo', 1, 0, 0, 1),
(13, 'pbkdf2_sha256$1000000$demo$hash13', 0, 'omedina', 'Oscar', 'Medina Rojas', 'oscar.medina@gmail.com', 0, 1, '2026-04-10 17:25:00', '12458745', '78983463', 'Activo', 1, 0, 0, 0),
(14, 'pbkdf2_sha256$1000000$demo$hash14', 0, 'jcastellon', 'Joel Lucas', 'Castellon Mamani', 'lucasrojas@gmail.com', 0, 1, '2026-04-15 10:05:00', '13569856', '76354658', 'Inactivo', 1, 0, 0, 0),
(15, 'pbkdf2_sha256$1000000$demo$hash15', 0, 'mlopez', 'Maria Esther', 'Lopez Morales', 'marialopez6@gmail.com', 0, 1, '2026-04-22 15:45:00', '14556798', '67458793', 'Activo', 1, 0, 0, 0);

-- FASE 2: TABLAS DE HERENCIA Y CATÁLOGOS DEPENDIENTES
INSERT INTO administrador (id_administrador) VALUES (4), (12);
INSERT INTO recepcionista (id_recepcionista) VALUES (3), (7), (11);

INSERT INTO entrenador (id_entrenador, certificado, especialidad, biografia_profesional, anios_experiencia, red_social_link, estado) VALUES
(1, 'CERT-ENT-004.pdf', 'Musculación e Hipertrofia', 'Especialista en ganancia muscular y recomposición corporal', 8, 'instagram.com/trainer_hipertrofia', 'Activo'),
(6, 'CERT-ENT-002.pdf', 'Fuerza y Potencia', 'Enfocado en powerlifting, halterofilia y fuerza máxima', 10, 'instagram.com/trainer_fuerza', 'Activo'),
(8, 'CERT-ENT-006.pdf', 'Cardio y Pérdida de Peso', 'Preparadora física orientada a déficit calórico y HIIT', 5, 'instagram.com/trainer_cardio', 'Activo'),
(11, 'CERT-ENT-003.pdf', 'Entrenamiento Funcional', 'Experto en movilidad articular, calistenia y TRX', 6, 'instagram.com/trainer_funcional', 'Activo');

INSERT INTO horario_entrenador (id_horario_entrenador, id_entrenador, id_turno, dia_semana) VALUES
(1, 1, 1, 'Lunes'), (2, 1, 1, 'Miercoles'), (3, 6, 3, 'Martes'),
(4, 8, 4, 'Jueves'), (5, 11, 1, 'Viernes');

INSERT INTO socio (id_socio, foto_perfil, fecha_registro, fecha_nacimiento, peso_inicial_kg, contacto_emerg_nombre) VALUES
(1, 'socios/cristhian_taborga.jpg', '2026-01-15', '1998-04-12', 78.50, 'Ana Coca (madre)'),
(2, 'socios/sofia_castro.jpg', '2026-01-20', '2001-09-03', 58.20, 'Luis Castro (padre)'),
(3, 'socios/maria_justiniano.jpg', '2026-02-10', '1999-11-21', 62.00, 'Pedro Justiniano (hermano)'),
(4, 'socios/luis_cuellar.jpg', '2026-02-18', '1990-02-08', 85.30, 'Rosa Saucedo (esposa)'),
(5, 'socios/rodrigo_montero.jpg', '2026-03-01', '1995-07-30', 90.10, 'Elena Gutiérrez (madre)'),
(6, 'socios/carlos_suarez.jpg', '2026-03-05', '1993-05-17', 80.00, 'Marta Rojas (madre)'),
(7, 'socios/natalia_rivero.jpg', '2026-03-12', '2000-12-01', 55.40, 'Jorge Rivero (padre)'),
(8, 'socios/carla_ardaya.jpg', '2026-03-20', '1997-03-25', 60.70, 'Lucía Paz (madre)'),
(9, 'socios/juan_aguilera.jpg', '2026-04-02', '2002-06-14', 72.00, 'Mario Aguilera (padre)'),
(10, 'socios/marcelo_vaca.jpg', '2026-04-10', '1996-10-09', 88.60, 'Silvia Zeballos (madre)'),
(12, 'socios/patricia_ortiz.jpg', '2026-04-02', '1991-01-19', 64.30, 'Raúl Ortiz (esposo)'),
(13, 'socios/oscar_medina.jpg', '2026-04-10', '1994-08-27', 77.80, 'Carmen Rojas (madre)'),
(14, 'socios/joel_castellon.jpg', '2026-04-15', '2003-02-11', 69.90, 'Julia Mamani (madre)'),
(15, 'socios/maria_lopez.jpg', '2026-04-22', '1998-09-05', 57.10, 'José Lopez (padre)');

INSERT INTO bitacora (id_bitacora, direccion_ip, nombre_usuario_db, accion, tabla_afectada, descripcion, fecha_hora, id_usuario) VALUES
(1, '192.168.1.10', 'lcuellar', 'LOGIN', 'usuario', 'Inicio de sesión exitoso', '2026-11-02 07:58:00', 4),
(2, '192.168.1.15', 'mjustiniano', 'CREATE', 'socio', 'Registro del socio Juan Pablo Aguilera Castedo', '2026-04-02 12:00:00', 3),
(3, '192.168.1.15', 'mjustiniano', 'CREATE', 'venta', 'Venta POS #1 por Bs 266.00', '2026-11-02 08:30:00', 3),
(4, '192.168.1.10', 'lcuellar', 'UPDATE', 'arqueo_caja', 'Cierre caja #1; diferencia Bs 0.00', '2026-11-02 22:00:00', 4),
(5, '192.168.1.10', 'lcuellar', 'REPORTE', 'reporte', 'Reporte ''Ventas'' exportado en PDF (3 filas).', '2026-11-10 09:20:00', 4),
(6, '192.168.1.22', 'portiz', 'DELETE', 'turno', 'Turno ''Madrugada'' eliminado.', '2026-11-11 10:05:00', 12);

INSERT INTO contrato_laboral (id_contrato_laboral, id_usuario, cargo, salario_mensual, fecha_inicio, fecha_finalizacion, estado) VALUES
(1, 1, 'Entrenador Principal', 4500, '2025-01-15', NULL, 'Activo'),
(2, 6, 'Entrenador de Fuerza', 3800, '2025-06-01', NULL, 'Activo'),
(3, 3, 'Recepcionista', 2800, '2026-01-10', NULL, 'Activo'),
(4, 7, 'Recepcionista', 2800, '2026-03-12', NULL, 'Activo'),
(5, 8, 'Entrenadora de Cardio', 3500, '2026-03-20', NULL, 'Activo'),
(6, 11, 'Entrenador Funcional', 3600, '2026-04-12', NULL, 'Activo'),
(7, 1, 'Entrenador Junior', 3000, '2024-02-01', '2025-01-14', 'Finalizado');

INSERT INTO producto (id_producto, id_categoria, nombre_producto, moneda_origen, precio_base_original, precio_venta_local, costo_promedio_local, stock_actual, stock_minimo, stock_maximo, clasificacion_abc, estado) VALUES
(1, 6, 'Multivitamínico 60 cápsulas', 'USD', 15, 160, 104.40, 60, 15, 100, 'B', 'Activo'),
(2, 12, 'Gomitas de Proteína', 'BOB', 2, 3.50, 2, 150, 30, 250, 'A', 'Activo'),
(3, 11, 'Barra Energética Proteica', 'BOB', 12, 20, 12, 180, 40, 300, 'A', 'Activo'),
(4, 7, 'Polera Deportiva Dry-Fit', 'BOB', 60, 120, 60, 95, 20, 150, 'B', 'Activo'),
(5, 15, 'Trofeo Conmemorativo', 'BOB', 35, 70, 35, 20, 5, 40, 'C', 'Activo'),
(6, 9, 'Agua Mineral 500 ml', 'BOB', 2.50, 5, 2.50, 300, 80, 500, 'A', 'Activo'),
(7, 10, 'Bebida Isotónica 500 ml', 'BOB', 6, 10, 6, 200, 40, 350, 'C', 'Activo'),
(8, 8, 'Short Deportivo Pro', 'BOB', 70, 130, 70, 80, 15, 120, 'B', 'Activo'),
(9, 10, 'Bebida Energética 473 ml', 'BOB', 9, 15, 9, 35, 50, 400, 'A', 'Activo'),
(10, 13, 'Mochila Deportiva Gym', 'USD', 18, 220, 125.28, 30, 8, 60, 'B', 'Activo'),
(11, 14, 'Toalla de Microfibra', 'BOB', 20, 40, 20, 0, 12, 90, 'C', 'Activo');

-- FASE 3: TRANSACCIONES OPERATIVAS
INSERT INTO arqueo_caja (id_caja, id_administrador, responsable_id, turno_id, fecha_apertura, fecha_cierre, monto_inicial, monto_final, efectivo_contado, diferencia, estado) VALUES
(1, 4, 3, 1, '2026-11-02 07:30:00', '2026-11-02 22:00:00', 200, 466.00, 466.00, 0.00, 'CERRADA'),
(2, 12, 7, 3, '2026-11-10 07:30:00', '2026-11-10 22:00:00', 200, 405.00, 400.00, -5.00, 'CERRADA'),
(3, 4, 3, 1, '2026-11-17 07:30:00', NULL, 250, NULL, NULL, NULL, 'ABIERTA');

INSERT INTO egreso_caja (id_egreso, caja_id, usuario_id, fecha_hora, concepto, monto, observacion) VALUES
(1, 2, 7, '2026-11-10 12:15:00', 'Compra de material de limpieza', 35.00, 'Factura menor'),
(2, 3, 3, '2026-11-17 09:00:00', 'Pago de agua para recepción', 20.00, NULL);

INSERT INTO compra (id_compra, id_administrador, id_proveedor, fecha_hora, nro_factura_proveedor, tasa_cambio_aplicada, monto_total_origen, monto_total_local, estado_compra) VALUES
(1, 4, 1, '2026-10-05 10:00:00', 'FAC-2026-101', 1.0000, 500.00, 500.00, 'Completada'),
(2, 12, 2, '2026-10-20 14:30:00', 'FAC-2026-405', 6.9600, 360.00, 2505.60, 'Completada'),
(3, 4, 3, '2026-11-03 09:15:00', 'FAC-2026-789', 1.0000, 6000.00, 6000.00, 'Completada'),
(4, 12, 1, '2026-09-15 11:00:00', 'FAC-2026-055', 1.0000, 900.00, 900.00, 'Completada');

INSERT INTO horario_laboral (id, id_turno, id_contrato_laboral, dia_semana, tolerancia_minutos) VALUES
(1, 1, 3, 'Lunes', 10),
(2, 1, 3, 'Martes', 10),
(3, 3, 4, 'Lunes', 10),
(4, 1, 1, 'Martes', 15),
(5, 3, 2, 'Miercoles', 5);

INSERT INTO pago_planilla (id_pago_planilla, id_contrato_laboral, periodo_mes, periodo_anio, salario_base, bonos, descuentos, total_pagado, fecha_pagada) VALUES
(1, 1, 10, 2026, 4500, 300, 0, 4800, '2026-10-31'),
(2, 2, 10, 2026, 3800, 150, 50, 3900, '2026-10-31'),
(3, 3, 10, 2026, 2800, 100, 0, 2900, '2026-10-31');

INSERT INTO marcacion_personal (id_marcacion_personal, id_contrato_laboral, fecha_hora, tipo_evento, metodo) VALUES
(1, 1, '2026-11-17 07:05:00', 'ENTRADA', 'Sistema Web'),
(2, 3, '2026-11-17 07:12:00', 'ENTRADA', 'Sistema Web'),
(3, 1, '2026-11-16 12:02:00', 'SALIDA', 'Sistema Web'),
(4, 2, '2026-11-17 14:20:00', 'ENTRADA', 'Voz');

INSERT INTO contrato_membresia (id_contrato_mem, id_socio, id_metodo_pago, id_plan_mem, id_renovacion, tipo_operacion, fecha_inicio, fecha_vencimiento, tasa_cambio_aplicada, monto_pagado_local, estado_membresia) VALUES
(1, 1, 1, 1, NULL, 'Alta', '2026-11-02', '2026-12-01', 1.0000, 250, 'Activa'),
(2, 3, 1, 1, NULL, 'Alta', '2026-09-01', '2026-09-30', 1.0000, 250, 'Activa'),
(3, 3, 3, 2, 2, 'Renovacion', '2026-10-01', '2026-12-29', 1.0000, 650, 'Activa'),
(4, 4, 1, 3, NULL, 'Alta', '2026-11-10', '2027-11-09', 1.0000, 2200, 'Activa'),
(5, 5, 4, 1, NULL, 'Alta', '2026-10-21', '2026-11-19', 1.0000, 250, 'Activa'),
(6, 9, 5, 2, NULL, 'Alta', '2026-08-20', '2026-11-17', 6.9600, 650, 'Activa');

INSERT INTO marcacion_acceso (id_marcacion_acceso, id_socio, fecha_hora, tipo_acceso, observacion) VALUES
(1, 1, '2026-11-17 07:15:00', 'PERMITIDO', 'Membresía vigente'),
(2, 3, '2026-11-17 09:00:00', 'PERMITIDO', 'Membresía vigente'),
(3, 10, '2026-11-17 10:20:00', 'DENEGADO', 'Sin membresía vigente'),
(4, 4, '2026-11-16 18:40:00', 'PERMITIDO', 'Membresía vigente');

INSERT INTO asignacion_rutina (id_asignacion_rutina, id_entrenador, id_socio, id_rutina, fecha_asignacion, fecha_inicio, fecha_fin, observaciones, estado, turno) VALUES
(1, 1, 1, 1, '2026-11-02', '2026-11-03', '2026-12-01', 'Adaptación inicial', 'Activa', 'mañana'),
(2, 6, 3, 2, '2026-10-02', '2026-10-03', '2026-12-29', NULL, 'Activa', 'tarde'),
(3, 1, 4, 3, '2026-11-10', '2026-11-11', NULL, 'Revisar técnica de peso muerto', 'Activa', 'noche');

INSERT INTO detalle_rutina (id, id_rutina, id_ejercicio, orden, series, repeticiones, descanso_minutos) VALUES
(1, 1, 2, 1, 3, 12, 1.5),
(2, 1, 1, 2, 3, 10, 1.5),
(3, 2, 5, 1, 4, 10, 1.5),
(4, 3, 2, 1, 5, 5, 2.0),
(5, 3, 3, 2, 5, 5, 2.5),
(6, 4, 8, 1, 3, 12, 1.0);

INSERT INTO venta (id_venta, id_usuario, id_metodo_pago, id_socio, caja_id, fecha_hora, nro_factura, tasa_cambio_aplicada, monto_total_local, estado_venta) VALUES
(1, 3, 1, 1, 1, '2026-11-02 08:30:00', 'FAC-2026-0001', 1.0000, 266.00, 'Completada'),
(2, 7, 1, 3, 2, '2026-11-10 11:15:00', 'FAC-2026-0002', 1.0000, 250.00, 'Completada'),
(3, 3, 2, 4, 1, '2026-11-02 15:40:00', 'FAC-2026-0003', 1.0000, 2200.00, 'Completada'),
(4, 3, 1, 5, 3, '2026-11-17 08:10:00', 'FAC-2026-0004', 1.0000, 30.00, 'Completada');

-- FASE 4: DETALLES DE TRANSACCIONES Y LOGÍSTICA
INSERT INTO detalle_compra (id, id_compra, id_producto, cantidad, costo_unitario_origen, costo_unitario_local, subtotal_origen, subtotal_local) VALUES
(1, 1, 6, 100, 2.50, 2.50, 250.00, 250.00),
(2, 1, 7, 50, 5.00, 5.00, 250.00, 250.00),
(3, 2, 10, 20, 18.00, 125.28, 360.00, 2505.60),
(4, 3, 4, 100, 60.00, 60.00, 6000.00, 6000.00),
(5, 4, 9, 100, 9.00, 9.00, 900.00, 900.00);

INSERT INTO kardex_inventario (id_kardex, id_producto, fecha_movimiento, tipo_movimiento, cantidad, motivo) VALUES
(1, 6, '2026-10-05 10:00:00', 'INGRESO', 100, 'Compra #1'),
(2, 7, '2026-10-05 10:00:00', 'INGRESO', 50, 'Compra #1'),
(3, 10, '2026-10-20 14:30:00', 'INGRESO', 20, 'Compra #2'),
(4, 4, '2026-11-03 09:15:00', 'INGRESO', 100, 'Compra #3'),
(5, 6, '2026-11-02 08:30:00', 'SALIDA', 2, 'Venta POS #1'),
(6, 3, '2026-11-02 08:30:00', 'SALIDA', 3, 'Venta POS #1'),
(7, 6, '2026-11-17 08:10:00', 'SALIDA', 2, 'Venta POS #4'),
(8, 7, '2026-11-17 08:10:00', 'SALIDA', 2, 'Venta POS #4'),
(9, 11, '2026-11-12 16:00:00', 'AJUSTE_NEGATIVO', 4, 'Toallas dañadas'),
(10, 9, '2026-09-15 11:00:00', 'INGRESO', 100, 'Compra #4');

INSERT INTO alerta_reposicion (id_alerta_repo, id_admin, id_producto, codigo_evento_global, nivel_urgencia, cantidad_sugerida, estado_alerta, orden_compra_erp, fecha_generacion, fecha_cierre) VALUES
(1, 4, 9, 'AUTO', 'Bajo', 365, 'Pendiente', NULL, '2026-11-15 18:00:00', NULL),
(2, 4, 11, 'AUTO', 'Agotado', 90, 'Pendiente', NULL, '2026-11-12 16:00:00', NULL),
(3, 12, 6, 'AUTO', 'Bajo', 420, 'Cerrada', 'OC-2026-01', '2026-10-01 09:00:00', '2026-10-05 10:00:00');

INSERT INTO detalle_venta_producto (id, id_venta, id_producto, cantidad, precio_unitario_origen, precio_unitario_local, subtotal_origen, subtotal_local) VALUES
(1, 1, 6, 2, 5, 5, 10, 10),
(2, 1, 3, 3, 2, 2, 6, 6),
(3, 4, 6, 2, 5, 5, 10, 10),
(4, 4, 7, 2, 10, 10, 20, 20);

INSERT INTO detalle_venta_servicio (id, id_venta, id_plan_membresia, cantidad, precio_unitario_origen, precio_unitario_local, subtotal_origen, subtotal_local) VALUES
(1, 1, 1, 1, 250, 250, 250, 250),
(2, 2, 1, 1, 250, 250, 250, 250),
(3, 3, 3, 1, 2200, 2200, 2200, 2200);

-- FASE 5: PAGOS EN LÍNEA, CONFIGURACIÓN Y NOTIFICACIONES
INSERT INTO configuracion_sistema (id_configuracion, clave, valor, fecha_actualizacion, actualizado_por) VALUES
(1, 'tipo_cambio_usd', 6.9600, '2026-11-01 08:00:00', 4);

INSERT INTO pago_pasarela (id_pago, proveedor, id_orden_externa, id_captura_externa, tipo_operacion, id_usuario, id_socio, id_plan_mem, id_contrato_mem, monto_local, monto_usd, tasa_cambio, estado, fecha_creacion, fecha_actualizacion) VALUES
(1, 'PAYPAL', '5O190127TN364715T', '3C679366HH908993F', 'MEMBRESIA', 9, 9, 2, 6, 650.00, 93.39, 6.9600, 'COMPLETADO', '2026-08-20 10:00:00', '2026-08-20 10:01:30'),
(2, 'PAYPAL', '8AB12345CD678901E', NULL, 'MEMBRESIA', 13, 13, 1, NULL, 250.00, 35.92, 6.9600, 'CANCELADO', '2026-11-14 19:00:00', '2026-11-14 19:05:00');

INSERT INTO notificacion (id_notificacion, id_usuario, tipo, titulo, mensaje, pantalla, referencia, leida, enviada_correo, fecha_creacion) VALUES
(1, 4, 'STOCK_BAJO', 'Stock bajo: Bebida Energética 473 ml', 'Quedan 35 unidad(es) de Bebida Energética 473 ml (mínimo 50). Se sugiere comprar 365 unidad(es).', 'alertas', 'stock-9-STOCK_BAJO-2026-11-15', 0, 1, '2026-11-15 18:00:00'),
(2, 4, 'STOCK_AGOTADO', 'Producto agotado: Toalla de Microfibra', 'Quedan 0 unidad(es) de Toalla de Microfibra (mínimo 12). Se sugiere comprar 90 unidad(es).', 'alertas', 'stock-11-STOCK_AGOTADO-2026-11-12', 1, 1, '2026-11-12 16:00:00'),
(3, 9, 'VENCIMIENTO', 'Tu membresía vence hoy', 'Tu Plan Trimestral Pro vence el 17/11/2026. Renueva para seguir entrenando.', 'inicio', 'venc-6-2026-11-17', 0, 1, '2026-11-17 06:00:00'),
(4, 5, 'VENCIMIENTO', 'Tu membresía vence en 2 días', 'Tu Plan Mensual Estándar vence el 19/11/2026.', 'inicio', 'venc-5-2026-11-17', 0, 1, '2026-11-17 06:00:00');

-- ==============================================================================
-- PROCEDIMIENTOS ALMACENADOS EN SQLite
-- SQLite no implementa CREATE PROCEDURE ni CREATE FUNCTION en SQL. La lógica
-- de negocio equivalente vive en el backend Django (api/membresias.py,
-- api/automatizacion.py, api/rrhh_views.py). En la base de datos se definen
-- VISTAS que encapsulan las consultas que esos procesos usan.
-- ==============================================================================

-- 1. Estado de membresía de cada socio (equivale a membresias.resumen_membresia, CU07).
CREATE VIEW vw_estado_membresia AS
SELECT s.id_socio,
       u.ci,
       u.first_name || ' ' || u.last_name AS socio,
       (SELECT pm.nombre_plan
          FROM contrato_membresia cm JOIN plan_membresia pm ON cm.id_plan_mem = pm.id_plan_membresia
         WHERE cm.id_socio = s.id_socio AND cm.estado_membresia = 'Activa'
         ORDER BY cm.fecha_vencimiento DESC LIMIT 1) AS plan,
       (SELECT MAX(cm.fecha_vencimiento) FROM contrato_membresia cm
         WHERE cm.id_socio = s.id_socio AND cm.estado_membresia = 'Activa') AS fecha_vencimiento,
       CASE
         WHEN (SELECT MAX(cm.fecha_vencimiento) FROM contrato_membresia cm
                WHERE cm.id_socio = s.id_socio AND cm.estado_membresia = 'Activa') IS NULL THEN 'Sin membresía'
         WHEN (SELECT MAX(cm.fecha_vencimiento) FROM contrato_membresia cm
                WHERE cm.id_socio = s.id_socio AND cm.estado_membresia = 'Activa') >= DATE('now', 'localtime') THEN 'Vigente'
         ELSE 'Vencida'
       END AS estado
FROM socio s
JOIN usuario u ON s.id_socio = u.id;

-- Uso (validación de acceso por CI):
-- SELECT estado FROM vw_estado_membresia WHERE ci = '78541234';

-- 2. Productos que requieren reposición (equivale a automatizacion.revisar_stock, CU16).
CREATE VIEW vw_productos_reposicion AS
SELECT p.id_producto,
       p.nombre_producto,
       p.stock_actual,
       p.stock_minimo,
       CASE WHEN p.stock_actual <= 0 THEN 'Agotado' ELSE 'Bajo' END AS nivel_urgencia,
       MAX(1, COALESCE(p.stock_maximo, p.stock_minimo * 2) - p.stock_actual) AS cantidad_sugerida
FROM producto p
WHERE p.stock_actual <= p.stock_minimo
  AND LOWER(p.estado) = 'activo';

-- 3. Recordatorios de vencimiento (equivale a automatizacion.generar_recordatorios_vencimiento).
CREATE VIEW vw_recordatorios_vencimiento AS
SELECT cm.id_contrato_mem,
       cm.id_socio,
       pm.nombre_plan,
       cm.fecha_vencimiento,
       CAST(JULIANDAY(cm.fecha_vencimiento) - JULIANDAY(DATE('now', 'localtime')) AS INTEGER) AS dias_restantes
FROM contrato_membresia cm
JOIN plan_membresia pm ON cm.id_plan_mem = pm.id_plan_membresia
WHERE cm.estado_membresia = 'Activa'
  AND cm.fecha_vencimiento BETWEEN DATE('now', 'localtime') AND DATE('now', 'localtime', '+3 days')
  AND NOT EXISTS (SELECT 1 FROM contrato_membresia c2
                  WHERE c2.id_socio = cm.id_socio AND c2.estado_membresia = 'Activa'
                    AND c2.fecha_vencimiento > cm.fecha_vencimiento);

-- 4. Resumen de cajas para el arqueo (CU10 y reporte estático "Arqueos de caja").
CREATE VIEW vw_resumen_caja AS
SELECT ac.id_caja,
       ac.estado,
       ac.fecha_apertura,
       ac.fecha_cierre,
       ac.monto_inicial,
       COALESCE((SELECT SUM(v.monto_total_local) FROM venta v
                 JOIN metodo_pago mp ON v.id_metodo_pago = mp.id_metodo_pago
                 WHERE v.caja_id = ac.id_caja AND mp.descripcion = 'Efectivo'), 0) AS ventas_efectivo,
       COALESCE((SELECT SUM(e.monto) FROM egreso_caja e WHERE e.caja_id = ac.id_caja), 0) AS egresos,
       ac.efectivo_contado,
       ac.diferencia
FROM arqueo_caja ac;

-- ==============================================================================
-- TRIGGERS (DISPARADORES) EN SQLite
-- El kardex automático (SALIDA por venta e INGRESO por compra) y las alertas
-- de reposición los registra el backend en api/automatizacion.py; por eso no
-- se duplican aquí. Los triggers protegen las reglas de integridad que el
-- backend también valida, para que se cumplan aunque se escriba directo en la BD.
-- ==============================================================================

-- 1. CU06: la fecha de vencimiento no puede ser anterior a la de inicio.
CREATE TRIGGER trg_validar_fechas_membresia
BEFORE INSERT ON contrato_membresia
WHEN NEW.fecha_vencimiento < NEW.fecha_inicio
BEGIN
    SELECT RAISE(ABORT, 'La fecha de vencimiento no puede ser anterior a la fecha de inicio.');
END;

-- 2. CU08 / CU15: el stock de un producto nunca puede quedar negativo.
CREATE TRIGGER trg_stock_no_negativo
BEFORE UPDATE OF stock_actual ON producto
WHEN NEW.stock_actual < 0
BEGIN
    SELECT RAISE(ABORT, 'Stock insuficiente: el stock no puede quedar negativo.');
END;

-- 3. CU21: un empleado solo puede tener un contrato laboral activo.
CREATE TRIGGER trg_un_contrato_laboral_activo
BEFORE INSERT ON contrato_laboral
WHEN NEW.estado = 'Activo'
 AND EXISTS (SELECT 1 FROM contrato_laboral
             WHERE id_usuario = NEW.id_usuario AND estado = 'Activo')
BEGIN
    SELECT RAISE(ABORT, 'El empleado ya tiene un contrato laboral activo.');
END;

-- 4. CU24: no se liquida dos veces el mismo contrato en el mismo periodo.
CREATE TRIGGER trg_planilla_sin_duplicados
BEFORE INSERT ON pago_planilla
WHEN EXISTS (SELECT 1 FROM pago_planilla
             WHERE id_contrato_laboral = NEW.id_contrato_laboral
               AND periodo_mes = NEW.periodo_mes
               AND periodo_anio = NEW.periodo_anio)
BEGIN
    SELECT RAISE(ABORT, 'El contrato ya fue liquidado en ese periodo.');
END;

-- 5. CU24: total pagado = máximo(0, salario base + bonos - descuentos).
CREATE TRIGGER trg_calculo_total_planilla
BEFORE INSERT ON pago_planilla
WHEN ROUND(NEW.total_pagado, 2) <> ROUND(MAX(0, NEW.salario_base + NEW.bonos - NEW.descuentos), 2)
BEGIN
    SELECT RAISE(ABORT, 'El total pagado no coincide con salario base + bonos - descuentos.');
END;

-- 6. CU10: no se registran egresos en una caja cerrada.
CREATE TRIGGER trg_egreso_caja_abierta
BEFORE INSERT ON egreso_caja
WHEN (SELECT estado FROM arqueo_caja WHERE id_caja = NEW.caja_id) <> 'ABIERTA'
BEGIN
    SELECT RAISE(ABORT, 'Solo se pueden registrar egresos en una caja abierta.');
END;

-- 7. Tipo de cambio: auditoría en bitácora de cada cambio del valor configurado.
CREATE TRIGGER trg_auditoria_tipo_cambio
AFTER UPDATE OF valor ON configuracion_sistema
WHEN OLD.valor <> NEW.valor
BEGIN
    INSERT INTO bitacora (direccion_ip, nombre_usuario_db, accion, tabla_afectada, descripcion, id_usuario)
    VALUES (NULL, 'Sistema', 'UPDATE', 'configuracion_sistema',
            'Cambio de ' || NEW.clave || ': ' || OLD.valor || ' -> ' || NEW.valor, NEW.actualizado_por);
END;

-- 8. PayPal: actualiza la fecha de modificación del pago (auto_now del modelo).
CREATE TRIGGER trg_pago_pasarela_fecha_actualizacion
AFTER UPDATE OF estado ON pago_pasarela
BEGIN
    UPDATE pago_pasarela SET fecha_actualizacion = CURRENT_TIMESTAMP WHERE id_pago = NEW.id_pago;
END;

