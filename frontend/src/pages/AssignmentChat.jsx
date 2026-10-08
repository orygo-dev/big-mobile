import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Camera, FileText, Loader2, MapPin, Paperclip, Send, X } from 'lucide-react';
import api, { errMsg, fileUrl } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

export function mergeMessages(previous, incoming) {
  const records = new Map(previous.map(item => [item.id, item]));
  incoming.forEach(item => records.set(item.id, item));
  return [...records.values()].sort((a, b) => a.sequence - b.sequence);
}

export default function AssignmentChat() {
  const { assignmentId } = useParams(), { user } = useAuth();
  const base = user.role === 'admin' ? '/admin' : '/app';
  const [thread, setThread] = useState(null), [messages, setMessages] = useState([]), [older, setOlder] = useState(false);
  const [text, setText] = useState(''), [files, setFiles] = useState([]), [location, setLocation] = useState(null);
  const [error, setError] = useState(''), [sendError, setSendError] = useState(''), [busy, setBusy] = useState(false), [gpsBusy, setGpsBusy] = useState(false);
  const records = useRef([]), retry = useRef(null), bottom = useRef(null), pane = useRef(null), mounted = useRef(true), sending = useRef(false), acknowledged = useRef(0);
  const path = `/chat/${assignmentId}`;
  const synced = useRef(0), currentPath = useRef(path);
  const follow = useRef(true);
  currentPath.current = path;
  const markRead = useCallback(async sequence => {
    if (!sequence || document.hidden || sequence <= acknowledged.current) return;
    const bounds = bottom.current?.getBoundingClientRect();
    const viewport = pane.current?.getBoundingClientRect();
    if (!bounds || !viewport || bounds.top > Math.min(window.innerHeight, viewport.bottom) + 24 || bounds.bottom < Math.max(0, viewport.top)) return;
    try { await api.post(`${path}/read`, { sequence }); acknowledged.current = sequence; window.dispatchEvent(new Event('big-mobile-chat-read')); } catch { /* Retry on the next visible poll. */ }
  }, [path]);
  const refresh = useCallback(async (initial = false) => {
    if (document.hidden && !initial) return;
    try {
      let after = initial ? 0 : synced.current;
      let more;
      do {
        const { data } = await api.get(path, { params: { after, limit: 50 } });
        if (!mounted.current || currentPath.current !== path) return;
        const merged = initial ? data.messages : mergeMessages(records.current, data.messages);
        records.current = merged; setMessages(merged); setThread(data.assignment); setError('');
        synced.current = Math.max(synced.current, data.messages.at(-1)?.sequence || 0);
        if (initial || !after) setOlder(data.has_more);
        more = !initial && after > 0 && data.has_more;
        after = synced.current;
        initial = false;
      } while (more);
      // Only acknowledge a sequence already added to the visible conversation.
      requestAnimationFrame(() => { if (mounted.current) markRead(records.current.at(-1)?.sequence); });
    } catch (e) { if (mounted.current) setError(errMsg(e)); }
  }, [path, markRead]);
  useEffect(() => {
    mounted.current = true; records.current = []; retry.current = null; acknowledged.current = 0; synced.current = 0;
    setMessages([]); setThread(null); setText(''); setFiles([]); setLocation(null); setSendError('');
    refresh(true); const timer = setInterval(() => refresh(), 5000);
    const visible = () => refresh(); document.addEventListener('visibilitychange', visible);
    const scroll = () => { const bounds = bottom.current?.getBoundingClientRect(), viewport = pane.current?.getBoundingClientRect(); follow.current = !!bounds && !!viewport && bounds.top <= viewport.bottom + 100 && bounds.bottom >= viewport.top; markRead(records.current.at(-1)?.sequence); };
    document.addEventListener('scroll', scroll, true);
    return () => { mounted.current = false; clearInterval(timer); document.removeEventListener('visibilitychange', visible); document.removeEventListener('scroll', scroll, true); };
  }, [refresh]);
  useEffect(() => { if (follow.current) bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [messages.at(-1)?.id]);
  const edit = () => { retry.current = null; setSendError(''); };
  async function loadOlder() {
    try { const { data } = await api.get(path, { params: { before: records.current[0]?.sequence, limit: 50 } }); records.current = mergeMessages(records.current, data.messages); setMessages(records.current); setOlder(data.has_more); } catch (e) { setError(errMsg(e)); }
  }
  function selectFiles(event) {
    const selected = [...event.target.files]; event.target.value = '';
    if (files.length + selected.length > 4) { setSendError('Maksimal 4 lampiran per pesan.'); return; }
    if (selected.some(file => file.size > 10 * 1024 * 1024 || !file.size)) { setSendError('Lampiran maksimal 10 MB dan tidak boleh kosong; foto maksimal 8 MB.'); return; }
    edit(); setFiles(previous => [...previous, ...selected]);
  }
  function getLocation() {
    if (!navigator.geolocation) { setSendError('Perangkat tidak mendukung lokasi.'); return; }
    setGpsBusy(true); setSendError('');
    navigator.geolocation.getCurrentPosition(position => {
      if (!mounted.current) return;
      follow.current = true;
      edit(); setLocation({ latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy }); setGpsBusy(false);
    }, () => { if (mounted.current) { setGpsBusy(false); setSendError('Lokasi belum tersedia. Aktifkan izin lokasi lalu coba lagi.'); } }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
  }
  async function send(event) {
    event.preventDefault(); if (sending.current || !thread || thread.read_only || (!text.trim() && !files.length && !location)) return;
    sending.current = true; setBusy(true); setSendError('');
    if (!retry.current) retry.current = { id: crypto.randomUUID(), text, files: [...files], location };
    const pending = retry.current, data = new FormData();
    data.append('client_message_id', pending.id); data.append('text', pending.text);
    if (pending.location) data.append('location', JSON.stringify(pending.location));
    pending.files.forEach(file => data.append('files', file));
    try {
      const { data: message } = await api.post(`${path}/messages`, data, { timeout: 120000 });
      if (!mounted.current) return;
      records.current = mergeMessages(records.current, [message]); setMessages(records.current);
      retry.current = null; setText(''); setFiles([]); setLocation(null); await refresh();
    } catch (e) { if (mounted.current) setSendError(`${errMsg(e)} Pesan dan lampiran tetap tersedia; tekan kirim untuk mencoba lagi.`); }
    finally { sending.current = false; if (mounted.current) setBusy(false); }
  }
  return <div className={`p-4 flex flex-col gap-4 ${user.role === 'admin' ? 'h-[calc(100dvh-6rem)] sm:h-[calc(100dvh-7rem)] lg:h-[calc(100dvh-8rem)]' : 'h-[100dvh]'}`}>
    <div className="brand-panel rounded-2xl border border-blue-100 p-4"><Link to={`${base}/chat`} className="text-sm text-blue-600 flex items-center gap-1 mb-2"><ArrowLeft size={16} />Kotak masuk</Link><h1 className="font-heading text-lg font-bold text-slate-900">{thread?.account_name || 'Chat penugasan'}</h1><p className="text-xs text-slate-500 break-all">{thread?.number || 'Memuat percakapan…'}</p>{thread && <p className="text-xs text-slate-600 mt-1">{[thread.officer_name, thread.contract_number, thread.license_plate].filter(Boolean).join(' · ')}</p>}<p className="text-xs text-slate-500 mt-1">Pesan koordinasi tidak mengubah status tugas atau laporan.</p></div>
    {error && <div role="alert" className="rounded-xl bg-amber-50 text-sm p-3">{error}<button onClick={() => refresh(!thread)} className="ml-2 text-blue-600">Coba lagi</button></div>}
    {!thread && !error && <Loader2 className="mx-auto text-blue-600 animate-spin" />}
    {older && <button onClick={loadOlder} className="text-sm text-blue-600">Muat pesan sebelumnya</button>}
    <div ref={pane} className="space-y-3 flex-1 min-h-0 overflow-y-auto overscroll-contain pr-1" aria-label="Percakapan" data-testid="chat-messages">
      {thread && !messages.length && <p className="text-center text-sm text-slate-500 py-6">Belum ada pesan. Mulai koordinasi di sini.</p>}
      {messages.map(message => { const own = message.sender_id === user.id; return <article key={message.id} className={`rounded-2xl p-3 w-fit max-w-[92%] sm:max-w-[640px] border ${own ? 'ml-auto bg-blue-600 border-blue-600 text-white' : 'mr-auto bg-white border-blue-100 text-slate-800'}`} data-testid={`chat-message-${message.id}`}>
        <p className={`text-xs font-semibold mb-1 ${own ? 'text-blue-100' : 'text-blue-600'}`}>{message.sender_name} · {message.sender_role === 'admin' ? 'Admin' : 'Petugas'}</p>
        {message.text && <p className="whitespace-pre-wrap break-words text-sm">{message.text}</p>}
        {message.attachments.map(attachment => <a key={attachment.id} href={fileUrl(attachment.url)} target="_blank" rel="noopener noreferrer" className="block mt-2 rounded-xl bg-white/15 p-2 border border-current/10" data-testid={`chat-attachment-${attachment.kind}`}>
          {attachment.kind === 'image' && <img src={fileUrl(attachment.url)} alt={attachment.name} loading="lazy" className="max-h-56 w-full object-contain rounded-lg" />}
          <span className="flex items-center gap-2 text-xs mt-1 break-all"><FileText size={14} className="shrink-0" />{attachment.name} · {Math.ceil(attachment.size / 1024)} KB</span>
        </a>)}
        {message.location && <a href={`https://www.google.com/maps?q=${message.location.latitude},${message.location.longitude}`} target="_blank" rel="noopener noreferrer" className="flex items-start gap-2 rounded-xl border border-current/20 p-3 mt-2 text-sm" data-testid="chat-location"><MapPin size={18} className="shrink-0" /><span>Buka lokasi<br /><span className="text-xs">{message.location.latitude.toFixed(6)}, {message.location.longitude.toFixed(6)}{message.location.accuracy != null && ` · ±${Math.round(message.location.accuracy)} m`}</span></span></a>}
        <p className={`text-[10px] text-right mt-2 ${own ? 'text-blue-100' : 'text-slate-400'}`}>{new Date(message.created_at).toLocaleString('id-ID')}</p>
      </article>; })}<div ref={bottom} />
    </div>
    {thread?.read_only ? <p className="rounded-xl bg-slate-100 p-4 text-sm text-slate-600 shrink-0" data-testid="chat-read-only">Tugas sudah ditutup. Riwayat chat dan lampiran tetap dapat dibaca.</p> : thread && <form onSubmit={send} className="brand-panel rounded-2xl border border-blue-200 p-3 space-y-3 shrink-0 max-h-[45dvh] overflow-y-auto" data-testid="chat-composer">
      {sendError && <p role="alert" className="text-sm text-rose-600">{sendError}</p>}
      {files.map((file, index) => <div key={`${index}-${file.name}`} className="flex justify-between gap-2 text-xs bg-blue-50 rounded-lg p-2"><span className="break-all">{file.name}</span><button type="button" disabled={busy} aria-label={`Hapus ${file.name}`} onClick={() => { edit(); setFiles(previous => previous.filter((_, i) => i !== index)); }}><X size={14} /></button></div>)}
      {location && <div className="flex justify-between text-xs bg-orange-50 p-2 rounded-lg" data-testid="chat-location-preview"><span>Lokasi siap dikirim: {location.latitude.toFixed(6)}, {location.longitude.toFixed(6)}</span><button type="button" disabled={busy} aria-label="Hapus lokasi" onClick={() => { edit(); setLocation(null); }}><X size={14} /></button></div>}
      <textarea aria-label="Pesan" data-testid="chat-text" maxLength={4000} rows={3} value={text} disabled={busy} onChange={event => { edit(); setText(event.target.value); }} placeholder="Tulis pesan koordinasi…" className="w-full resize-y rounded-xl border border-slate-200 p-3 text-sm focus:outline-blue-500" />
      <div className="flex items-center gap-3"><label className={`text-blue-600 text-sm flex gap-1 items-center cursor-pointer ${busy ? 'opacity-50' : ''}`}><Paperclip size={18} />File<input type="file" multiple accept=".jpg,.jpeg,.png,.webp,.pdf,.txt,.csv,.docx,.xlsx,.pptx" disabled={busy} onChange={selectFiles} className="sr-only" data-testid="chat-file-input" aria-label="Lampirkan foto atau dokumen" /></label><label className="text-blue-600 cursor-pointer" title="Ambil foto"><Camera size={18} /><input type="file" accept="image/jpeg,image/png" capture="environment" disabled={busy} onChange={selectFiles} className="sr-only" aria-label="Ambil foto" /></label><button type="button" disabled={busy || gpsBusy} onClick={getLocation} className="text-blue-600 text-sm flex gap-1 items-center" data-testid="chat-share-location">{gpsBusy ? <Loader2 size={18} className="animate-spin" /> : <MapPin size={18} />}Lokasi</button><button type="submit" disabled={busy || gpsBusy || (!text.trim() && !files.length && !location)} className="ml-auto brand-action rounded-xl p-3 disabled:opacity-50" aria-label="Kirim pesan" data-testid="chat-send">{busy ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}</button></div>
      <p className="text-[10px] text-slate-500">Maks. 4 lampiran · foto 8 MB · dokumen 10 MB · PDF, TXT, CSV, DOCX, XLSX, PPTX</p>
    </form>}
  </div>;
}
