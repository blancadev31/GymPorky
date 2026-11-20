// Funcionalidad adicional: campana de notificaciones automáticas
// (stock bajo / agotado y recordatorios de vencimiento de membresía).
import React, { useCallback, useEffect, useRef, useState } from 'react';
import api from '../services/api';

type Notificacion = {
  id_notificacion: number;
  tipo: string;
  titulo: string;
  mensaje: string;
  pantalla: string | null;
  leida: boolean;
  fecha_creacion: string;
};

const ICONO: Record<string, string> = { STOCK_BAJO: 'Stock', STOCK_AGOTADO: 'Agotado', VENCIMIENTO: 'Vence', SISTEMA: 'Aviso' };

export default function NotificacionesCampana({ onIr }: { onIr: (pantalla: string) => void }) {
  const [abierta, setAbierta] = useState(false);
  const [total, setTotal] = useState(0);
  const [lista, setLista] = useState<Notificacion[]>([]);
  const caja = useRef<HTMLDivElement>(null);

  const contar = useCallback(async () => {
    try { const r = await api.get('notificaciones/no-leidas/'); setTotal(r.data.total); } catch { /* sin sesión */ }
  }, []);

  useEffect(() => {
    void contar();
    const id = window.setInterval(contar, 60000); // revisa cada minuto
    return () => window.clearInterval(id);
  }, [contar]);

  useEffect(() => {
    const cerrar = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) setAbierta(false); };
    document.addEventListener('mousedown', cerrar);
    return () => document.removeEventListener('mousedown', cerrar);
  }, []);

  const abrir = async () => {
    const nuevo = !abierta;
    setAbierta(nuevo);
    if (nuevo) {
      try { const r = await api.get<Notificacion[]>('notificaciones/'); setLista(r.data); } catch { setLista([]); }
    }
  };
  const seleccionar = async (n: Notificacion) => {
    if (!n.leida) {
      try { await api.post(`notificaciones/${n.id_notificacion}/leer/`); } catch { /* ignore */ }
      setLista((l) => l.map((x) => (x.id_notificacion === n.id_notificacion ? { ...x, leida: true } : x)));
      setTotal((t) => Math.max(0, t - 1));
    }
    if (n.pantalla) { onIr(n.pantalla); setAbierta(false); }
  };
  const leerTodas = async () => {
    try { await api.post('notificaciones/leer-todas/'); } catch { /* ignore */ }
    setLista((l) => l.map((x) => ({ ...x, leida: true })));
    setTotal(0);
  };

  return (
    <div className="relative" ref={caja}>
      <button onClick={abrir} className="relative rounded bg-gray-800 px-3 py-2 text-white hover:bg-gray-700" aria-label="Notificaciones">
        Notificaciones
        {total > 0 && <span className="absolute -right-1 -top-1 rounded-full bg-red-600 px-1.5 text-xs font-bold">{total > 99 ? '99+' : total}</span>}
      </button>
      {abierta && (
        <div className="absolute right-0 z-40 mt-1 w-[22rem] max-w-[calc(100vw-1rem)] rounded border border-gray-700 bg-gray-900 shadow-xl">
          <div className="flex items-center justify-between border-b border-gray-700 p-3">
            <b>Notificaciones</b>
            {lista.some((n) => !n.leida) && <button onClick={leerTodas} className="text-xs text-yellow-400 hover:underline">Marcar todas como leídas</button>}
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {lista.length === 0 && <p className="p-4 text-center text-sm text-gray-400">No tienes notificaciones.</p>}
            {lista.map((n) => (
              <button key={n.id_notificacion} onClick={() => seleccionar(n)}
                className={`block w-full border-b border-gray-800 p-3 text-left hover:bg-gray-800 ${n.leida ? 'opacity-60' : ''}`}>
                <p className="text-sm font-bold">{ICONO[n.tipo] || '•'} {n.titulo}</p>
                <p className="mt-1 text-xs text-gray-300">{n.mensaje}</p>
                <p className="mt-1 text-[11px] text-gray-500">{new Date(n.fecha_creacion).toLocaleString('es-BO')}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
