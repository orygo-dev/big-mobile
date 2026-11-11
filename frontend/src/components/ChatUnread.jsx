import { useContext, useEffect, useRef, useState } from 'react';
import {AdminInboxContext} from '@/context/AdminInboxContext';
import api from '@/lib/api';
import { toast } from 'sonner';

export default function ChatUnread() {
  const shared = useContext(AdminInboxContext);
  const hasShared = shared !== null;
  const [count, setCount] = useState(0);
  const previous = useRef(null);
  useEffect(() => {
    if (hasShared) return;
    let alive = true;
    const refresh = async () => {
      if (document.hidden) return;
      try { const { data } = await api.get('/chat/unread'); if (alive) { if (previous.current !== null && data.count > previous.current) toast.info('Ada pesan chat baru. Buka menu Chat untuk membaca.', { id: 'chat-new-message' }); previous.current = data.count; setCount(data.count); } } catch { /* Page shows actionable network errors. */ }
    };
    refresh(); const timer = setInterval(refresh, 15000);
    window.addEventListener('big-mobile-chat-read', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => { alive = false; clearInterval(timer); window.removeEventListener('big-mobile-chat-read', refresh); document.removeEventListener('visibilitychange', refresh); };
  }, [hasShared]);
  const unread = shared?.chat ?? count;
  return unread > 0 ? <span aria-label={`${unread} pesan belum dibaca`} className="rounded-full bg-orange-500 px-1.5 text-[10px] font-bold text-white">{unread > 99 ? '99+' : unread}</span> : null;
}
