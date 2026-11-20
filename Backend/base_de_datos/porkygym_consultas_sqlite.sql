-- ==============================================================================
-- OPERACIONES DE ACTUALIZACIÓN (UPDATE)
-- ==============================================================================
-- 1. RRHH (CU21): Promoción de un empleado y aumento salarial del contrato 1.
UPDATE contrato_laboral
SET cargo = 'Entrenador Principal Senior',
    salario_mensual = 5200.00
WHERE id_contrato_laboral = 1;

-- 2. INVENTARIO (CU12): Ajuste de precio de venta del producto 1.
UPDATE producto
SET precio_venta_local = 175.00
WHERE id_producto = 1;

-- 3. LOGÍSTICA (CU16): Cierre de las alertas cuyo stock ya se recuperó
--    (misma regla que automatizacion.revisar_stock).
UPDATE alerta_reposicion
SET estado_alerta = 'Cerrada',
    fecha_cierre = CURRENT_TIMESTAMP
WHERE estado_alerta = 'Pendiente'
  AND id_producto IN (SELECT id_producto FROM producto WHERE stock_actual > stock_minimo);

-- 4. MEMBRESÍAS (CU06): Marcar como 'Vencida' todo contrato cuya fecha ya pasó.
UPDATE contrato_membresia
SET estado_membresia = 'Vencida'
WHERE fecha_vencimiento < DATE('now', 'localtime')
  AND estado_membresia = 'Activa';

-- 5. CONFIGURACIÓN (tipo de cambio): el Administrador actualiza el valor del USD.
UPDATE configuracion_sistema
SET valor = 6.9700,
    actualizado_por = 4,
    fecha_actualizacion = CURRENT_TIMESTAMP
WHERE clave = 'tipo_cambio_usd';

-- ==============================================================================
-- OPERACIONES DE ELIMINACIÓN (DELETE)
-- ==============================================================================
-- 1. RUTINAS (CU18): Quitar un ejercicio asignado por error a una rutina.
--    "Extensión de Tríceps" (ejercicio 8) en la rutina PPL (rutina 4).
DELETE FROM detalle_rutina
WHERE id_rutina = 4 AND id_ejercicio = 8;

-- 2. CATÁLOGO (CU11): Eliminar una categoría sin productos asociados.
--    Si tuviera productos, la clave foránea ON DELETE RESTRICT lo impediría.
DELETE FROM categoria_producto
WHERE id_categoria = 16
  AND NOT EXISTS (SELECT 1 FROM producto p WHERE p.id_categoria = 16);

-- 3. RRHH (CU22): Quitar un horario laboral asignado por error.
DELETE FROM horario_laboral
WHERE id_contrato_laboral = 2 AND dia_semana = 'Miercoles';

-- 4. NOTIFICACIONES: Limpiar avisos ya leídos con más de 30 días.
DELETE FROM notificacion
WHERE leida = 1
  AND fecha_creacion < DATETIME('now', '-30 days');

-- ==============================================================================
-- CONSULTAS (30 SQL) - SINTAXIS SQLite
-- ==============================================================================
-- ===== Consultas simples
-- 1. Inventario: productos en o por debajo del stock mínimo (CU16) — Base de las alertas de reposición: lista lo que hay que reponer antes de que se agote.
SELECT id_producto, nombre_producto, stock_actual, stock_minimo
FROM producto
WHERE stock_actual <= stock_minimo AND estado = 'Activo'
ORDER BY stock_actual ASC;

-- 2. Caja: caja abierta en este momento (CU10) — El sistema solo admite una caja ABIERTA a la vez (restricción una_sola_caja_abierta_global).
SELECT id_caja, responsable_id, turno_id, fecha_apertura, monto_inicial
FROM arqueo_caja
WHERE estado = 'ABIERTA';

-- 3. Membresías: planes activos con acceso a piscina (CU05) — Permite a recepción ofrecer los planes con beneficios premium.
SELECT nombre_plan, costo_base_origen, duracion_dias
FROM plan_membresia
WHERE acceso_piscina = 1 AND estado = 'Activo'
ORDER BY costo_base_origen DESC;

-- 4. Acceso: ingresos permitidos y denegados del día (CU07) — Monitor de afluencia del día en recepción.
SELECT tipo_acceso, COUNT(*) AS cantidad_marcaciones
FROM marcacion_acceso
WHERE DATE(fecha_hora) = DATE('now', 'localtime')
GROUP BY tipo_acceso;

-- 5. RRHH: masa salarial por estado de contrato (CU21) — Previsión del gasto mensual en sueldos.
SELECT estado, COUNT(*) AS contratos, SUM(salario_mensual) AS masa_salarial
FROM contrato_laboral
GROUP BY estado;

-- ===== Consultas múltiples
-- 6. Finanzas: ingresos por método de pago en el mes actual (reporte estadístico) — Mismo dato del reporte "Ingresos por método de pago".
SELECT mp.descripcion, COUNT(v.id_venta) AS transacciones, SUM(v.monto_total_local) AS ingreso_total
FROM venta v
JOIN metodo_pago mp ON v.id_metodo_pago = mp.id_metodo_pago
WHERE strftime('%Y-%m', v.fecha_hora) = strftime('%Y-%m', 'now', 'localtime')
GROUP BY mp.descripcion
ORDER BY ingreso_total DESC;

-- 7. Rutinas: detalle de una rutina con sus ejercicios en orden (CU18) — Es lo que ve el socio en su panel.
SELECT r.nombre_rutina, r.nivel, dr.orden, e.nombre_ejercicio, e.grupo_muscular,
       dr.series, dr.repeticiones, dr.descanso_minutos
FROM rutina r
JOIN detalle_rutina dr ON r.id_rutina = dr.id_rutina
JOIN ejercicio e ON dr.id_ejercicio = e.id_ejercicio
WHERE r.id_rutina = 1
ORDER BY dr.orden;

-- 8. RRHH: marcaciones del personal del día (CU23) — Cruza usuario, contrato y marcaciones.
SELECT u.first_name, u.last_name, cl.cargo, mp.fecha_hora, mp.tipo_evento, mp.metodo
FROM marcacion_personal mp
JOIN contrato_laboral cl ON mp.id_contrato_laboral = cl.id_contrato_laboral
JOIN usuario u ON cl.id_usuario = u.id
WHERE DATE(mp.fecha_hora) = DATE('now', 'localtime')
ORDER BY mp.fecha_hora;

-- 9. Membresías: socios con contrato activo y su vencimiento (CU06) — Reporte principal de recepción.
SELECT u.first_name, u.last_name, u.ci, pm.nombre_plan, cm.fecha_vencimiento, cm.estado_membresia
FROM contrato_membresia cm
JOIN socio s ON cm.id_socio = s.id_socio
JOIN usuario u ON s.id_socio = u.id
JOIN plan_membresia pm ON cm.id_plan_mem = pm.id_plan_membresia
WHERE cm.estado_membresia = 'Activa'
ORDER BY cm.fecha_vencimiento;

-- 10. Ventas: top 5 productos más vendidos (reporte estadístico) — Mismo cálculo del reporte "Productos más vendidos".
SELECT p.nombre_producto, cp.nombre_categoria, SUM(dvp.cantidad) AS unidades, SUM(dvp.subtotal_local) AS total_bs
FROM detalle_venta_producto dvp
JOIN producto p ON dvp.id_producto = p.id_producto
JOIN categoria_producto cp ON p.id_categoria = cp.id_categoria
GROUP BY p.nombre_producto, cp.nombre_categoria
ORDER BY unidades DESC
LIMIT 5;

-- 11. Kardex: ingresos al inventario con su producto (CU15) — Trazabilidad de entradas generadas por compras.
SELECT k.fecha_movimiento, p.nombre_producto, k.tipo_movimiento, k.cantidad, k.motivo
FROM kardex_inventario k
JOIN producto p ON k.id_producto = p.id_producto
WHERE k.tipo_movimiento = 'INGRESO'
ORDER BY k.fecha_movimiento DESC;

-- 12. Inventario: valorización por categoría (reporte estático) — Mismo cálculo del reporte "Inventario valorizado".
SELECT cp.nombre_categoria, SUM(p.stock_actual) AS unidades,
       ROUND(SUM(p.stock_actual * p.costo_promedio_local), 2) AS valorizado_bs
FROM producto p
JOIN categoria_producto cp ON p.id_categoria = cp.id_categoria
WHERE p.stock_actual > 0
GROUP BY cp.nombre_categoria
ORDER BY valorizado_bs DESC;

-- 13. Planilla: pagos de un periodo con empleado y cargo (CU24) — Detalle de la planilla liquidada.
SELECT u.first_name, u.last_name, cl.cargo, pp.periodo_mes, pp.periodo_anio,
       pp.salario_base, pp.bonos, pp.descuentos, pp.total_pagado
FROM pago_planilla pp
JOIN contrato_laboral cl ON pp.id_contrato_laboral = cl.id_contrato_laboral
JOIN usuario u ON cl.id_usuario = u.id
WHERE pp.periodo_anio = 2026 AND pp.periodo_mes = 10;

-- 14. Ventas: socios con compras acumuladas mayores a Bs 200 (CU08) — Identifica a los clientes que más compran.
SELECT u.first_name, u.last_name, u.email, COUNT(v.id_venta) AS compras, SUM(v.monto_total_local) AS total_gastado
FROM venta v
JOIN usuario u ON v.id_socio = u.id
GROUP BY u.id, u.first_name, u.last_name, u.email
HAVING SUM(v.monto_total_local) > 200
ORDER BY total_gastado DESC;

-- 15. Bitácora: eliminaciones y exportaciones de reportes (CU03 / reportes) — Trazabilidad de acciones sensibles.
SELECT b.fecha_hora, b.direccion_ip, u.username, b.accion, b.tabla_afectada, b.descripcion
FROM bitacora b
LEFT JOIN usuario u ON b.id_usuario = u.id
WHERE b.accion IN ('DELETE', 'REPORTE')
ORDER BY b.fecha_hora DESC;

-- ===== Subconsultas
-- 16. Socios sin ningún contrato de membresía (NOT IN) — Candidatos para campañas de captación.
SELECT first_name, last_name, email
FROM usuario
WHERE es_socio = 1
  AND id NOT IN (SELECT id_socio FROM contrato_membresia);

-- 17. Productos más caros que el promedio de su categoría (correlacionada) — Análisis de precios.
SELECT nombre_producto, precio_venta_local
FROM producto p1
WHERE precio_venta_local > (SELECT AVG(p2.precio_venta_local)
                            FROM producto p2
                            WHERE p2.id_categoria = p1.id_categoria);

-- 18. Proveedores de productos con alerta pendiente (IN anidado) — A quién llamar para reponer.
SELECT razon_social, telefono, email
FROM proveedor
WHERE id_proveedor IN (
    SELECT c.id_proveedor
    FROM compra c
    JOIN detalle_compra dc ON c.id_compra = dc.id_compra
    WHERE dc.id_producto IN (SELECT id_producto FROM alerta_reposicion WHERE estado_alerta = 'Pendiente')
);

-- 19. Socios cuya membresía vence en los próximos 3 días (subconsulta en WHERE) — Mismo criterio de los recordatorios automáticos (3, 2, 1 y 0 días).
SELECT u.first_name, u.last_name, u.telefono
FROM usuario u
WHERE u.id IN (
    SELECT id_socio
    FROM contrato_membresia
    WHERE estado_membresia = 'Activa'
      AND fecha_vencimiento BETWEEN DATE('now', 'localtime') AND DATE('now', 'localtime', '+3 days')
);

-- 20. Empleados con salario mayor al promedio (CTE) — Auditoría salarial interna.
WITH promedio AS (
    SELECT AVG(salario_mensual) AS media FROM contrato_laboral WHERE estado = 'Activo'
)
SELECT u.first_name, cl.cargo, cl.salario_mensual, ROUND((SELECT media FROM promedio), 2) AS promedio_gym
FROM contrato_laboral cl
JOIN usuario u ON cl.id_usuario = u.id
WHERE cl.estado = 'Activo'
  AND cl.salario_mensual > (SELECT media FROM promedio);

-- 21. Socios con acceso denegado hoy que no tienen ningún ingreso permitido (NOT EXISTS) — Detecta intentos de ingreso sin membresía vigente.
SELECT m1.id_socio, m1.fecha_hora, m1.observacion
FROM marcacion_acceso m1
WHERE m1.tipo_acceso = 'DENEGADO'
  AND DATE(m1.fecha_hora) = DATE('now', 'localtime')
  AND NOT EXISTS (SELECT 1 FROM marcacion_acceso m2
                  WHERE m2.id_socio = m1.id_socio
                    AND m2.tipo_acceso = 'PERMITIDO'
                    AND DATE(m2.fecha_hora) = DATE('now', 'localtime'));

-- 22. Ejercicios que no están en ninguna rutina (NOT EXISTS) — Limpieza del catálogo de ejercicios.
SELECT e.nombre_ejercicio, e.equipo_requerido
FROM ejercicio e
WHERE NOT EXISTS (SELECT 1 FROM detalle_rutina dr WHERE dr.id_ejercicio = e.id_ejercicio);

-- 23. Margen bruto por producto con ranking (CTE + función de ventana) — Qué producto conviene impulsar.
WITH margenes AS (
    SELECT nombre_producto, precio_venta_local, costo_promedio_local,
           (precio_venta_local - costo_promedio_local) AS margen_bruto
    FROM producto
)
SELECT *, RANK() OVER (ORDER BY margen_bruto DESC) AS ranking
FROM margenes
WHERE margen_bruto > 0;

-- 24. Último pago de planilla de cada contrato (correlacionada) — Recibo más reciente por empleado.
SELECT cl.id_usuario, cl.cargo, pp.total_pagado, pp.fecha_pagada
FROM pago_planilla pp
JOIN contrato_laboral cl ON pp.id_contrato_laboral = cl.id_contrato_laboral
WHERE pp.fecha_pagada = (SELECT MAX(fecha_pagada) FROM pago_planilla
                         WHERE id_contrato_laboral = pp.id_contrato_laboral);

-- 25. Socios que renovaron al menos una vez (EXISTS) — Clientes leales.
SELECT u.first_name, u.last_name, u.email
FROM usuario u
WHERE EXISTS (SELECT 1 FROM contrato_membresia cm
              WHERE cm.id_socio = u.id AND cm.id_renovacion IS NOT NULL);

-- 26. Entrenadores sin asignaciones en los últimos 30 días (NOT EXISTS) — Seguimiento del trabajo del área de entrenamiento.
SELECT u.first_name, u.last_name, e.especialidad
FROM entrenador e
JOIN usuario u ON e.id_entrenador = u.id
WHERE NOT EXISTS (SELECT 1 FROM asignacion_rutina ar
                  WHERE ar.id_entrenador = e.id_entrenador
                    AND ar.fecha_asignacion >= DATE('now', 'localtime', '-30 days'));

-- 27. Compra más costosa registrada (subconsulta en FROM) — Control de gastos mayores.
SELECT mc.id_compra, mc.monto_total_local, p.razon_social
FROM (SELECT id_compra, id_proveedor, monto_total_local
      FROM compra ORDER BY monto_total_local DESC LIMIT 1) AS mc
JOIN proveedor p ON mc.id_proveedor = p.id_proveedor;

-- 28. Ingresos por día y promedio móvil de 7 días (CTE + ventana) — Base del gráfico "Ingresos diarios".
WITH ventas_diarias AS (
    SELECT DATE(fecha_hora) AS dia, SUM(monto_total_local) AS total_dia
    FROM venta
    GROUP BY DATE(fecha_hora)
)
SELECT dia, total_dia,
       ROUND(AVG(total_dia) OVER (ORDER BY dia ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS promedio_7_dias
FROM ventas_diarias
ORDER BY dia DESC;

-- 29. Cajas cerradas con diferencia en el arqueo (subconsulta escalar) — Descuadres entre lo esperado y lo contado (CU10).
SELECT ac.id_caja, ac.monto_inicial, ac.monto_final AS esperado, ac.efectivo_contado, ac.diferencia,
       (SELECT COALESCE(SUM(v.monto_total_local), 0) FROM venta v WHERE v.caja_id = ac.id_caja) AS ventas_caja,
       (SELECT COALESCE(SUM(e.monto), 0) FROM egreso_caja e WHERE e.caja_id = ac.id_caja) AS egresos_caja
FROM arqueo_caja ac
WHERE ac.estado = 'CERRADA' AND ac.diferencia <> 0;

-- 30. Productos clase C con ingresos por encima del promedio (CTE) — Detecta productos que deberían recategorizarse en la clasificación ABC.
WITH rendimiento AS (
    SELECT id_producto, SUM(subtotal_local) AS ingresos
    FROM detalle_venta_producto
    GROUP BY id_producto
)
SELECT p.nombre_producto, p.clasificacion_abc, r.ingresos
FROM producto p
JOIN rendimiento r ON p.id_producto = r.id_producto
WHERE p.clasificacion_abc = 'C'
  AND r.ingresos > (SELECT AVG(ingresos) FROM rendimiento)
ORDER BY r.ingresos DESC;

