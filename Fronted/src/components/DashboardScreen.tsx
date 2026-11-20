// Funcionalidad adicional: dashboard con estadísticas reales del gimnasio.
// Se actualiza solo cada 2 minutos. Lo que se muestra depende del perfil.
import React, { useCallback, useEffect, useState } from 'react';
import api from '../services/api';

type Fila = Record<string, string | number>;
type Datos = {
  fecha: string;
  perfil: string;
  kpis?: Record<string, string | number | boolean>;
  ingresos_14_dias?: Fila[];
  accesos_por_hora?: Fila[];
  top_productos?: Fila[];
  membresias_por_plan?: Fila[];
  por_vencer?: { socio: string; ci: string; telefono: string; plan: string; vence: string; dias: number }[];
  stock_bajo?: { producto: string; stock: number; minimo: number }[];
  entrenamiento?: { asignaciones_activas: number; socios_entrenados: number; por_nivel: Fila[] };
};

const COLORES = ['#eab308', '#38bdf8', '#4ade80', '#f87171'];

const Tarjeta: React.FC<{ titulo: string; valor: React.ReactNode; color?: string; detalle?: string; onClick?: () => void }> = ({ titulo, valor, color = '#facc15', detalle, onClick }) => (
  <button onClick={onClick} disabled={!onClick} className="rounded-lg border border-gray-700 bg-gray-900 p-4 text-left enabled:hover:border-yellow-500">
    <p className="text-xs text-gray-400">{titulo}</p>
    <p className="mt-1 text-2xl font-bold" style={{ color }}>{valor}</p>
    {detalle && <p className="mt-1 text-xs text-gray-500">{detalle}</p>}
  </button>
);

function Barras({ titulo, filas, series, horizontal = false }: { titulo: string; filas: Fila[]; series: string[]; horizontal?: boolean }) {
  const max = Math.max(1, ...filas.flatMap((f) => series.map((s) => Number(f[s]) || 0)));
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 p-4">
      <h3 className="mb-3 font-bold text-yellow-400">{titulo}</h3>
      {series.length > 1 && (
        <div className="mb-2 flex gap-3 text-xs">{series.map((s, i) => <span key={s} className="flex items-center gap-1"><i className="inline-block h-2.5 w-2.5" style={{ background: COLORES[i] }} />{s}</span>)}</div>
      )}
      {filas.length === 0 ? <p className="py-6 text-center text-sm text-gray-500">Sin datos todavía.</p> : horizontal ? (
        <div className="grid gap-2">
          {filas.map((f, i) => (
            <div key={i} className="text-xs">
              <div className="mb-0.5 flex justify-between"><span className="truncate pr-2">{String(f.etiqueta)}</span><b>{f[series[0]]}</b></div>
              <div className="h-2.5 rounded bg-gray-800"><div className="h-2.5 rounded" style={{ width: `${(Number(f[series[0]]) / max) * 100}%`, background: COLORES[0] }} /></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex h-44 items-end gap-1">
          {filas.map((f, i) => (
            <div key={i} className="flex h-full flex-1 flex-col items-center justify-end" title={`${f.etiqueta}: ${series.map((s) => `${s} ${f[s]}`).join(' · ')}`}>
              <div className="flex h-full w-full items-end justify-center gap-px">
                {series.map((s, j) => <div key={s} className="w-full rounded-t" style={{ height: `${((Number(f[s]) || 0) / max) * 100}%`, background: COLORES[j], minHeight: Number(f[s]) ? 2 : 0 }} />)}
              </div>
              <span className="mt-1 text-[9px] text-gray-400">{String(f.etiqueta)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DashboardScreen({ onVolver, onIr }: { onVolver: () => void; onIr: (p: string) => void }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState('');
  const [actualizado, setActualizado] = useState('');

  const cargar = useCallback(async () => {
    try {
      const r = await api.get<Datos>('dashboard/');
      setDatos(r.data); setError(''); setActualizado(new Date().toLocaleTimeString('es-BO'));
    } catch (e: any) { setError(e?.response?.data?.detail || 'No se pudo cargar el dashboard.'); }
  }, []);
  useEffect(() => {
    void cargar();
    const id = window.setInterval(cargar, 120000);
    return () => window.clearInterval(id);
  }, [cargar]);

  const k = datos?.kpis;
  return (
    <section className="mx-auto w-full max-w-7xl">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-yellow-400 sm:text-3xl">DASHBOARD</h1>
          <p className="mt-1 text-sm text-gray-400">Datos reales del sistema · Perfil {datos?.perfil || '…'} · Actualizado {actualizado || '…'} (cada 2 min)</p>
        </div>
        <div className="flex gap-2">
          <button onClick={cargar} className="rounded border border-gray-600 px-3 py-2 hover:bg-gray-700">↻ Actualizar</button>
          <button onClick={onVolver} className="rounded border border-gray-600 px-3 py-2 hover:bg-gray-700">Volver</button>
        </div>
      </header>
      {error && <div className="mb-3 rounded border border-red-700 bg-red-950/50 p-3 text-red-300">{error}</div>}

      {k && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          <Tarjeta titulo="Ingresos de hoy" valor={`Bs ${k.ingresos_hoy}`} color="#4ade80" detalle={`${k.ventas_hoy} venta(s) POS`} />
          {k.ingresos_mes !== undefined && <Tarjeta titulo="Ingresos del mes" valor={`Bs ${k.ingresos_mes}`} color="#4ade80" detalle={`POS ${k.ventas_mes} · Membresías ${k.membresias_mes}`} />}
          <Tarjeta titulo="Socios con membresía vigente" valor={`${k.socios_activos}/${k.socios_total}`} detalle={`${k.nuevos_socios_mes} nuevo(s) este mes`} />
          <Tarjeta titulo="Vencen en 3 días o menos" valor={k.por_vencer as number} color={Number(k.por_vencer) ? '#fb923c' : '#4ade80'} onClick={() => onIr('contrato')} />
          <Tarjeta titulo="Ingresos de socios hoy" valor={k.accesos_hoy as number} color="#38bdf8" detalle={`${k.accesos_denegados_hoy} denegado(s)`} onClick={() => onIr('acceso')} />
          <Tarjeta titulo="Productos con stock bajo" valor={k.stock_bajo as number} color={Number(k.stock_bajo) ? '#f87171' : '#4ade80'} onClick={() => onIr('alertas')} />
          <Tarjeta titulo="Caja" valor={k.caja_abierta ? 'ABIERTA' : 'CERRADA'} color={k.caja_abierta ? '#4ade80' : '#9ca3af'} onClick={() => onIr('caja')} />
          <Tarjeta titulo="Personal presente hoy" valor={k.personal_presente as number} detalle="con marcación de entrada" />
        </div>
      )}

      {datos && (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {datos.ingresos_14_dias && <Barras titulo="Ingresos de los últimos 14 días (Bs)" filas={datos.ingresos_14_dias} series={['ventas', 'membresias']} />}
          {datos.accesos_por_hora && <Barras titulo="Horas pico — ingresos de los últimos 7 días" filas={datos.accesos_por_hora} series={['accesos']} />}
          {datos.top_productos && <Barras titulo="Productos más vendidos del mes" filas={datos.top_productos} series={['cantidad']} horizontal />}
          {datos.membresias_por_plan && <Barras titulo="Socios vigentes por plan" filas={datos.membresias_por_plan} series={['socios']} horizontal />}
          {datos.entrenamiento && (
            <div className="grid gap-3">
              <div className="grid grid-cols-2 gap-3">
                <Tarjeta titulo="Rutinas asignadas activas" valor={datos.entrenamiento.asignaciones_activas} />
                <Tarjeta titulo="Socios entrenados" valor={datos.entrenamiento.socios_entrenados} />
              </div>
              <Barras titulo="Asignaciones por nivel" filas={datos.entrenamiento.por_nivel} series={['asignaciones']} horizontal />
            </div>
          )}
          {datos.por_vencer && (
            <div className="rounded-lg border border-gray-700 bg-gray-900 p-4">
              <h3 className="mb-3 font-bold text-yellow-400">Membresías por vencer (3 días)</h3>
              {datos.por_vencer.length === 0 ? <p className="text-sm text-gray-500">Ninguna. </p> : (
                <table className="w-full text-sm"><tbody>
                  {datos.por_vencer.map((f, i) => (
                    <tr key={i} className="border-b border-gray-800">
                      <td className="py-1">{f.socio}</td><td>{f.plan}</td><td className="text-gray-400">{f.telefono}</td>
                      <td className={`text-right font-bold ${f.dias <= 1 ? 'text-red-400' : 'text-orange-300'}`}>{f.dias === 0 ? 'Hoy' : `${f.dias} d`}</td>
                    </tr>
                  ))}
                </tbody></table>
              )}
            </div>
          )}
          {datos.stock_bajo && (
            <div className="rounded-lg border border-gray-700 bg-gray-900 p-4">
              <h3 className="mb-3 font-bold text-yellow-400">Stock bajo</h3>
              {datos.stock_bajo.length === 0 ? <p className="text-sm text-gray-500">Todo el inventario está sobre el mínimo. </p> : (
                <table className="w-full text-sm"><tbody>
                  {datos.stock_bajo.map((p, i) => (
                    <tr key={i} className="border-b border-gray-800"><td className="py-1">{p.producto}</td>
                      <td className={`text-right font-bold ${p.stock <= 0 ? 'text-red-400' : 'text-orange-300'}`}>{p.stock} / mín. {p.minimo}</td></tr>
                  ))}
                </tbody></table>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
