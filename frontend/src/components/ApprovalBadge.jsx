import {useEffect,useState} from 'react';
import api from '@/lib/api';

export default function ApprovalBadge(){
  const [count,setCount]=useState(0);
  useEffect(()=>{
    let active=true;
    const refresh=()=>{if(!document.hidden)api.get('/approvals/pending-count').then(({data})=>{if(active)setCount(data.count);}).catch(()=>{});};
    refresh();const timer=setInterval(refresh,15000);
    window.addEventListener('big-mobile-approval-changed',refresh);document.addEventListener('visibilitychange',refresh);
    return ()=>{active=false;clearInterval(timer);window.removeEventListener('big-mobile-approval-changed',refresh);document.removeEventListener('visibilitychange',refresh);};
  },[]);
  return count>0?<span className="ml-auto rounded-full bg-orange-500 px-2 py-0.5 text-xs font-bold text-white" aria-label={`${count} penugasan menunggu approval`} data-testid="approval-pending-count">{count}</span>:null;
}
