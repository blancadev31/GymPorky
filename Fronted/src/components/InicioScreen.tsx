// Pantalla de inicio por perfil: cada rol ve sus accesos directos y sus
// indicadores (visualización por perfil de las funcionalidades del sistema).
import React, { useEffect, useState } from 'react';
import api from '../services/api';

type Usuario = {
  username: string;
  es_socio: boolean;
  es_entrenador: boolean;
  es_recepcionista: boolean;
  es_administrador: boolean;
};
type Props = { usuario: Usuario; onIr: (pantalla: string) => void };
type Atajo = { pantalla: string; titulo: string; descripcion: string; roles: (keyof Usuario)[] };

type MiPanel = {
  membresia: { estado: string; plan: string | null; fecha_vencimiento: string | null; dias_restantes: number | null; tiene_membresia: boolean };
  alerta_vencimiento: boolean;
  rutina: { nombre: string; nivel: string; turno: string; entrenador: string; ejercicios: { orden: number; ejercicio: string; series: number; repeticiones: number }[] } | null;
  visitas_mes: number;
  racha_dias: number;
  ultimo_ingreso: string | null;
  pagos?: Pago[];
};
type Pago = {
  nro: number; socio: string; ci: string; plan: string; operacion: string; inicio: string; vencimiento: string;
  metodo: string; monto: string; estado: string; referencia_paypal: string | null;
};

// Escapa texto antes de ponerlo en el HTML del comprobante.
const esc = (v: unknown) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));

// Abre el comprobante de pago de membresía en una ventana nueva lista para imprimir o guardar en PDF.
function verComprobante(p: Pago) {
  const fila = (k: string, v: string) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`;
  const html = `<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Comprobante de membresía N° ${esc(p.nro)}</title>
<style>body{font-family:Arial,sans-serif;max-width:560px;margin:24px auto;color:#111}h1{font-size:20px;margin:0}
.sub{color:#555;font-size:13px;margin:4px 0 16px}table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;width:42%;color:#444;font-weight:normal}th,td{padding:7px 4px;border-bottom:1px solid #ddd}
.total td,.total th{font-weight:bold;font-size:16px;color:#111}.nota{font-size:11px;color:#666;margin-top:16px}
button{margin-top:16px;padding:8px 14px}@media print{button{display:none}}</style></head><body>
<h1>PORKY GYM – Comprobante de pago de membresía</h1>
<p class="sub">Comprobante N° ${esc(p.nro)} · Emitido: ${esc(new Date().toLocaleString('es-BO'))}</p>
<table>${fila('Socio', p.socio)}${p.ci ? fila('CI', p.ci) : ''}${fila('Plan', p.plan)}${fila('Operación', p.operacion)}
${fila('Vigencia', `${p.inicio} al ${p.vencimiento}`)}${fila('Método de pago', p.metodo)}
${p.referencia_paypal ? fila('Referencia PayPal', p.referencia_paypal) : ''}${fila('Estado', p.estado)}
<tr class="total"><th>Total pagado</th><td>Bs ${esc(p.monto)}</td></tr></table>
<p class="nota">Comprobante interno sin valor fiscal.</p>
<button onclick="window.print()">Imprimir / Guardar PDF</button></body></html>`;
  const w = window.open('', '_blank');
  if (!w) { alert('Permita las ventanas emergentes para ver el comprobante.'); return; }
  w.document.write(html);
  w.document.close();
}

const ATAJOS: Atajo[] = [
  { pantalla: 'dashboard', titulo: 'Dashboard', descripcion: 'Estadísticas reales del gimnasio en tiempo real.', roles: ['es_administrador', 'es_recepcionista', 'es_entrenador'] },
  { pantalla: 'acceso', titulo: 'Control de acceso', descripcion: 'Validar el ingreso de socios.', roles: ['es_administrador', 'es_recepcionista'] },
  { pantalla: 'acceso', titulo: 'Marcar mi ingreso', descripcion: 'Registre su llegada al gimnasio.', roles: ['es_socio'] },
  { pantalla: 'registrar-socio', titulo: 'Nuevo socio', descripcion: 'Registrar expediente de socio.', roles: ['es_administrador', 'es_recepcionista'] },
  { pantalla: 'contrato', titulo: 'Membresías', descripcion: 'Registrar o renovar contrato.', roles: ['es_administrador', 'es_recepcionista'] },
  { pantalla: 'ventas', titulo: 'Punto de venta', descripcion: 'Procesar venta POS.', roles: ['es_administrador', 'es_recepcionista'] },
  { pantalla: 'caja', titulo: 'Arqueo de caja', descripcion: 'Abrir y cerrar caja.', roles: ['es_administrador', 'es_recepcionista'] },
  { pantalla: 'productos', titulo: 'Inventario', descripcion: 'Productos, compras y kardex.', roles: ['es_administrador'] },
  { pantalla: 'entrenamiento', titulo: 'Entrenamiento', descripcion: 'Ejercicios, rutinas y asignaciones.', roles: ['es_administrador', 'es_entrenador'] },
  { pantalla: 'entrenamiento', titulo: 'Mi rutina', descripcion: 'Consulte la rutina que le asignaron.', roles: ['es_socio'] },
  { pantalla: 'rrhh', titulo: 'Recursos humanos', descripcion: 'Contratos, turnos, asistencia y planilla.', roles: ['es_administrador'] },
  { pantalla: 'rrhh', titulo: 'Mi asistencia', descripcion: 'Marcar entrada/salida, mi horario y boletas.', roles: ['es_recepcionista', 'es_entrenador'] },
  { pantalla: 'reportes', titulo: 'Reportes', descripcion: 'Estáticos, dinámicos y estadísticos en PDF/Excel/CSV.', roles: ['es_administrador', 'es_recepcionista', 'es_entrenador'] },
  { pantalla: 'usuarios', titulo: 'Usuarios', descripcion: 'Administrar cuentas y roles.', roles: ['es_administrador'] },
  { pantalla: 'bitacora', titulo: 'Bitácora', descripcion: 'Auditoría de acciones.', roles: ['es_administrador'] },
];

export default function InicioScreen({ usuario, onIr }: Props) {
  const esPersonal = usuario.es_administrador || usuario.es_recepcionista;
  const [accesos, setAccesos] = useState<{ permitidos: number; denegados: number; socios_unicos: number } | null>(null);
  const [panel, setPanel] = useState<MiPanel | null>(null);

  useEffect(() => {
    if (esPersonal) api.get('acceso/resumen-hoy/').then((r) => setAccesos(r.data)).catch(() => undefined);
    else if (usuario.es_socio) api.get<MiPanel>('mi-panel/').then((r) => setPanel(r.data)).catch(() => undefined);
  }, [esPersonal, usuario.es_socio]);

  const roles = [
    usuario.es_administrador && 'Administrador',
    usuario.es_recepcionista && 'Recepcionista',
    usuario.es_entrenador && 'Entrenador',
    usuario.es_socio && 'Socio',
  ].filter(Boolean).join(', ') || 'Sin rol asignado';

  const visibles = ATAJOS.filter((a) => a.roles.some((r) => usuario[r]));
  const unicos = visibles.filter((a, i) => visibles.findIndex((b) => b.titulo === a.titulo) === i);

  return (
    <section className="mx-auto w-full max-w-6xl">
      <h1 className="text-2xl font-bold">BIENVENIDO AL SISTEMA PORKY GYM, <span className="text-yellow-400">{usuario.username}</span></h1>
      <p className="mt-1 text-gray-400">Perfil: <b className="text-white">{roles}</b>. Estas son las funciones disponibles para usted.</p>

      {accesos && (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded border border-gray-700 bg-gray-900 p-4"><p className="text-sm text-gray-400">Ingresos de socios hoy</p><p className="text-3xl font-bold text-green-400">{accesos.permitidos}</p></div>
          <div className="rounded border border-gray-700 bg-gray-900 p-4"><p className="text-sm text-gray-400">Accesos denegados hoy</p><p className="text-3xl font-bold text-red-400">{accesos.denegados}</p></div>
          <div className="rounded border border-gray-700 bg-gray-900 p-4"><p className="text-sm text-gray-400">Socios distintos hoy</p><p className="text-3xl font-bold text-yellow-400">{accesos.socios_unicos}</p></div>
        </div>
      )}
      {panel && (
        <div className="mt-4 grid gap-3">
          {panel.alerta_vencimiento && (
            <div className="rounded-lg border-2 border-orange-500 bg-orange-950/40 p-4 font-bold text-orange-200">
               Tu membresía vence {panel.membresia.dias_restantes === 0 ? 'hoy' : panel.membresia.dias_restantes === 1 ? 'mañana' : `en ${panel.membresia.dias_restantes} días`} ({panel.membresia.fecha_vencimiento}). Renuévala en recepción para no perder tu acceso.
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="rounded border border-gray-700 bg-gray-900 p-4 sm:col-span-2">
              <p className="text-sm text-gray-400">Mi membresía</p>
              <p className={`text-2xl font-bold ${panel.membresia.tiene_membresia ? 'text-green-400' : 'text-red-400'}`}>{panel.membresia.estado}</p>
              <p className="text-sm text-gray-300">{panel.membresia.plan || 'Sin plan'}{panel.membresia.fecha_vencimiento ? ` · vence ${panel.membresia.fecha_vencimiento}` : ''}</p>
              {panel.membresia.tiene_membresia && panel.membresia.dias_restantes !== null && (
                <div className="mt-2 h-2 rounded bg-gray-800"><div className="h-2 rounded bg-yellow-500" style={{ width: `${Math.min(100, (panel.membresia.dias_restantes / 30) * 100)}%` }} /></div>
              )}
            </div>
            <div className="rounded border border-gray-700 bg-gray-900 p-4"><p className="text-sm text-gray-400">Visitas este mes</p><p className="text-3xl font-bold text-yellow-400">{panel.visitas_mes}</p><p className="text-xs text-gray-500">Último: {panel.ultimo_ingreso || '—'}</p></div>
            <div className="rounded border border-gray-700 bg-gray-900 p-4"><p className="text-sm text-gray-400">Racha de días seguidos</p><p className="text-3xl font-bold text-orange-400"> {panel.racha_dias}</p></div>
          </div>
          <div className="rounded border border-gray-700 bg-gray-900 p-4">
            <p className="mb-2 font-bold text-yellow-400">Mi rutina de hoy</p>
            {panel.rutina ? (
              <>
                <p className="text-sm text-gray-300">{panel.rutina.nombre} · {panel.rutina.nivel} · turno {panel.rutina.turno} · Entrenador: {panel.rutina.entrenador}</p>
                <ol className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
                  {panel.rutina.ejercicios.map((e) => <li key={e.orden} className="rounded bg-gray-800 px-2 py-1">{e.orden}. {e.ejercicio} — {e.series}x{e.repeticiones}</li>)}
                </ol>
              </>
            ) : <p className="text-sm text-gray-400">Aún no tienes una rutina asignada. Pídela a tu entrenador.</p>}
          </div>
          <div className="rounded border border-gray-700 bg-gray-900 p-4">
            <p className="mb-2 font-bold text-yellow-400">Mis pagos y comprobantes</p>
            {panel.pagos && panel.pagos.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead className="text-gray-400"><tr><th className="p-2">N°</th><th className="p-2">Plan</th><th className="p-2">Vigencia</th><th className="p-2">Método</th><th className="p-2">Monto</th><th className="p-2"></th></tr></thead>
                  <tbody>
                    {panel.pagos.map((p) => (
                      <tr key={p.nro} className="border-t border-gray-800">
                        <td className="p-2">{p.nro}</td><td className="p-2">{p.plan}</td><td className="p-2">{p.inicio} – {p.vencimiento}</td>
                        <td className="p-2">{p.metodo}</td><td className="p-2">Bs {p.monto}</td>
                        <td className="p-2"><button onClick={() => verComprobante(p)} className="rounded bg-yellow-500 px-3 py-1 font-bold text-black">Ver comprobante</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="text-sm text-gray-400">Aún no tienes pagos de membresía registrados.</p>}
          </div>
          <p className="text-xs text-gray-500"> Pregúntale a PorkyBot (abajo a la derecha): "¿Cuándo vence mi membresía?" o di "marcar mi ingreso" con el micrófono.</p>
        </div>
      )}

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {unicos.map((a) => (
          <button key={a.titulo} onClick={() => onIr(a.pantalla)} className="rounded-lg border border-gray-700 bg-gray-900 p-4 text-left transition hover:border-yellow-500">
            <p className="text-lg font-bold text-yellow-400">{a.titulo}</p>
            <p className="mt-1 text-sm text-gray-300">{a.descripcion}</p>
          </button>
        ))}
      </div>
    </section>
  );
}
