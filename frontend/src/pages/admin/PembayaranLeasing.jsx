import {useEffect, useRef, useState} from "react";
import api, {errMsg, fileUrl} from "@/lib/api";
import {formatDateTime} from "@/lib/constants";
import {rupiah} from "@/components/ReportPayment";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription} from "@/components/ui/dialog";
import {Loader2, Wallet} from "lucide-react";
import EmptyState from "@/components/EmptyState";
import {toast} from "sonner";
import {useNavigate, useSearchParams} from "react-router-dom";

export default function PembayaranLeasing() {
  const navigate=useNavigate();
  const [searchParams]=useSearchParams();
  const fromFinance=searchParams.get('from')==='keuangan';
  const [items,setItems]=useState([]),[page,setPage]=useState(1),[next,setNext]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState("");
  const [open,setOpen]=useState(false),[clients,setClients]=useState([]),[clientPage,setClientPage]=useState(1),[moreClients,setMoreClients]=useState(false),[clientsLoading,setClientsLoading]=useState(false),[clientError,setClientError]=useState("");
  const [leasing,setLeasing]=useState(""),[amount,setAmount]=useState(""),[proof,setProof]=useState(null),[busy,setBusy]=useState(false),[formError,setFormError]=useState("");
  const key=useRef(null);
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{
    let active=true;setLoading(true);setError("");
    api.get('/leasing-payments',{params:{page}}).then(({data})=>{if(active){setItems(data.items);setNext(data.next_page);}}).catch(e=>{if(active)setError(errMsg(e));}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[page,open,refresh]);
  async function loadClients(number=1) {
    setClientsLoading(true);setClientError("");
    try {
      const {data}=await api.get('/clients',{params:{page:number,limit:500}});
      setClients(previous=>number===1?data:[...previous,...data.filter(c=>!previous.some(old=>old.id===c.id))]);setClientPage(number);setMoreClients(data.length===500);
    }catch(e){setClientError(errMsg(e));}finally{setClientsLoading(false);}
  }
  function start(){setLeasing("");setAmount("");setProof(null);setFormError("");key.current=null;setOpen(true);loadClients();}
  useEffect(()=>{if(fromFinance)start();},[fromFinance]);
  function edit(){key.current=null;setFormError("");}
  async function save(event){
    event.preventDefault();if(busy)return;
    if(!leasing||!proof){setFormError("Pilih leasing dan unggah bukti pembayaran.");return;}
    if(!/^\d+(\.\d{1,2})?$/.test(amount)||Number(amount)<=0||Number(amount)>999999999999.99){setFormError("Isi nominal lebih dari nol, maksimal 999999999999.99 dan dua angka desimal.");return;}
    setBusy(true);setFormError("");
    try {
      if(!key.current)key.current=crypto.randomUUID();
      const body=new FormData();body.append('client_id',leasing);body.append('payment_amount',amount);body.append('payment_request_id',key.current);body.append('file',proof);
      await api.post('/leasing-payments',body);toast.success('Pembayaran leasing berhasil disimpan');setPage(1);setOpen(false);if(fromFinance)navigate('/admin/keuangan');
    }catch(e){setFormError(errMsg(e));}finally{setBusy(false);}
  }
  return <div className="space-y-5 animate-fade-in">
    {fromFinance&&<Button variant="outline" onClick={()=>navigate('/admin/keuangan')}>Kembali ke Laporan Keuangan</Button>}
    <div className="flex items-center justify-between gap-3 flex-wrap"><div><h1 className="font-heading text-2xl font-bold text-slate-900">Pembayaran Leasing</h1><p className="text-sm text-slate-500 mt-1">Penerimaan pembayaran dari leasing beserta bukti pembayaran.</p></div><Button onClick={start} data-testid="leasing-payment-create">Pembayaran Baru</Button></div>
    <div className="brand-panel rounded-2xl border border-slate-200 overflow-hidden">
      {loading?<div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-blue-600"/></div>:error?<div role="alert" className="p-5 space-y-3"><p>{error}</p><Button variant="outline" onClick={()=>{setRefresh(value=>value+1);}}>Coba lagi</Button></div>:!items.length?<EmptyState icon={Wallet} title="Belum ada pembayaran leasing" desc="Klik Pembayaran Baru untuk mencatat pembayaran dan mengunggah buktinya."/>:<div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider"><tr className="text-left"><th className="px-5 py-3 font-medium">Tanggal Dicatat</th><th className="px-5 py-3 font-medium">Leasing</th><th className="px-5 py-3 font-medium">Jumlah Pembayaran</th><th className="px-5 py-3 font-medium">Bukti Pembayaran</th></tr></thead><tbody>{items.map(row=><tr key={row.id} className="border-t border-slate-100" data-testid={`leasing-payment-row-${row.id}`}><td className="px-5 py-3 whitespace-nowrap">{formatDateTime(row.created_at)}</td><td className="px-5 py-3 font-medium">{row.leasing_name}</td><td className="px-5 py-3 whitespace-nowrap">{rupiah(row.payment_amount)}</td><td className="px-5 py-3"><a className="text-blue-600 font-semibold hover:underline" href={fileUrl(row.url)} target="_blank" rel="noopener noreferrer">Lihat Bukti</a></td></tr>)}</tbody></table></div>}
    </div>
    {(page>1||next)&&<div className="flex justify-end items-center gap-3"><Button variant="outline" disabled={loading||page===1} onClick={()=>setPage(p=>p-1)}>Sebelumnya</Button><span className="text-sm">Halaman {page}</span><Button variant="outline" disabled={loading||!next} onClick={()=>setPage(next)}>Berikutnya</Button></div>}
    <Dialog open={open} onOpenChange={value=>{if(!busy)setOpen(value);}}><DialogContent><DialogHeader><DialogTitle>Pembayaran Leasing Baru</DialogTitle><DialogDescription>Tanggal dicatat otomatis saat pembayaran berhasil disimpan.</DialogDescription></DialogHeader>
      <form onSubmit={save} className="space-y-4">
        <div className="space-y-2"><label htmlFor="leasing" className="text-sm font-medium">Leasing</label><select id="leasing" required disabled={busy||clientsLoading} value={leasing} onChange={e=>{setLeasing(e.target.value);edit();}} className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white" data-testid="leasing-payment-client"><option value="">{clientsLoading?'Memuat leasing...':'Pilih leasing'}</option>{clients.map(c=><option key={c.id} value={c.id}>{c.nama_perusahaan}</option>)}</select>{clientError&&<p role="alert" className="text-sm text-red-600">{clientError}</p>}{clientError&&<Button type="button" variant="outline" onClick={()=>loadClients(clientPage)}>Coba lagi</Button>}{moreClients&&<Button type="button" variant="outline" disabled={busy||clientsLoading} onClick={()=>loadClients(clientPage+1)}>Muat leasing lainnya</Button>}{!clientsLoading&&!clientError&&!clients.length&&<p className="text-sm text-slate-500">Tambahkan data melalui menu Pemberi Kuasa / Leasing terlebih dahulu.</p>}</div>
        <div className="space-y-2"><label htmlFor="leasing-amount" className="text-sm font-medium">Jumlah Pembayaran (Rp)</label><Input id="leasing-amount" required type="number" min="0.01" max="999999999999.99" step="0.01" disabled={busy} value={amount} onChange={e=>{setAmount(e.target.value);edit();}} placeholder="Contoh: 1500000" data-testid="leasing-payment-amount"/></div>
        <div className="space-y-2"><label htmlFor="leasing-proof" className="text-sm font-medium">Bukti Pembayaran</label><Input id="leasing-proof" type="file" required disabled={busy} accept="image/jpeg,image/png,image/webp,application/pdf" onChange={e=>{const file=e.target.files?.[0];edit();if(file&&(!['image/jpeg','image/png','image/webp','application/pdf'].includes(file.type)||!file.size||file.size>8*1024*1024)){e.target.value='';setProof(null);setFormError('Gunakan JPG, PNG, WEBP atau PDF maksimal 8 MB.');return;}setProof(file||null);}} data-testid="leasing-payment-proof"/><p className="text-xs text-slate-500">JPG, PNG, WEBP atau PDF, maksimal 8 MB.</p></div>
        {formError&&<p role="alert" className="text-sm text-red-600">{formError}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={()=>setOpen(false)}>Batal</Button><Button type="submit" disabled={busy||clientsLoading||!clients.length} data-testid="leasing-payment-save">{busy?<><Loader2 className="w-4 h-4 mr-2 animate-spin"/>Menyimpan...</>:'Simpan Pembayaran'}</Button></div>
      </form>
    </DialogContent></Dialog>
  </div>;
}
