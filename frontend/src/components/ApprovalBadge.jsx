import {useContext,useEffect,useState} from 'react';
import {AdminInboxContext} from '@/context/AdminInboxContext';
import api from '@/lib/api';

export default function ApprovalBadge(){
  const shared=useContext(AdminInboxContext),hasShared=shared!==null;
  const [count,setCount]=useState(0);
  useEffect(()=>{
    if(hasShared)return;
    let active=true;
    const refresh=()=>{if(!document.hidden)api.get('/approvals/pending-count').then(({data})=>{if(active)setCount(data.count);}).catch(()=>{});};
    refresh();const timer=setInterval(refresh,15000);
    window.addEventListener('big-mobile-approval-changed',refresh);document.addEventListener('visibilitychange',refresh);
    return ()=>{active=false;clearInterval(timer);window.removeEventListener('big-mobile-approval-changed',refresh);document.removeEventListener('visibilitychange',refresh);};
  },[hasShared]);
  const pending=shared?.approvals??count;
  return pending>0?<span className="ml-auto rounded-full bg-orange-500 px-2 py-0.5 text-xs font-bold text-white" aria-label={`${pending} penugasan menunggu approval`} data-testid="approval-pending-count">{pending}</span>:null;
}
