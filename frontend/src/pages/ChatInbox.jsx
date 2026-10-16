import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageCircle, ChevronRight, Loader2, Plus } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import api, { errMsg } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

export default function ChatInbox() {
  const { user } = useAuth();
  const base = user.role === 'admin' ? '/admin' : '/app';
  const [items, setItems] = useState([]), [next, setNext] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState('');
  const loadedPage = useRef(1);
  const [newOpen, setNewOpen] = useState(false), [choices, setChoices] = useState([]), [choiceNext, setChoiceNext] = useState(null), [choiceLoading, setChoiceLoading] = useState(false), [choiceError, setChoiceError] = useState('');
  async function loadChoices(page = 1) {
    setChoiceLoading(true); setChoiceError('');
    try {
      const {data} = await api.get('/chat', {params: {page, active_only: true}});
      setChoices(previous => page === 1 ? data.items : [...previous, ...data.items.filter(item => !previous.some(old => old.assignment_id === item.assignment_id))]);
      setChoiceNext(data.next_page);
    } catch (e) { setChoiceError(errMsg(e)); }
    finally { setChoiceLoading(false); }
  }
  async function load(page = 1) {
    try {
      const { data } = await api.get('/chat', { params: { page } });
      loadedPage.current = page;
      setItems(previous => page === 1 ? data.items : [...previous, ...data.items.filter(item => !previous.some(old => old.assignment_id === item.assignment_id))]);
      setNext(data.next_page); setError('');
    } catch (e) { setError(errMsg(e)); } finally { setLoading(false); }
  }
  useEffect(() => {
    let stopped = false;
    const refresh = () => { if (!stopped && !document.hidden && loadedPage.current === 1) load(); };
    refresh(); const timer = setInterval(refresh, 15000);
    return () => { stopped = true; clearInterval(timer); };
  }, []);
  return <div className="p-4 space-y-4">
    <div><h1 className="font-heading text-2xl font-bold text-slate-900">Chat penugasan</h1><p className="text-sm text-slate-500 mt-1">Pilih penugasan aktif di bawah untuk mulai chat dengan {user.role === 'admin' ? 'petugas' : 'admin'}. Riwayat percakapan tetap tersedia setelah tugas ditutup.</p></div>
    <button onClick={() => {setNewOpen(true); setChoices([]); setChoiceNext(null); loadChoices();}} className="brand-action rounded-xl px-4 py-3 flex items-center gap-2 font-semibold" data-testid="chat-new-message"><Plus size={18} />Pesan Baru</button>
    <Dialog open={newOpen} onOpenChange={setNewOpen}><DialogContent className="max-w-lg max-h-[85dvh] overflow-y-auto">
      <DialogHeader><DialogTitle>Pesan Baru</DialogTitle><DialogDescription>{user.role === 'admin' ? 'Pilih petugas melalui penugasan aktifnya.' : 'Pilih penugasan untuk mengirim pesan kepada admin.'} Pesan dan lampiran tersimpan pada penugasan yang dipilih.</DialogDescription></DialogHeader>
      {choiceError && <div role="alert" className="text-sm text-rose-600">{choiceError}<button onClick={() => loadChoices()} className="ml-2 text-blue-600">Coba lagi</button></div>}
      {!choiceLoading && !choiceError && !choices.length && <p className="text-sm text-slate-600">{user.role === 'admin' ? 'Belum ada penugasan aktif. Buat penugasan untuk petugas terlebih dahulu.' : 'Belum ada penugasan aktif untuk Anda. Hubungi admin untuk mendapatkan penugasan.'}</p>}
      {choices.map(item => <Link key={item.assignment_id} to={`${base}/chat/${item.assignment_id}`} onClick={() => setNewOpen(false)} className="rounded-xl border border-blue-100 p-3 hover:bg-blue-50 block" data-testid={`chat-start-${item.assignment_id}`}><p className="font-semibold text-sm">{user.role === 'admin' ? item.officer_name : 'Admin'} · {item.account_name || item.number}</p><p className="text-xs text-slate-500 mt-1">{[item.number, item.contract_number, item.license_plate].filter(Boolean).join(' · ')}</p><p className="text-xs text-blue-600 mt-2">Buka percakapan →</p></Link>)}
      {choiceLoading && <Loader2 className="animate-spin mx-auto text-blue-600" aria-label="Memuat penugasan" />}
      {choiceNext && <button disabled={choiceLoading} onClick={() => loadChoices(choiceNext)} className="text-sm text-blue-600">Muat penugasan lainnya</button>}
    </DialogContent></Dialog>
    <button onClick={() => load()} className="text-sm font-semibold text-blue-600">Perbarui kotak masuk</button>
    {error && <div role="alert" className="rounded-xl bg-amber-50 p-3 text-sm">{error}<button onClick={() => load()} className="ml-3 text-blue-600">Coba lagi</button></div>}
    {loading ? <Loader2 className="animate-spin text-blue-600 mx-auto" /> : !items.length && !error ? <div className="brand-panel rounded-2xl p-8 text-center text-slate-500"><MessageCircle className="mx-auto mb-3 text-blue-500" />Belum ada penugasan aktif atau riwayat chat.<p className="text-sm mt-2">{user.role === 'admin' ? 'Buat penugasan untuk petugas terlebih dahulu melalui menu Penugasan.' : 'Chat tersedia setelah admin memberikan penugasan kepada Anda.'}</p></div> : <div className="space-y-3">{items.map(item => <Link key={item.assignment_id} to={`${base}/chat/${item.assignment_id}`} className="brand-panel rounded-2xl p-4 border border-blue-100 flex items-center gap-3" data-testid={`chat-inbox-${item.assignment_id}`}>
      <div className="rounded-2xl bg-blue-50 p-3 text-blue-600"><MessageCircle size={22} /></div><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-900 truncate">{item.account_name || item.number}</p><p className="text-xs text-slate-500 truncate">{item.officer_name} · {item.number} · {item.status}</p><p className="text-sm text-slate-600 truncate mt-1">{item.last_message}</p></div>
      {item.unread > 0 && <span className="rounded-full bg-orange-500 text-white text-xs px-2 py-1">{item.unread}</span>}<ChevronRight size={18} className="text-slate-400" />
    </Link>)}</div>}
    {next && <button onClick={() => load(next)} className="text-blue-600 text-sm">Muat percakapan lainnya</button>}
  </div>;
}
