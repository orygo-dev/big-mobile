import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageCircle, ChevronRight, Loader2 } from 'lucide-react';
import api, { errMsg } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

export default function ChatInbox() {
  const { user } = useAuth();
  const base = user.role === 'admin' ? '/admin' : '/app';
  const [items, setItems] = useState([]), [next, setNext] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState('');
  const loadedPage = useRef(1);
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
    <div><h1 className="font-heading text-2xl font-bold text-slate-900">Chat penugasan</h1><p className="text-sm text-slate-500 mt-1">Koordinasi admin dan petugas. Mulai chat dari halaman penugasan atau detail tugas.</p></div>
    <button onClick={() => load()} className="text-sm font-semibold text-blue-600">Perbarui kotak masuk</button>
    {error && <div role="alert" className="rounded-xl bg-amber-50 p-3 text-sm">{error}<button onClick={() => load()} className="ml-3 text-blue-600">Coba lagi</button></div>}
    {loading ? <Loader2 className="animate-spin text-blue-600 mx-auto" /> : !items.length && !error ? <div className="brand-panel rounded-2xl p-8 text-center text-slate-500"><MessageCircle className="mx-auto mb-3 text-blue-500" />Belum ada percakapan</div> : <div className="space-y-3">{items.map(item => <Link key={item.assignment_id} to={`${base}/chat/${item.assignment_id}`} className="brand-panel rounded-2xl p-4 border border-blue-100 flex items-center gap-3" data-testid={`chat-inbox-${item.assignment_id}`}>
      <div className="rounded-2xl bg-blue-50 p-3 text-blue-600"><MessageCircle size={22} /></div><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-900 truncate">{item.account_name || item.number}</p><p className="text-xs text-slate-500 truncate">{item.officer_name} · {item.number} · {item.status}</p><p className="text-sm text-slate-600 truncate mt-1">{item.last_message}</p></div>
      {item.unread > 0 && <span className="rounded-full bg-orange-500 text-white text-xs px-2 py-1">{item.unread}</span>}<ChevronRight size={18} className="text-slate-400" />
    </Link>)}</div>}
    {next && <button onClick={() => load(next)} className="text-blue-600 text-sm">Muat percakapan lainnya</button>}
  </div>;
}
