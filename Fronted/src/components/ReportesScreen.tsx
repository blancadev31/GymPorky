// REPORTES (funcionalidad adicional)
//   - Estáticos   : formato fijo, se generan con un clic.
//   - Dinámicos   : el usuario elige entidad, columnas, filtros, orden y límite.
//   - Estadísticos: datos agregados mostrados como gráfico de barras.
// Todos se exportan a PDF, Excel (.xlsx) y CSV. El catálogo que se muestra
// depende del perfil del usuario (lo decide el backend en /reportes/).
import React, { useEffect, useMemo, useState } from 'react';
import api, { descargarArchivo } from '../services/api';

type Props = { onVolver: () => void };
type Columna = { clave: string; titulo: string };
type Catalogo = {
  roles: string[];
  estaticos: { clave: string; titulo: string }[];
  dinamicos: { clave: string; titulo: string; columnas: Columna[]; filtros: string[] }[];
  estadisticos: { clave: string; titulo: string; tipo: string }[];
};
type Datos = { titulo: string; subtitulo: string; columnas: Columna[]; filas: Record<string, string | number>[]; total_filas: number; series?: string[] };

const input = 'w-full rounded border border-gray-700 bg-gray-800 p-2 text-white outline-none focus:border-yellow-500';
const primary = 'rounded bg-yellow-500 px-4 py-2 font-bold text-black hover:bg-yellow-400 disabled:opacity-50';
const secondary = 'rounded border border-gray-600 px-3 py-2 text-white hover:bg-gray-700';
const COLORES = ['#eab308', '#38bdf8', '#4ade80', '#f87171'];
const ETIQUETA_FILTRO: Record<string, string> = { metodo: 'Método de pago', estado: 'Estado / tipo', plan: 'Plan' };

const limpiar = (o: Record<string, string>): Record<string, string> =>
  Object.fromEntries(Object.entries(o).filter(([, v]) => v)) as Record<string, string>;

function errorTexto(e: any) {
  return e?.response?.data?.detail || 'No se pudo generar el reporte.';
}

const BotonesExportar: React.FC<{ onExportar: (f: string) => void; deshabilitado?: boolean }> = ({ onExportar, deshabilitado }) => (
  <div className="flex flex-wrap gap-2">
    <button disabled={deshabilitado} className="rounded bg-red-700 px-3 py-2 font-bold text-white hover:bg-red-600 disabled:opacity-50" onClick={() => onExportar('pdf')}>PDF</button>
    <button disabled={deshabilitado} className="rounded bg-green-700 px-3 py-2 font-bold text-white hover:bg-green-600 disabled:opacity-50" onClick={() => onExportar('xlsx')}>Excel</button>
    <button disabled={deshabilitado} className="rounded bg-sky-700 px-3 py-2 font-bold text-white hover:bg-sky-600 disabled:opacity-50" onClick={() => onExportar('csv')}>CSV</button>
  </div>
);

const TablaVista: React.FC<{ datos: Datos }> = ({ datos }) => (
  <div className="mt-3">
    <p className="mb-2 text-sm text-gray-400">{datos.subtitulo}</p>
    <div className="max-h-[55vh] overflow-auto rounded border border-gray-700">
      <table className="w-full min-w-[640px] text-sm">
        <thead className="sticky top-0 bg-gray-800 text-yellow-400"><tr>{datos.columnas.map((c) => <th key={c.clave} className="p-2 text-left">{c.titulo}</th>)}</tr></thead>
        <tbody>
          {datos.filas.slice(0, 300).map((f, i) => (
            <tr key={i} className="border-b border-gray-800">{datos.columnas.map((c) => <td key={c.clave} className="p-2">{String(f[c.clave] ?? '')}</td>)}</tr>
          ))}
        </tbody>
      </table>
      {datos.filas.length === 0 && <p className="p-4 text-center text-gray-400">Sin registros.</p>}
    </div>
    {datos.total_filas > 300 && <p className="mt-1 text-xs text-gray-500">Vista previa de 300 filas; la exportación incluye las {datos.total_filas}.</p>}
  </div>
);

// Gráfico de barras en SVG (sin librerías externas).
const GraficoBarras: React.FC<{ datos: Datos }> = ({ datos }) => {
  const series = datos.series || [];
  const filas = datos.filas;
  const max = Math.max(1, ...filas.flatMap((f) => series.map((s) => Number(f[s]) || 0)));
  const ancho = Math.max(600, filas.length * (series.length * 18 + 14));
  const alto = 300;
  const base = alto - 60;
  const grupo = (ancho - 60) / Math.max(1, filas.length);
  const barra = Math.min(28, (grupo - 8) / Math.max(1, series.length));
  return (
    <div className="mt-3 overflow-x-auto rounded border border-gray-700 bg-gray-950 p-3">
      <div className="mb-2 flex flex-wrap gap-4 text-sm">
        {series.map((s, i) => <span key={s} className="flex items-center gap-1"><span className="inline-block h-3 w-3" style={{ background: COLORES[i % 4] }} />{datos.columnas.find((c) => c.clave === s)?.titulo || s}</span>)}
      </div>
      {filas.length === 0 ? <p className="p-6 text-center text-gray-400">Sin datos en el periodo.</p> : (
        <svg width={ancho} height={alto} role="img" aria-label={datos.titulo}>
          {[0, 0.25, 0.5, 0.75, 1].map((p) => (
            <g key={p}>
              <line x1={50} x2={ancho - 5} y1={base - p * (base - 20)} y2={base - p * (base - 20)} stroke="#374151" />
              <text x={45} y={base - p * (base - 20) + 4} fontSize="10" fill="#9ca3af" textAnchor="end">{Math.round(max * p)}</text>
            </g>
          ))}
          {filas.map((f, i) => {
            const x0 = 55 + i * grupo;
            return (
              <g key={i}>
                {series.map((s, j) => {
                  const v = Number(f[s]) || 0;
                  const h = (v / max) * (base - 20);
                  return <rect key={s} x={x0 + j * barra} y={base - h} width={barra - 2} height={h} fill={COLORES[j % 4]}><title>{`${f.etiqueta}: ${v}`}</title></rect>;
                })}
                <text x={x0 + (barra * series.length) / 2} y={base + 12} fontSize="10" fill="#d1d5db" textAnchor="end" transform={`rotate(-40 ${x0 + (barra * series.length) / 2} ${base + 12})`}>{String(f.etiqueta).slice(0, 18)}</text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
};

export default function ReportesScreen({ onVolver }: Props) {
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null);
  const [tab, setTab] = useState<'estaticos' | 'dinamicos' | 'estadisticos'>('estaticos');
  const [datos, setDatos] = useState<Datos | null>(null);
  const [actual, setActual] = useState<{ url: string; params: Record<string, string>; nombre: string } | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');

  // Estado del reporte dinámico
  const [entidad, setEntidad] = useState('');
  const [columnas, setColumnas] = useState<string[]>([]);
  const [filtros, setFiltros] = useState<Record<string, string>>({ desde: '', hasta: '', q: '', orden: 'desc', limite: '1000' });
  // Estado del estadístico
  const [rango, setRango] = useState({ desde: '', hasta: '' });

  useEffect(() => {
    api.get<Catalogo>('reportes/').then((r) => {
      setCatalogo(r.data);
      if (r.data.dinamicos.length) { setEntidad(r.data.dinamicos[0].clave); setColumnas(r.data.dinamicos[0].columnas.map((c) => c.clave)); }
    }).catch((e) => setError(errorTexto(e)));
  }, []);

  const defDinamico = useMemo(() => catalogo?.dinamicos.find((d) => d.clave === entidad), [catalogo, entidad]);

  const consultar = async (url: string, params: Record<string, string>, nombre: string) => {
    setCargando(true); setError('');
    try {
      const limpio = limpiar(params);
      const r = await api.get<Datos>(url, { params: limpio });
      setDatos(r.data); setActual({ url, params: limpio, nombre });
    } catch (e) { setError(errorTexto(e)); setDatos(null); }
    finally { setCargando(false); }
  };

  const exportar = async (formato: string, url?: string, params?: Record<string, string>, nombre?: string) => {
    const destino = url ? { url, params: params || {}, nombre: nombre || 'reporte' } : actual;
    if (!destino) return;
    setError('');
    try { await descargarArchivo(destino.url, { ...destino.params, formato }, `${destino.nombre}.${formato}`); }
    catch (e) { setError(errorTexto(e)); }
  };

  const cambiarEntidad = (clave: string) => {
    setEntidad(clave);
    const d = catalogo?.dinamicos.find((x) => x.clave === clave);
    setColumnas(d ? d.columnas.map((c) => c.clave) : []);
    setFiltros({ desde: '', hasta: '', q: '', orden: 'desc', limite: '1000' });
    setDatos(null);
  };
  const paramsDinamicos = () => ({ ...filtros, columnas: columnas.join(',') });

  return (
    <section className="mx-auto w-full max-w-7xl">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-yellow-400 sm:text-3xl">REPORTES</h1>
          <p className="mt-1 text-sm text-gray-400">Perfil: {catalogo?.roles.join(', ') || '…'} · Exportación a PDF, Excel y CSV.</p>
        </div>
        <button type="button" onClick={onVolver} className={secondary}>Volver</button>
      </header>

      <nav className="mb-4 flex flex-wrap gap-2">
        {([['estaticos', 'Reportes estáticos'], ['dinamicos', 'Reportes dinámicos'], ['estadisticos', 'Reportes estadísticos (gráficos)']] as const).map(([k, t]) => (
          <button key={k} className={tab === k ? primary : secondary} onClick={() => { setTab(k); setDatos(null); setActual(null); }}>{t}</button>
        ))}
      </nav>
      {error && <div role="alert" className="mb-3 rounded border border-red-700 bg-red-950/50 p-3 text-red-300">{error}</div>}

      {tab === 'estaticos' && catalogo && (
        <div className="grid gap-3 md:grid-cols-2">
          {catalogo.estaticos.map((r) => (
            <div key={r.clave} className="rounded border border-gray-700 bg-gray-900 p-4">
              <h3 className="mb-3 font-bold">{r.titulo}</h3>
              <div className="flex flex-wrap items-center gap-2">
                <button className={secondary} onClick={() => consultar(`reportes/estatico/${r.clave}/`, {}, r.clave)}>Ver en pantalla</button>
                <BotonesExportar onExportar={(f) => exportar(f, `reportes/estatico/${r.clave}/`, {}, r.clave)} />
              </div>
            </div>
          ))}
          {catalogo.estaticos.length === 0 && <p className="text-gray-400">Su perfil no tiene reportes estáticos.</p>}
        </div>
      )}

      {tab === 'dinamicos' && catalogo && (
        catalogo.dinamicos.length === 0 ? <p className="text-gray-400">Su perfil no tiene reportes dinámicos.</p> : (
          <div className="grid gap-3 rounded border border-gray-700 bg-gray-900 p-4">
            <div className="grid gap-3 md:grid-cols-4">
              <label className="text-sm text-gray-300">Información a reportar
                <select className={`${input} mt-1`} value={entidad} onChange={(e) => cambiarEntidad(e.target.value)}>
                  {catalogo.dinamicos.map((d) => <option key={d.clave} value={d.clave}>{d.titulo}</option>)}
                </select>
              </label>
              <label className="text-sm text-gray-300">Desde<input type="date" className={`${input} mt-1`} value={filtros.desde} onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })} /></label>
              <label className="text-sm text-gray-300">Hasta<input type="date" className={`${input} mt-1`} value={filtros.hasta} onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })} /></label>
              <label className="text-sm text-gray-300">Buscar texto<input className={`${input} mt-1`} value={filtros.q} onChange={(e) => setFiltros({ ...filtros, q: e.target.value })} placeholder="Socio, producto, etc." /></label>
              {defDinamico?.filtros.map((f) => (
                <label key={f} className="text-sm text-gray-300">{ETIQUETA_FILTRO[f] || f}
                  <input className={`${input} mt-1`} value={filtros[f] || ''} onChange={(e) => setFiltros({ ...filtros, [f]: e.target.value })} />
                </label>
              ))}
              <label className="text-sm text-gray-300">Orden
                <select className={`${input} mt-1`} value={filtros.orden} onChange={(e) => setFiltros({ ...filtros, orden: e.target.value })}><option value="desc">Más recientes primero</option><option value="asc">Más antiguos primero</option></select>
              </label>
              <label className="text-sm text-gray-300">Límite de filas<input type="number" min="1" max="5000" className={`${input} mt-1`} value={filtros.limite} onChange={(e) => setFiltros({ ...filtros, limite: e.target.value })} /></label>
            </div>
            <div>
              <p className="mb-1 text-sm text-gray-300">Columnas a incluir:</p>
              <div className="flex flex-wrap gap-2">
                {defDinamico?.columnas.map((c) => (
                  <label key={c.clave} className={`cursor-pointer rounded px-2 py-1 text-sm ${columnas.includes(c.clave) ? 'bg-yellow-500 text-black' : 'bg-gray-800'}`}>
                    <input type="checkbox" className="hidden" checked={columnas.includes(c.clave)} onChange={() => setColumnas(columnas.includes(c.clave) ? columnas.filter((x) => x !== c.clave) : [...columnas, c.clave])} />{c.titulo}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button className={primary} disabled={cargando || columnas.length === 0} onClick={() => consultar(`reportes/dinamico/${entidad}/`, paramsDinamicos(), `dinamico_${entidad}`)}>{cargando ? 'Generando…' : 'Generar reporte'}</button>
              <BotonesExportar deshabilitado={columnas.length === 0} onExportar={(f) => exportar(f, `reportes/dinamico/${entidad}/`, limpiar(paramsDinamicos()), `dinamico_${entidad}`)} />
            </div>
          </div>
        )
      )}

      {tab === 'estadisticos' && catalogo && (
        <div className="grid gap-3">
          <div className="flex flex-wrap items-end gap-2 rounded border border-gray-700 bg-gray-900 p-3">
            <label className="text-sm text-gray-300">Desde<input type="date" className={`${input} mt-1`} value={rango.desde} onChange={(e) => setRango({ ...rango, desde: e.target.value })} /></label>
            <label className="text-sm text-gray-300">Hasta<input type="date" className={`${input} mt-1`} value={rango.hasta} onChange={(e) => setRango({ ...rango, hasta: e.target.value })} /></label>
            <p className="text-xs text-gray-500">Si no elige fechas se usan los últimos 30 días.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {catalogo.estadisticos.map((r) => (
              <div key={r.clave} className="rounded border border-gray-700 bg-gray-900 p-4">
                <h3 className="mb-3 font-bold">{r.titulo}</h3>
                <div className="flex flex-wrap items-center gap-2">
                  <button className={secondary} onClick={() => consultar(`reportes/estadistico/${r.clave}/`, rango, r.clave)}>Ver gráfico</button>
                  <BotonesExportar onExportar={(f) => exportar(f, `reportes/estadistico/${r.clave}/`, limpiar(rango), r.clave)} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {datos && (
        <div className="mt-5 rounded border border-gray-700 bg-gray-900 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-bold text-yellow-400">{datos.titulo}</h2>
            <BotonesExportar onExportar={(f) => exportar(f)} />
          </div>
          {tab === 'estadisticos' && <GraficoBarras datos={datos} />}
          <TablaVista datos={datos} />
        </div>
      )}
    </section>
  );
}
