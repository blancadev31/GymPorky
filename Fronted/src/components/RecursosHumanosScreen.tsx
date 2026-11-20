// PAQUETE 6: RECURSOS HUMANOS
//   CU21 Administrar contratos laborales   (Administrador)
//   CU22 Configurar turnos y horarios      (Administrador)
//   CU23 Registrar marcación de asistencia (Administrador: control; personal: "Mi asistencia")
//   CU24 Liquidar planilla de pagos        (Administrador; el personal ve sus boletas)
import React, { useCallback, useEffect, useState } from 'react';
import api from '../services/api';

type Props = { onVolver: () => void; esAdministrador: boolean };

type Contrato = { id_contrato_laboral: number; id_usuario: number; empleado_nombre: string; empleado_username: string; empleado_roles: string; cargo: string; salario_mensual: string; fecha_inicio: string; fecha_finalizacion: string | null; estado: string };
type Empleado = { id: number; username: string; nombre: string; roles: string; tiene_contrato_activo: boolean };
type Turno = { id_turno: number; nombre_turno: string; hora_inicio: string; hora_fin: string };
type Horario = { id: number; id_contrato_laboral: number; empleado_nombre: string; cargo: string; id_turno: number; turno_nombre: string; hora_inicio: string; hora_fin: string; dia_semana: string; tolerancia_minutos: number };
type Marcacion = { id_marcacion_personal: number; empleado_nombre: string; cargo: string; fecha_hora: string; tipo_evento: string; metodo: string; estado: string; minutos_atraso: number };
type Pago = { id_pago_planilla: number; empleado_nombre: string; cargo: string; periodo_mes: number; periodo_anio: number; salario_base: string; bonos: string; descuentos: string; total_pagado: string; fecha_pagada: string };
type Previa = { id_contrato_laboral: number; empleado_nombre: string; cargo: string; salario_base: string; dias_programados: number; faltas: number; minutos_atraso: number; descuentos: string; total_estimado: string; ya_liquidado: boolean };

const DIAS = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo'];
const input = 'w-full rounded border border-gray-700 bg-gray-800 p-2 text-white outline-none focus:border-yellow-500';
const primary = 'rounded bg-yellow-500 px-4 py-2 font-bold text-black hover:bg-yellow-400 disabled:opacity-50';
const secondary = 'rounded border border-gray-600 px-3 py-2 text-white hover:bg-gray-700';
const peligro = 'rounded bg-red-700 px-3 py-1 text-white hover:bg-red-600';
const th = 'p-2 text-left';
const fechaHora = (iso: string) => new Date(iso).toLocaleString('es-BO');

function errorTexto(error: any): string {
  const data = error?.response?.data;
  if (!data) return 'No se pudo conectar con el servidor.';
  if (typeof data.detail === 'string') return data.detail;
  if (typeof data === 'object') return Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`).join(' | ');
  return 'Ocurrió un error al procesar la solicitud.';
}

const Tabla: React.FC<{ cabeceras: string[]; vacio: boolean; children: React.ReactNode }> = ({ cabeceras, vacio, children }) => (
  <div className="overflow-x-auto rounded border border-gray-700">
    <table className="w-full min-w-[640px] text-sm">
      <thead className="bg-gray-800 text-yellow-400"><tr>{cabeceras.map((c) => <th key={c} className={th}>{c}</th>)}</tr></thead>
      <tbody>{children}</tbody>
    </table>
    {vacio && <p className="p-4 text-center text-gray-400">Sin registros.</p>}
  </div>
);

// ---------------------------------------------------------------------------
// CU21
// ---------------------------------------------------------------------------
function Contratos({ avisar }: { avisar: (ok: string, err?: string) => void }) {
  const [contratos, setContratos] = useState<Contrato[]>([]);
  const [empleados, setEmpleados] = useState<Empleado[]>([]);
  const vacio = { id_usuario: '', cargo: '', salario_mensual: '', fecha_inicio: new Date().toISOString().slice(0, 10), fecha_finalizacion: '' };
  const [form, setForm] = useState(vacio);
  const [editando, setEditando] = useState<Contrato | null>(null);

  const cargar = useCallback(async () => {
    try {
      const [c, e] = await Promise.all([api.get<Contrato[]>('contratos-laborales/'), api.get<Empleado[]>('contratos-laborales/empleados-disponibles/')]);
      setContratos(c.data); setEmpleados(e.data);
    } catch (err) { avisar('', errorTexto(err)); }
  }, [avisar]);
  useEffect(() => { void cargar(); }, [cargar]);

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    const datos = { ...form, id_usuario: Number(form.id_usuario), fecha_finalizacion: form.fecha_finalizacion || null };
    try {
      if (editando) await api.patch(`contratos-laborales/${editando.id_contrato_laboral}/`, datos);
      else await api.post('contratos-laborales/', datos);
      avisar(editando ? 'Contrato actualizado.' : 'Contrato laboral registrado.');
      setForm(vacio); setEditando(null); await cargar();
    } catch (err) { avisar('', errorTexto(err)); }
  };
  const finalizar = async (c: Contrato) => {
    if (!window.confirm(`¿Finalizar el contrato de ${c.empleado_nombre}?`)) return;
    try { await api.post(`contratos-laborales/${c.id_contrato_laboral}/finalizar/`, {}); avisar('Contrato finalizado.'); await cargar(); }
    catch (err) { avisar('', errorTexto(err)); }
  };
  const editar = (c: Contrato) => {
    setEditando(c);
    setForm({ id_usuario: String(c.id_usuario), cargo: c.cargo, salario_mensual: c.salario_mensual, fecha_inicio: c.fecha_inicio, fecha_finalizacion: c.fecha_finalizacion || '' });
  };

  return (
    <div className="grid gap-4">
      <form onSubmit={guardar} className="grid gap-3 rounded border border-gray-700 bg-gray-900 p-4 md:grid-cols-5">
        <label className="text-sm text-gray-300 md:col-span-2">Empleado *
          <select required className={`${input} mt-1`} value={form.id_usuario} disabled={!!editando} onChange={(e) => setForm({ ...form, id_usuario: e.target.value })}>
            <option value="">Seleccione…</option>
            {empleados.filter((x) => !x.tiene_contrato_activo || String(x.id) === form.id_usuario).map((x) => <option key={x.id} value={x.id}>{x.nombre} — {x.roles}</option>)}
          </select>
        </label>
        <label className="text-sm text-gray-300">Cargo *<input required className={`${input} mt-1`} value={form.cargo} onChange={(e) => setForm({ ...form, cargo: e.target.value })} placeholder="Recepcionista" /></label>
        <label className="text-sm text-gray-300">Salario mensual (Bs) *<input required type="number" min="1" step="0.01" className={`${input} mt-1`} value={form.salario_mensual} onChange={(e) => setForm({ ...form, salario_mensual: e.target.value })} /></label>
        <label className="text-sm text-gray-300">Fecha inicio *<input required type="date" className={`${input} mt-1`} value={form.fecha_inicio} onChange={(e) => setForm({ ...form, fecha_inicio: e.target.value })} /></label>
        <label className="text-sm text-gray-300">Fecha fin (opcional)<input type="date" className={`${input} mt-1`} value={form.fecha_finalizacion} onChange={(e) => setForm({ ...form, fecha_finalizacion: e.target.value })} /></label>
        <div className="flex items-end gap-2 md:col-span-4">
          <button className={primary}>{editando ? 'Guardar cambios' : '+ Registrar contrato'}</button>
          {editando && <button type="button" className={secondary} onClick={() => { setEditando(null); setForm(vacio); }}>Cancelar</button>}
        </div>
      </form>
      <Tabla cabeceras={['Empleado', 'Roles', 'Cargo', 'Salario (Bs)', 'Inicio', 'Fin', 'Estado', 'Acciones']} vacio={contratos.length === 0}>
        {contratos.map((c) => (
          <tr key={c.id_contrato_laboral} className="border-b border-gray-800">
            <td className="p-2">{c.empleado_nombre}</td><td className="p-2">{c.empleado_roles}</td><td className="p-2">{c.cargo}</td>
            <td className="p-2">{c.salario_mensual}</td><td className="p-2">{c.fecha_inicio}</td><td className="p-2">{c.fecha_finalizacion || 'Indefinido'}</td>
            <td className={`p-2 font-bold ${c.estado === 'Activo' ? 'text-green-400' : 'text-gray-400'}`}>{c.estado}</td>
            <td className="flex gap-2 p-2">{c.estado === 'Activo' && <><button className={secondary} onClick={() => editar(c)}>Editar</button><button className={peligro} onClick={() => finalizar(c)}>Finalizar</button></>}</td>
          </tr>
        ))}
      </Tabla>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CU22
// ---------------------------------------------------------------------------
function TurnosHorarios({ avisar }: { avisar: (ok: string, err?: string) => void }) {
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [horarios, setHorarios] = useState<Horario[]>([]);
  const [contratos, setContratos] = useState<Contrato[]>([]);
  const [turno, setTurno] = useState({ nombre_turno: '', hora_inicio: '', hora_fin: '' });
  const [horario, setHorario] = useState({ id_contrato_laboral: '', id_turno: '', dias: [] as string[], tolerancia_minutos: '10' });

  const cargar = useCallback(async () => {
    try {
      const [t, h, c] = await Promise.all([api.get<Turno[]>('turnos-gestion/'), api.get<Horario[]>('horarios-laborales/'), api.get<Contrato[]>('contratos-laborales/', { params: { estado: 'Activo' } })]);
      setTurnos(t.data); setHorarios(h.data); setContratos(c.data);
    } catch (err) { avisar('', errorTexto(err)); }
  }, [avisar]);
  useEffect(() => { void cargar(); }, [cargar]);

  const crearTurno = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await api.post('turnos-gestion/', turno); avisar('Turno creado.'); setTurno({ nombre_turno: '', hora_inicio: '', hora_fin: '' }); await cargar(); }
    catch (err) { avisar('', errorTexto(err)); }
  };
  const borrarTurno = async (t: Turno) => {
    if (!window.confirm(`¿Eliminar el turno ${t.nombre_turno}?`)) return;
    try { await api.delete(`turnos-gestion/${t.id_turno}/`); avisar('Turno eliminado.'); await cargar(); }
    catch (err) { avisar('', errorTexto(err)); }
  };
  const asignar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (horario.dias.length === 0) { avisar('', 'Seleccione al menos un día.'); return; }
    const errores: string[] = [];
    for (const dia of horario.dias) {
      try {
        await api.post('horarios-laborales/', { id_contrato_laboral: Number(horario.id_contrato_laboral), id_turno: Number(horario.id_turno), dia_semana: dia, tolerancia_minutos: Number(horario.tolerancia_minutos) || 0 });
      } catch (err) { errores.push(`${dia}: ${errorTexto(err)}`); }
    }
    if (errores.length) avisar('', errores.join(' | ')); else avisar('Horario asignado.');
    setHorario({ ...horario, dias: [] }); await cargar();
  };
  const quitar = async (h: Horario) => {
    try { await api.delete(`horarios-laborales/${h.id}/`); avisar('Horario eliminado.'); await cargar(); }
    catch (err) { avisar('', errorTexto(err)); }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="grid content-start gap-3">
        <h3 className="font-bold text-yellow-400">Turnos (franjas horarias)</h3>
        <form onSubmit={crearTurno} className="grid gap-2 rounded border border-gray-700 bg-gray-900 p-3 sm:grid-cols-4">
          <input required className={input} placeholder="Nombre" value={turno.nombre_turno} onChange={(e) => setTurno({ ...turno, nombre_turno: e.target.value })} />
          <input required type="time" className={input} value={turno.hora_inicio} onChange={(e) => setTurno({ ...turno, hora_inicio: e.target.value })} />
          <input required type="time" className={input} value={turno.hora_fin} onChange={(e) => setTurno({ ...turno, hora_fin: e.target.value })} />
          <button className={primary}>+ Turno</button>
        </form>
        <Tabla cabeceras={['Turno', 'Inicio', 'Fin', '']} vacio={turnos.length === 0}>
          {turnos.map((t) => <tr key={t.id_turno} className="border-b border-gray-800"><td className="p-2">{t.nombre_turno}</td><td className="p-2">{t.hora_inicio.slice(0, 5)}</td><td className="p-2">{t.hora_fin.slice(0, 5)}</td><td className="p-2"><button className={peligro} onClick={() => borrarTurno(t)}>Eliminar</button></td></tr>)}
        </Tabla>
      </div>
      <div className="grid content-start gap-3">
        <h3 className="font-bold text-yellow-400">Horario laboral por empleado</h3>
        <form onSubmit={asignar} className="grid gap-2 rounded border border-gray-700 bg-gray-900 p-3">
          <select required className={input} value={horario.id_contrato_laboral} onChange={(e) => setHorario({ ...horario, id_contrato_laboral: e.target.value })}>
            <option value="">Empleado (contrato activo)…</option>
            {contratos.map((c) => <option key={c.id_contrato_laboral} value={c.id_contrato_laboral}>{c.empleado_nombre} — {c.cargo}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <select required className={input} value={horario.id_turno} onChange={(e) => setHorario({ ...horario, id_turno: e.target.value })}>
              <option value="">Turno…</option>
              {turnos.map((t) => <option key={t.id_turno} value={t.id_turno}>{t.nombre_turno} ({t.hora_inicio.slice(0, 5)}-{t.hora_fin.slice(0, 5)})</option>)}
            </select>
            <input type="number" min="0" className={input} value={horario.tolerancia_minutos} onChange={(e) => setHorario({ ...horario, tolerancia_minutos: e.target.value })} title="Tolerancia en minutos" />
          </div>
          <div className="flex flex-wrap gap-2">
            {DIAS.map((d) => (
              <label key={d} className={`cursor-pointer rounded px-2 py-1 text-sm ${horario.dias.includes(d) ? 'bg-yellow-500 text-black' : 'bg-gray-800'}`}>
                <input type="checkbox" className="hidden" checked={horario.dias.includes(d)} onChange={() => setHorario({ ...horario, dias: horario.dias.includes(d) ? horario.dias.filter((x) => x !== d) : [...horario.dias, d] })} />{d}
              </label>
            ))}
          </div>
          <button className={primary}>Asignar horario</button>
        </form>
        <Tabla cabeceras={['Empleado', 'Día', 'Turno', 'Tolerancia', '']} vacio={horarios.length === 0}>
          {horarios.map((h) => <tr key={h.id} className="border-b border-gray-800"><td className="p-2">{h.empleado_nombre}</td><td className="p-2">{h.dia_semana}</td><td className="p-2">{h.turno_nombre} ({h.hora_inicio.slice(0, 5)}-{h.hora_fin.slice(0, 5)})</td><td className="p-2">{h.tolerancia_minutos} min</td><td className="p-2"><button className={peligro} onClick={() => quitar(h)}>Quitar</button></td></tr>)}
        </Tabla>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CU23 (vista de control del administrador)
// ---------------------------------------------------------------------------
function ControlAsistencia({ avisar }: { avisar: (ok: string, err?: string) => void }) {
  const hoy = new Date().toISOString().slice(0, 10);
  const [marcaciones, setMarcaciones] = useState<Marcacion[]>([]);
  const [contratos, setContratos] = useState<Contrato[]>([]);
  const [filtro, setFiltro] = useState({ desde: hoy, hasta: hoy, contrato: '' });
  const [manual, setManual] = useState('');

  const cargar = useCallback(async () => {
    try {
      const params = Object.fromEntries(Object.entries(filtro).filter(([, v]) => v));
      const [m, c] = await Promise.all([api.get<Marcacion[]>('marcaciones-personal/', { params }), api.get<Contrato[]>('contratos-laborales/', { params: { estado: 'Activo' } })]);
      setMarcaciones(m.data); setContratos(c.data);
    } catch (err) { avisar('', errorTexto(err)); }
  }, [filtro, avisar]);
  useEffect(() => { void cargar(); }, [cargar]);

  const registrarManual = async () => {
    if (!manual) return;
    try { const r = await api.post('marcaciones-personal/', { id_contrato_laboral: Number(manual) }); avisar(`Marcación de ${r.data.tipo_evento} registrada (${r.data.estado}).`); await cargar(); }
    catch (err) { avisar('', errorTexto(err)); }
  };
  const anular = async (m: Marcacion) => {
    if (!window.confirm('¿Anular esta marcación?')) return;
    try { await api.delete(`marcaciones-personal/${m.id_marcacion_personal}/`); avisar('Marcación anulada.'); await cargar(); }
    catch (err) { avisar('', errorTexto(err)); }
  };
  const atrasos = marcaciones.filter((m) => m.estado === 'Atraso').length;

  return (
    <div className="grid gap-3">
      <div className="grid gap-2 rounded border border-gray-700 bg-gray-900 p-3 md:grid-cols-6">
        <input type="date" className={input} value={filtro.desde} onChange={(e) => setFiltro({ ...filtro, desde: e.target.value })} />
        <input type="date" className={input} value={filtro.hasta} onChange={(e) => setFiltro({ ...filtro, hasta: e.target.value })} />
        <select className={`${input} md:col-span-2`} value={filtro.contrato} onChange={(e) => setFiltro({ ...filtro, contrato: e.target.value })}>
          <option value="">Todo el personal</option>
          {contratos.map((c) => <option key={c.id_contrato_laboral} value={c.id_contrato_laboral}>{c.empleado_nombre}</option>)}
        </select>
        <select className={input} value={manual} onChange={(e) => setManual(e.target.value)}>
          <option value="">Marcación manual…</option>
          {contratos.map((c) => <option key={c.id_contrato_laboral} value={c.id_contrato_laboral}>{c.empleado_nombre}</option>)}
        </select>
        <button className={primary} onClick={registrarManual} disabled={!manual}>Registrar</button>
      </div>
      <p className="text-sm text-gray-400">Marcaciones: {marcaciones.length} · Atrasos: <span className="font-bold text-red-400">{atrasos}</span></p>
      <Tabla cabeceras={['Fecha y hora', 'Empleado', 'Cargo', 'Evento', 'Estado', 'Atraso', 'Método', '']} vacio={marcaciones.length === 0}>
        {marcaciones.map((m) => (
          <tr key={m.id_marcacion_personal} className="border-b border-gray-800">
            <td className="p-2">{fechaHora(m.fecha_hora)}</td><td className="p-2">{m.empleado_nombre}</td><td className="p-2">{m.cargo}</td>
            <td className="p-2">{m.tipo_evento}</td>
            <td className={`p-2 font-bold ${m.estado === 'Atraso' ? 'text-red-400' : m.estado === 'Puntual' ? 'text-green-400' : 'text-gray-300'}`}>{m.estado}</td>
            <td className="p-2">{m.minutos_atraso ? `${m.minutos_atraso} min` : '—'}</td><td className="p-2">{m.metodo}</td>
            <td className="p-2"><button className={peligro} onClick={() => anular(m)}>Anular</button></td>
          </tr>
        ))}
      </Tabla>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CU24
// ---------------------------------------------------------------------------
function Planilla({ avisar }: { avisar: (ok: string, err?: string) => void }) {
  const ahora = new Date();
  const mesAnterior = ahora.getMonth() === 0 ? 12 : ahora.getMonth();
  const anioMes = ahora.getMonth() === 0 ? ahora.getFullYear() - 1 : ahora.getFullYear();
  const [periodo, setPeriodo] = useState({ mes: String(mesAnterior), anio: String(anioMes) });
  const [previa, setPrevia] = useState<Previa[]>([]);
  const [bonos, setBonos] = useState<Record<string, string>>({});
  const [pagos, setPagos] = useState<Pago[]>([]);

  const cargarPagos = useCallback(async () => {
    try { const r = await api.get<Pago[]>('planilla/', { params: periodo }); setPagos(r.data); }
    catch (err) { avisar('', errorTexto(err)); }
  }, [periodo, avisar]);
  useEffect(() => { void cargarPagos(); }, [cargarPagos]);

  const previsualizar = async () => {
    try { const r = await api.get('planilla/previsualizar/', { params: periodo }); setPrevia(r.data.empleados); }
    catch (err) { avisar('', errorTexto(err)); }
  };
  const liquidar = async () => {
    if (!window.confirm(`¿Liquidar la planilla de ${periodo.mes}/${periodo.anio}? Esta acción genera los pagos.`)) return;
    try {
      const r = await api.post('planilla/liquidar/', { ...periodo, bonos });
      avisar(`Planilla liquidada: ${r.data.creados.length} pago(s).${r.data.omitidos.length ? ` Ya liquidados: ${r.data.omitidos.join(', ')}` : ''}`);
      setPrevia([]); setBonos({}); await cargarPagos();
    } catch (err) { avisar('', errorTexto(err)); }
  };
  const anular = async (p: Pago) => {
    if (!window.confirm(`¿Anular el pago de ${p.empleado_nombre}?`)) return;
    try { await api.delete(`planilla/${p.id_pago_planilla}/`); avisar('Pago anulado.'); await cargarPagos(); }
    catch (err) { avisar('', errorTexto(err)); }
  };
  const totalPlanilla = pagos.reduce((s, p) => s + Number(p.total_pagado), 0);

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-end gap-2 rounded border border-gray-700 bg-gray-900 p-3">
        <label className="text-sm text-gray-300">Mes<select className={`${input} mt-1`} value={periodo.mes} onChange={(e) => setPeriodo({ ...periodo, mes: e.target.value })}>{Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}</select></label>
        <label className="text-sm text-gray-300">Año<input type="number" className={`${input} mt-1 w-28`} value={periodo.anio} onChange={(e) => setPeriodo({ ...periodo, anio: e.target.value })} /></label>
        <button className={secondary} onClick={previsualizar}>Calcular / previsualizar</button>
        <button className={primary} onClick={liquidar} disabled={previa.length === 0}>Liquidar planilla</button>
      </div>
      {previa.length > 0 && (
        <Tabla cabeceras={['Empleado', 'Cargo', 'Salario base', 'Días prog.', 'Faltas', 'Atraso (min)', 'Descuentos', 'Bono (Bs)', 'Total estimado', 'Estado']} vacio={false}>
          {previa.map((p) => (
            <tr key={p.id_contrato_laboral} className="border-b border-gray-800">
              <td className="p-2">{p.empleado_nombre}</td><td className="p-2">{p.cargo}</td><td className="p-2">{p.salario_base}</td>
              <td className="p-2">{p.dias_programados}</td><td className="p-2">{p.faltas}</td><td className="p-2">{p.minutos_atraso}</td>
              <td className="p-2 text-red-400">{p.descuentos}</td>
              <td className="p-2"><input type="number" min="0" step="0.01" className={`${input} w-24`} disabled={p.ya_liquidado} value={bonos[String(p.id_contrato_laboral)] || ''} onChange={(e) => setBonos({ ...bonos, [String(p.id_contrato_laboral)]: e.target.value })} /></td>
              <td className="p-2 font-bold">{(Number(p.total_estimado) + Number(bonos[String(p.id_contrato_laboral)] || 0)).toFixed(2)}</td>
              <td className="p-2">{p.ya_liquidado ? <span className="text-gray-400">Ya liquidado</span> : <span className="text-yellow-400">Pendiente</span>}</td>
            </tr>
          ))}
        </Tabla>
      )}
      <h3 className="font-bold text-yellow-400">Pagos registrados del periodo — Total: Bs {totalPlanilla.toFixed(2)}</h3>
      <Tabla cabeceras={['Empleado', 'Cargo', 'Periodo', 'Base', 'Bonos', 'Descuentos', 'Total pagado', 'Fecha', '']} vacio={pagos.length === 0}>
        {pagos.map((p) => (
          <tr key={p.id_pago_planilla} className="border-b border-gray-800">
            <td className="p-2">{p.empleado_nombre}</td><td className="p-2">{p.cargo}</td><td className="p-2">{p.periodo_mes}/{p.periodo_anio}</td>
            <td className="p-2">{p.salario_base}</td><td className="p-2">{p.bonos}</td><td className="p-2">{p.descuentos}</td>
            <td className="p-2 font-bold text-green-400">{p.total_pagado}</td><td className="p-2">{p.fecha_pagada}</td>
            <td className="p-2"><button className={peligro} onClick={() => anular(p)}>Anular</button></td>
          </tr>
        ))}
      </Tabla>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Vista del personal (Recepcionista / Entrenador): Mi asistencia
// ---------------------------------------------------------------------------
function MiAsistencia({ avisar }: { avisar: (ok: string, err?: string) => void }) {
  const [datos, setDatos] = useState<{ siguiente_evento: string | null; tiene_contrato: boolean; marcaciones: Marcacion[] }>({ siguiente_evento: null, tiene_contrato: false, marcaciones: [] });
  const [horario, setHorario] = useState<Horario[]>([]);
  const [pagos, setPagos] = useState<Pago[]>([]);

  const cargar = useCallback(async () => {
    try {
      const [m, h, p] = await Promise.all([api.get('marcaciones-personal/mis-marcaciones/'), api.get<Horario[]>('horarios-laborales/mi-horario/'), api.get<Pago[]>('planilla/mis-pagos/')]);
      setDatos(m.data); setHorario(h.data); setPagos(p.data);
    } catch (err) { avisar('', errorTexto(err)); }
  }, [avisar]);
  useEffect(() => { void cargar(); }, [cargar]);

  const marcar = async () => {
    try { const r = await api.post('marcaciones-personal/marcar/'); avisar(`${r.data.tipo_evento} registrada a las ${new Date(r.data.fecha_hora).toLocaleTimeString('es-BO')} — ${r.data.estado}${r.data.minutos_atraso ? ` (${r.data.minutos_atraso} min)` : ''}.`); await cargar(); }
    catch (err) { avisar('', errorTexto(err)); }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded border border-gray-700 bg-gray-900 p-5">
        {datos.tiene_contrato ? (
          <button className={`${primary} w-full py-6 text-xl`} onClick={marcar}>MARCAR {datos.siguiente_evento}</button>
        ) : (
          <p className="text-yellow-300">No tiene un contrato laboral activo. Consulte con administración.</p>
        )}
        <h3 className="mt-5 mb-2 font-bold text-yellow-400">Mi horario</h3>
        <Tabla cabeceras={['Día', 'Turno', 'Horario', 'Tolerancia']} vacio={horario.length === 0}>
          {horario.map((h) => <tr key={h.id} className="border-b border-gray-800"><td className="p-2">{h.dia_semana}</td><td className="p-2">{h.turno_nombre}</td><td className="p-2">{h.hora_inicio.slice(0, 5)} - {h.hora_fin.slice(0, 5)}</td><td className="p-2">{h.tolerancia_minutos} min</td></tr>)}
        </Tabla>
      </div>
      <div className="grid content-start gap-3">
        <h3 className="font-bold text-yellow-400">Mis marcaciones</h3>
        <Tabla cabeceras={['Fecha y hora', 'Evento', 'Estado']} vacio={datos.marcaciones.length === 0}>
          {datos.marcaciones.map((m) => <tr key={m.id_marcacion_personal} className="border-b border-gray-800"><td className="p-2">{fechaHora(m.fecha_hora)}</td><td className="p-2">{m.tipo_evento}</td><td className={`p-2 ${m.estado === 'Atraso' ? 'text-red-400' : 'text-green-400'}`}>{m.estado}{m.minutos_atraso ? ` (${m.minutos_atraso} min)` : ''}</td></tr>)}
        </Tabla>
        <h3 className="font-bold text-yellow-400">Mis boletas de pago</h3>
        <Tabla cabeceras={['Periodo', 'Base', 'Bonos', 'Descuentos', 'Total']} vacio={pagos.length === 0}>
          {pagos.map((p) => <tr key={p.id_pago_planilla} className="border-b border-gray-800"><td className="p-2">{p.periodo_mes}/{p.periodo_anio}</td><td className="p-2">{p.salario_base}</td><td className="p-2">{p.bonos}</td><td className="p-2">{p.descuentos}</td><td className="p-2 font-bold">{p.total_pagado}</td></tr>)}
        </Tabla>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
export default function RecursosHumanosScreen({ onVolver, esAdministrador }: Props) {
  const pestanas = esAdministrador
    ? [['contratos', 'Contratos laborales'], ['horarios', 'Turnos y horarios'], ['asistencia', 'Control de asistencia'], ['planilla', 'Planilla de pagos'], ['mia', 'Mi asistencia']]
    : [['mia', 'Mi asistencia']];
  const [tab, setTab] = useState(pestanas[0][0]);
  const [mensaje, setMensaje] = useState('');
  const [error, setError] = useState('');
  const avisar = useCallback((ok: string, err?: string) => { setMensaje(ok); setError(err || ''); }, []);

  return (
    <section className="mx-auto w-full max-w-7xl">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-yellow-400 sm:text-3xl">RECURSOS HUMANOS</h1>
          <p className="mt-1 text-sm text-gray-400">Contratos laborales, turnos, asistencia del personal y planilla de sueldos.</p>
        </div>
        <button type="button" onClick={onVolver} className={secondary}>Volver</button>
      </header>
      <nav className="mb-4 flex flex-wrap gap-2">
        {pestanas.map(([k, t]) => <button key={k} onClick={() => { setTab(k); avisar(''); }} className={tab === k ? primary : secondary}>{t}</button>)}
      </nav>
      {mensaje && <div role="status" className="mb-3 rounded border border-green-700 bg-green-950/50 p-3 text-green-300">{mensaje}</div>}
      {error && <div role="alert" className="mb-3 rounded border border-red-700 bg-red-950/50 p-3 text-red-300">{error}</div>}
      {tab === 'contratos' && <Contratos avisar={avisar} />}
      {tab === 'horarios' && <TurnosHorarios avisar={avisar} />}
      {tab === 'asistencia' && <ControlAsistencia avisar={avisar} />}
      {tab === 'planilla' && <Planilla avisar={avisar} />}
      {tab === 'mia' && <MiAsistencia avisar={avisar} />}
    </section>
  );
}
