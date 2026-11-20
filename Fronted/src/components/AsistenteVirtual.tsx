// Funcionalidad adicional: asistente virtual "PorkyBot" con comandos de voz.
// - Chat flotante que consulta /api/chatbot/ (respuestas con datos reales).
// - Micrófono (Web Speech API, Chrome/Edge): reconoce la voz en español.
// - Comandos de voz que se ejecutan en el navegador sin pasar por el servidor:
//     "ir a ventas", "abrir reportes", "validar acceso 8765432",
//     "marcar mi ingreso", "marcar asistencia", "cerrar sesión", "leer en voz alta / silencio".
// - Lee las respuestas en voz alta (speechSynthesis) si el usuario lo activa.
import React, { useEffect, useRef, useState } from 'react';
import api from '../services/api';
import { limpiarSesion } from '../services/sesion';

type Mensaje = { de: 'bot' | 'yo'; texto: string };
type Props = { onIr: (pantalla: string) => void };

const PANTALLAS: [RegExp, string][] = [
  [/\b(dashboard|tablero|estad[ií]sticas?)\b/, 'dashboard'],
  [/\b(ventas?|punto de venta|pos)\b/, 'ventas'],
  [/\b(caja|arqueo)\b/, 'caja'],
  [/\b(reportes?)\b/, 'reportes'],
  [/\b(acceso|control de acceso)\b/, 'acceso'],
  [/\b(personal|recursos humanos|planilla|asistencia)\b/, 'rrhh'],
  [/\b(kardex)\b/, 'kardex'],
  [/\b(alertas?)\b/, 'alertas'],
  [/\b(productos?|inventario)\b/, 'productos'],
  [/\b(entrenamiento|rutinas?|ejercicios?)\b/, 'entrenamiento'],
  [/\b(membres[ií]as?|contratos? de membres[ií]a|renovar)\b/, 'contrato'],
  [/\b(nuevo socio|registrar socio)\b/, 'registrar-socio'],
  [/\b(usuarios)\b/, 'usuarios'],
  [/\b(bit[aá]cora)\b/, 'bitacora'],
  [/\b(inicio|principal)\b/, 'inicio'],
];

const normalizar = (t: string) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[¿?¡!.,]/g, '').trim();

export default function AsistenteVirtual({ onIr }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [mensajes, setMensajes] = useState<Mensaje[]>([{ de: 'bot', texto: '¡Hola! Soy PorkyBot. Pregúntame o usa el micrófono para darme una orden de voz.' }]);
  const [sugerencias, setSugerencias] = useState<string[]>(['¿Qué puedes hacer?']);
  const [texto, setTexto] = useState('');
  const [escuchando, setEscuchando] = useState(false);
  const [hablar, setHablar] = useState(() => localStorage.getItem('porkybot_voz') === '1');
  const [pensando, setPensando] = useState(false);
  const reconocedor = useRef<any>(null);
  const fin = useRef<HTMLDivElement>(null);

  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  const vozDisponible = Boolean(SR);

  useEffect(() => { fin.current?.scrollIntoView({ behavior: 'smooth' }); }, [mensajes, abierto]);
  useEffect(() => { try { localStorage.setItem('porkybot_voz', hablar ? '1' : '0'); } catch { /* sin storage */ } }, [hablar]);

  const decir = (t: string) => {
    if (!hablar || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(t.replace(/[•]/g, ''));
    u.lang = 'es-ES';
    window.speechSynthesis.speak(u);
  };
  const bot = (t: string) => { setMensajes((m) => [...m, { de: 'bot', texto: t }]); decir(t); };

  // Comandos que se resuelven en el navegador (respuesta inmediata).
  const comandoLocal = (original: string): boolean => {
    const t = normalizar(original);
    if (/\b(cerrar sesion|salir del sistema)\b/.test(t)) {
      bot('Cerrando sesión. ¡Hasta pronto!');
      setTimeout(() => { limpiarSesion(); window.location.reload(); }, 900);
      return true;
    }
    if (/\b(silencio|no hables|deja de hablar)\b/.test(t)) { setHablar(false); window.speechSynthesis?.cancel(); setMensajes((m) => [...m, { de: 'bot', texto: 'Listo, ya no leeré las respuestas.' }]); return true; }
    if (/\b(habla|leer en voz alta|lee en voz alta|activar voz)\b/.test(t)) { setHablar(true); setMensajes((m) => [...m, { de: 'bot', texto: 'Voz activada: leeré las respuestas.' }]); return true; }
    const acceso = t.match(/validar (?:el )?acceso(?: de| del socio| al socio)?\s+([a-z0-9 ]+)/);
    if (acceso) {
      const termino = acceso[1].replace(/\s+/g, '');
      try { sessionStorage.setItem('acceso_termino_voz', termino); } catch { /* ignore */ }
      bot(`Validando el acceso de ${termino}…`);
      onIr('acceso');
      window.dispatchEvent(new CustomEvent('porky-acceso-voz', { detail: termino }));
      return true;
    }
    if (/\bmarcar (mi )?ingreso\b/.test(t)) {
      try { sessionStorage.setItem('acceso_termino_voz', '__yo__'); } catch { /* ignore */ }
      bot('Marcando tu ingreso…'); onIr('acceso');
      window.dispatchEvent(new CustomEvent('porky-acceso-voz', { detail: '__yo__' }));
      return true;
    }
    if (/\bmarcar (mi )?(asistencia|entrada|salida)\b/.test(t)) {
      api.post('marcaciones-personal/marcar/')
        .then((r) => bot(`${r.data.tipo_evento} registrada: ${r.data.estado}${r.data.minutos_atraso ? ` (${r.data.minutos_atraso} min de atraso)` : ''}.`))
        .catch((e) => bot(e?.response?.data?.detail || 'No se pudo registrar la marcación.'));
      return true;
    }
    if (/\b(ir a|ve a|abrir|abre|llevame a|mostrar|muestrame)\b/.test(t)) {
      const destino = PANTALLAS.find(([re]) => re.test(t));
      if (destino) { bot(`Abriendo ${destino[1].replace('-', ' ')}.`); onIr(destino[1]); return true; }
    }
    return false;
  };

  const enviar = async (contenido: string) => {
    const limpio = contenido.trim();
    if (!limpio || pensando) return;
    setMensajes((m) => [...m, { de: 'yo', texto: limpio }]);
    setTexto('');
    if (comandoLocal(limpio)) return;
    setPensando(true);
    try {
      const r = await api.post('chatbot/', { mensaje: limpio });
      bot(r.data.respuesta);
      setSugerencias(r.data.sugerencias || []);
      if (r.data.accion?.tipo === 'navegar') onIr(r.data.accion.pantalla);
    } catch {
      bot('No pude conectarme con el servidor. Inténtalo de nuevo.');
    } finally { setPensando(false); }
  };

  const microfono = () => {
    if (!vozDisponible) { bot('Tu navegador no permite reconocimiento de voz. Usa Google Chrome o Microsoft Edge.'); return; }
    if (escuchando) { reconocedor.current?.stop(); return; }
    const rec = new SR();
    rec.lang = 'es-BO';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e: any) => { const dicho = e.results[0][0].transcript; void enviar(dicho); };
    rec.onerror = (e: any) => { if (e.error === 'not-allowed') bot('Permite el uso del micrófono en el navegador para darme órdenes de voz.'); };
    rec.onend = () => setEscuchando(false);
    reconocedor.current = rec;
    setEscuchando(true);
    setAbierto(true);
    rec.start();
  };

  return (
    <>
      {/* Botón flotante de voz directa */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
        {abierto && (
          <div className="flex h-[30rem] w-[22rem] max-w-[calc(100vw-2rem)] flex-col rounded-xl border border-gray-700 bg-gray-950 shadow-2xl">
            <div className="flex items-center justify-between rounded-t-xl bg-yellow-500 px-3 py-2 text-black">
              <b>PorkyBot · Asistente</b>
              <div className="flex items-center gap-2">
                <button onClick={() => setHablar(!hablar)} title={hablar ? 'Desactivar voz' : 'Leer respuestas en voz alta'} className="rounded px-1 hover:bg-yellow-400">{hablar ? 'Voz activada' : 'Voz apagada'}</button>
                <button onClick={() => setAbierto(false)} className="rounded px-1 font-bold hover:bg-yellow-400" aria-label="Cerrar">✕</button>
              </div>
            </div>
            <div className="flex-1 space-y-2 overflow-y-auto p-3 text-sm">
              {mensajes.map((m, i) => (
                <div key={i} className={`max-w-[85%] whitespace-pre-line rounded-lg px-3 py-2 ${m.de === 'yo' ? 'ml-auto bg-yellow-500 text-black' : 'bg-gray-800 text-white'}`}>{m.texto}</div>
              ))}
              {pensando && <div className="w-16 rounded-lg bg-gray-800 px-3 py-2 text-gray-400">…</div>}
              <div ref={fin} />
            </div>
            {sugerencias.length > 0 && (
              <div className="flex flex-wrap gap-1 border-t border-gray-800 p-2">
                {sugerencias.map((s) => <button key={s} onClick={() => enviar(s)} className="rounded-full border border-gray-600 px-2 py-0.5 text-xs hover:bg-gray-800">{s}</button>)}
              </div>
            )}
            <form onSubmit={(e) => { e.preventDefault(); void enviar(texto); }} className="flex gap-2 border-t border-gray-800 p-2">
              <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={escuchando ? 'Escuchando…' : 'Escribe o usa el micrófono'}
                className="flex-1 rounded border border-gray-700 bg-gray-800 px-2 py-1.5 text-sm text-white outline-none focus:border-yellow-500" />
              <button type="button" onClick={microfono} title="Hablar" className={`rounded px-3 ${escuchando ? 'animate-pulse bg-red-600' : 'bg-gray-700 hover:bg-gray-600'}`}>Hablar</button>
              <button type="submit" className="rounded bg-yellow-500 px-3 font-bold text-black">Enviar</button>
            </form>
          </div>
        )}
        <div className="flex gap-2">
          {vozDisponible && (
            <button onClick={microfono} title="Comando de voz" className={`rounded px-3 py-2 text-sm font-semibold shadow-lg ${escuchando ? 'animate-pulse bg-red-600 text-white' : 'bg-gray-800 text-gray-100 hover:bg-gray-700'}`}>{escuchando ? 'Escuchando...' : 'Comando de voz'}</button>
          )}
          <button onClick={() => setAbierto(!abierto)} title="Asistente PorkyBot" className="rounded bg-yellow-500 px-3 py-2 text-sm font-semibold text-black shadow-lg hover:bg-yellow-400">PorkyBot</button>
        </div>
      </div>
    </>
  );
}
