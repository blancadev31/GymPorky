// CU07: VALIDAR ACCESO DE SOCIO
// - Administrador / Recepcionista: validan el ingreso por CI, usuario o correo,
//   ven el resultado (PERMITIDO / DENEGADO), métricas del día e historial.
// - Socio: marca su propio ingreso y consulta su historial de accesos.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import api from '../services/api';

type Props = { onVolver: () => void; esPersonal: boolean };

type Marcacion = {
  id_marcacion_acceso: number;
  socio_nombre: string;
  socio_ci: string | null;
  socio_username: string;
  fecha_hora: string;
  tipo_acceso: string;
  observacion: string;
};

type Resultado = {
  permitido: boolean;
  motivo: string;
  aviso?: string | null;
  membresia?: { estado: string; plan: string | null; fecha_vencimiento: string | null; dias_restantes: number | null };
  socio?: { nombre: string; username: string; ci: string | null };
};

const input = 'w-full rounded border border-gray-700 bg-gray-800 p-2 text-white outline-none focus:border-yellow-500';
const primary = 'rounded bg-yellow-500 px-4 py-2 font-bold text-black hover:bg-yellow-400 disabled:opacity-50';
const secondary = 'rounded border border-gray-600 px-4 py-2 text-white hover:bg-gray-700';

const fecha = (iso: string) => new Date(iso).toLocaleString('es-BO');

function errorTexto(e: any, porDefecto: string) {
  return e?.response?.data?.motivo || e?.response?.data?.detail || porDefecto;
}

export default function AccesoScreen({ onVolver, esPersonal }: Props) {
  const [termino, setTermino] = useState('');
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [historial, setHistorial] = useState<Marcacion[]>([]);
  const [resumen, setResumen] = useState({ permitidos: 0, denegados: 0, socios_unicos: 0 });
  const [filtros, setFiltros] = useState({ desde: '', hasta: '', tipo: '', q: '' });
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState('');
  const campo = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async () => {
    try {
      if (esPersonal) {
        const params = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v));
        const [h, r] = await Promise.all([api.get<Marcacion[]>('acceso/', { params }), api.get('acceso/resumen-hoy/')]);
        setHistorial(h.data);
        setResumen(r.data);
      } else {
        const h = await api.get<Marcacion[]>('acceso/mis-accesos/');
        setHistorial(h.data);
      }
    } catch (e) {
      setError(errorTexto(e, 'No se pudo cargar el historial de accesos.'));
    }
  }, [esPersonal, filtros]);

  useEffect(() => { void cargar(); }, [cargar]);

  const validar = async (e?: React.FormEvent, terminoVoz?: string) => {
    e?.preventDefault();
    const buscado = (terminoVoz ?? termino).trim();
    if (esPersonal && !buscado) { setError('Ingrese el CI, usuario o correo del socio.'); return; }
    setProcesando(true); setError(''); setResultado(null);
    try {
      const r = esPersonal
        ? await api.post<Resultado>('acceso/validar/', { termino: buscado })
        : await api.post<Resultado>('acceso/mi-ingreso/');
      setResultado(r.data);
      setTermino('');
      await cargar();
    } catch (err: any) {
      if (err?.response?.data?.motivo) setResultado(err.response.data);
      else setError(errorTexto(err, 'No se pudo validar el acceso.'));
      await cargar();
    } finally {
      setProcesando(false);
      campo.current?.focus();
    }
  };

  // Comando de voz del asistente: "validar acceso <CI>" o "marcar mi ingreso".
  useEffect(() => {
    let pendiente: string | null = null;
    try { pendiente = sessionStorage.getItem('acceso_termino_voz'); sessionStorage.removeItem('acceso_termino_voz'); } catch { /* ignore */ }
    if (!pendiente) return;
    if (esPersonal && pendiente !== '__yo__') { setTermino(pendiente); void validar(undefined, pendiente); }
    else if (!esPersonal) void validar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Si la pantalla ya estaba abierta, el asistente avisa con un evento.
  useEffect(() => {
    const alOir = (e: Event) => {
      const valor = (e as CustomEvent<string>).detail;
      try { sessionStorage.removeItem('acceso_termino_voz'); } catch { /* ignore */ }
      if (esPersonal && valor !== '__yo__') { setTermino(valor); void validar(undefined, valor); }
      else if (!esPersonal) void validar();
    };
    window.addEventListener('porky-acceso-voz', alOir);
    return () => window.removeEventListener('porky-acceso-voz', alOir);
  });

  return (
    <section className="mx-auto w-full max-w-6xl">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-yellow-400 sm:text-3xl">
            {esPersonal ? 'CONTROL DE ACCESO DE SOCIOS' : 'MARCAR MI INGRESO'}
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            {esPersonal
              ? 'Valide la membresía del socio antes de permitir su ingreso al gimnasio.'
              : 'Registre su ingreso al gimnasio. Se verifica que su membresía esté vigente.'}
          </p>
        </div>
        <button type="button" onClick={onVolver} className={secondary}>Volver</button>
      </header>

      {error && <div role="alert" className="mb-4 rounded border border-red-700 bg-red-950/50 p-3 text-red-300">{error}</div>}

      <div className="grid gap-4 lg:grid-cols-3">
        <form onSubmit={validar} className="rounded-lg border border-gray-700 bg-gray-900 p-5 lg:col-span-2">
          {esPersonal ? (
            <>
              <label className="text-sm text-gray-300">CI, usuario o correo del socio
                <input ref={campo} autoFocus className={`${input} mt-1 text-lg`} value={termino}
                  onChange={(e) => setTermino(e.target.value)} placeholder="Ej. 8765432 o juanperez" />
              </label>
              <button type="submit" disabled={procesando} className={`${primary} mt-4 w-full py-3 text-lg`}>
                {procesando ? 'Validando...' : 'VALIDAR ACCESO'}
              </button>
            </>
          ) : (
            <button type="submit" disabled={procesando} className={`${primary} w-full py-6 text-xl`}>
              {procesando ? 'Validando...' : 'MARCAR MI INGRESO AHORA'}
            </button>
          )}

          {resultado && (
            <div className={`mt-5 rounded-lg border-2 p-5 ${resultado.permitido ? 'border-green-500 bg-green-950/40' : 'border-red-500 bg-red-950/40'}`}>
              <p className={`text-3xl font-black ${resultado.permitido ? 'text-green-400' : 'text-red-400'}`}>
                {resultado.permitido ? ' ACCESO PERMITIDO' : ' ACCESO DENEGADO'}
              </p>
              <p className="mt-2 text-gray-200">{resultado.motivo}</p>
              {resultado.aviso && <p className="mt-2 font-bold text-yellow-300"> {resultado.aviso}</p>}
              {resultado.socio && (
                <div className="mt-3 grid gap-1 text-sm text-gray-300 sm:grid-cols-2">
                  <p>Socio: <b>{resultado.socio.nombre}</b> ({resultado.socio.username})</p>
                  <p>CI: <b>{resultado.socio.ci || '—'}</b></p>
                  <p>Plan: <b>{resultado.membresia?.plan || '—'}</b></p>
                  <p>Vence: <b>{resultado.membresia?.fecha_vencimiento || '—'}</b>
                    {resultado.membresia?.dias_restantes != null && ` (${resultado.membresia.dias_restantes} días)`}</p>
                </div>
              )}
            </div>
          )}
        </form>

        {esPersonal && (
          <div className="grid gap-3">
            <div className="rounded-lg border border-gray-700 bg-gray-900 p-4"><p className="text-sm text-gray-400">Ingresos permitidos hoy</p><p className="text-3xl font-bold text-green-400">{resumen.permitidos}</p></div>
            <div className="rounded-lg border border-gray-700 bg-gray-900 p-4"><p className="text-sm text-gray-400">Accesos denegados hoy</p><p className="text-3xl font-bold text-red-400">{resumen.denegados}</p></div>
            <div className="rounded-lg border border-gray-700 bg-gray-900 p-4"><p className="text-sm text-gray-400">Socios distintos hoy</p><p className="text-3xl font-bold text-yellow-400">{resumen.socios_unicos}</p></div>
          </div>
        )}
      </div>

      <div className="mt-6 rounded-lg border border-gray-700 bg-gray-900 p-4">
        <h2 className="mb-3 text-lg font-bold">{esPersonal ? 'Historial de accesos' : 'Mis accesos recientes'}</h2>
        {esPersonal && (
          <div className="mb-3 grid gap-2 sm:grid-cols-4">
            <input type="date" className={input} value={filtros.desde} onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })} />
            <input type="date" className={input} value={filtros.hasta} onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })} />
            <select className={input} value={filtros.tipo} onChange={(e) => setFiltros({ ...filtros, tipo: e.target.value })}>
              <option value="">Todos</option><option value="PERMITIDO">Permitidos</option><option value="DENEGADO">Denegados</option>
            </select>
            <input className={input} placeholder="Buscar socio" value={filtros.q} onChange={(e) => setFiltros({ ...filtros, q: e.target.value })} />
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] text-left text-sm">
            <thead className="bg-gray-800 text-yellow-400">
              <tr><th className="p-2">Fecha y hora</th>{esPersonal && <th className="p-2">Socio</th>}{esPersonal && <th className="p-2">CI</th>}<th className="p-2">Resultado</th><th className="p-2">Observación</th></tr>
            </thead>
            <tbody>
              {historial.map((m) => (
                <tr key={m.id_marcacion_acceso} className="border-b border-gray-800">
                  <td className="p-2">{fecha(m.fecha_hora)}</td>
                  {esPersonal && <td className="p-2">{m.socio_nombre}</td>}
                  {esPersonal && <td className="p-2">{m.socio_ci || '—'}</td>}
                  <td className={`p-2 font-bold ${m.tipo_acceso === 'PERMITIDO' ? 'text-green-400' : 'text-red-400'}`}>{m.tipo_acceso}</td>
                  <td className="p-2 text-gray-300">{m.observacion}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {historial.length === 0 && <p className="p-4 text-center text-gray-400">Sin accesos registrados.</p>}
        </div>
      </div>
    </section>
  );
}
