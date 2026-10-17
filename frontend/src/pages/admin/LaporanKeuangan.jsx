import {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import api, {errMsg, fileUrl} from "@/lib/api";
import {formatDateTime} from "@/lib/constants";
import ReportPayment, {rupiah} from "@/components/ReportPayment";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription} from "@/components/ui/dialog";
import EmptyState from "@/components/EmptyState";
import {ArrowDownLeft, ArrowUpRight, ChartNoAxesCombined, Download, Loader2} from "lucide-react";

export default function LaporanKeuangan() {
  const navigate=useNavigate();
  const [start,setStart]=useState(''),[end,setEnd]=useState(''),[kind,setKind]=useState(''),[page,setPage]=useState(1),[refresh,setRefresh]=useState(0);
  const [data,setData]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[exporting,setExporting]=useState(''),[exportError,setExportError]=useState('');
  const [expenseOpen,setExpenseOpen]=useState(false),[pending,setPending]=useState([]),[pendingLoading,setPendingLoading]=useState(false),[pendingError,setPendingError]=useState(''),[selected,setSelected]=useState(''),[report,setReport]=useState(null),[reportLoading,setReportLoading]=useState(false);
  const invalid=!!(start&&end&&start>end);
  useEffect(()=>{
    let active=true;
    if(invalid){setLoading(false);setData(null);return;}
    setLoading(true);setError('');
    api.get('/finance',{params:{start,end,kind,page}}).then(({data})=>{if(active)setData(data);}).catch(e=>{if(active){setError(errMsg(e));setData(null);}}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[start,end,kind,page,refresh,invalid]);
  useEffect(()=>{setExportError('');},[start,end,kind]);
  useEffect(()=>{
    if(!expenseOpen)return;
    let active=true;setPendingLoading(true);setPendingError('');setSelected('');setReport(null);
    Promise.all([api.get('/laporan',{params:{payment_status:'MENUNGGU_PEMBAYARAN'}}),api.get('/laporan',{params:{payment_status:'BELUM_DICATAT'}})]).then(responses=>{if(active)setPending(responses.flatMap(r=>r.data).filter(r=>!r.payment_proof));}).catch(e=>{if(active)setPendingError(errMsg(e));}).finally(()=>{if(active)setPendingLoading(false);});
    return ()=>{active=false;};
  },[expenseOpen]);
  useEffect(()=>{
    if(!selected){setReport(null);setReportLoading(false);return;}
    let active=true;setReport(null);setPendingError('');setReportLoading(true);
    api.get(`/laporan/${selected}`).then(({data})=>{if(active)setReport(data);}).catch(e=>{if(active)setPendingError(errMsg(e));}).finally(()=>{if(active)setReportLoading(false);});
    return ()=>{active=false;};
  },[selected]);
  function filter(setter,value){setter(value);setPage(1);}
  async function download(extension){
    if(exporting||invalid)return;setExporting(extension);setExportError('');
    try {
      const response=await api.get(`/finance/export/${extension}`,{params:{start,end,kind},responseType:'blob',timeout:120000});
      const url=URL.createObjectURL(response.data);const link=document.createElement('a');link.href=url;link.download=`laporan-keuangan.${extension}`;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){
      if(e.response?.data instanceof Blob){try{e.response.data=JSON.parse(await e.response.data.text());}catch{ /* Keep the original error if the proxy returned a non-JSON body. */ }}
      setExportError(errMsg(e));
    }finally{setExporting('');}
  }
  return <div className="space-y-5 animate-fade-in">
    <div className="flex items-center justify-between gap-3 flex-wrap"><div><h1 className="font-heading text-2xl font-bold text-slate-900">Laporan Keuangan</h1><p className="text-sm text-slate-500 mt-1">Pemasukan leasing dan pengeluaran pembayaran petugas yang sudah selesai.</p></div><div className="flex gap-2 flex-wrap"><Button variant="outline" onClick={()=>setExpenseOpen(true)} data-testid="finance-add-expense"><ArrowUpRight className="w-4 h-4 mr-1"/>Tambah Pengeluaran</Button><Button onClick={()=>navigate('/admin/pembayaran-leasing?from=keuangan')} data-testid="finance-add-income"><ArrowDownLeft className="w-4 h-4 mr-1"/>Tambah Pemasukan</Button></div></div>
    <div className="brand-panel rounded-2xl border border-slate-200 p-4 flex flex-wrap gap-3 items-end">
      <label className="text-sm space-y-1">Dari tanggal<Input type="date" value={start} onChange={e=>filter(setStart,e.target.value)} data-testid="finance-start"/></label>
      <label className="text-sm space-y-1">Sampai tanggal<Input type="date" value={end} onChange={e=>filter(setEnd,e.target.value)} data-testid="finance-end"/></label>
      <label className="text-sm space-y-1">Jenis transaksi<select value={kind} onChange={e=>filter(setKind,e.target.value)} className="block h-10 rounded-xl border border-slate-200 bg-white px-3" data-testid="finance-kind"><option value="">Semua transaksi</option><option value="PEMASUKAN">Pemasukan</option><option value="PENGELUARAN">Pengeluaran</option></select></label>
      <Button variant="outline" onClick={()=>{setStart('');setEnd('');setKind('');setPage(1);}}>Reset Filter</Button>
      <div className="flex gap-2 flex-wrap lg:ml-auto">{['pdf','xlsx'].map(extension=><Button key={extension} variant="outline" disabled={loading||invalid||!!error||!!exporting} onClick={()=>download(extension)} data-testid={`finance-export-${extension}`}>{exporting===extension?<Loader2 className="w-4 h-4 mr-2 animate-spin"/>:<Download className="w-4 h-4 mr-2"/>}{extension==='pdf'?'Ekspor PDF':'Ekspor Excel'}</Button>)}</div>
    </div>
    {invalid&&<p role="alert" className="text-sm text-red-600">Tanggal akhir harus setelah atau sama dengan tanggal awal.</p>}
    {exportError&&<p role="alert" className="text-sm text-red-600">{exportError}</p>}
    {!invalid&&<>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{[['Total Pemasukan','income','bg-emerald-50 border-emerald-200 text-emerald-800'],['Total Pengeluaran','expense','bg-orange-50 border-orange-200 text-orange-800'],['Selisih','balance','bg-blue-50 border-blue-200 text-blue-800']].map(([label,key,style])=><div key={key} className={`rounded-2xl border p-5 ${style}`}><p className="text-sm font-semibold">{label}</p><p className="text-2xl font-bold mt-2 break-words" data-testid={`finance-${key}`}>{loading?'…':data?rupiah(data.summary[key]):'—'}</p></div>)}</div>
      <p className="text-xs text-slate-500">Total mengikuti seluruh hasil filter. Tanggal memakai WIB; selisih adalah pemasukan dikurangi pengeluaran pada periode yang dipilih.</p>
      <div className="brand-panel rounded-2xl border border-slate-200 overflow-hidden">
        {loading?<div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-blue-600"/></div>:error?<div role="alert" className="p-5 space-y-3"><p>{error}</p><Button variant="outline" onClick={()=>setRefresh(v=>v+1)}>Coba lagi</Button></div>:!data?.items.length?<EmptyState icon={ChartNoAxesCombined} title="Belum ada transaksi" desc="Tambahkan pembayaran atau sesuaikan filter tanggal dan jenis transaksi."/>:<div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider"><tr className="text-left">{['Tanggal Transaksi','Jenis','Leasing / Tim','Keterangan','Nominal','Bukti','Sumber'].map(label=><th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody>{data.items.map(row=><tr key={row.id} className="border-t border-slate-100" data-testid="finance-row"><td className="px-4 py-3 whitespace-nowrap">{formatDateTime(row.date)}</td><td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${row.type==='PEMASUKAN'?'bg-emerald-100 text-emerald-800':'bg-orange-100 text-orange-800'}`}>{row.type==='PEMASUKAN'?'Pemasukan':'Pengeluaran'}</span></td><td className="px-4 py-3 min-w-40 font-medium break-words">{row.party}</td><td className="px-4 py-3 min-w-48 max-w-sm break-words whitespace-pre-wrap">{row.description}</td><td className="px-4 py-3 whitespace-nowrap font-semibold">{rupiah(row.amount)}</td><td className="px-4 py-3">{row.proof_url&&<a className="text-blue-600 hover:underline whitespace-nowrap" href={fileUrl(row.proof_url)} target="_blank" rel="noopener noreferrer">Lihat Bukti</a>}</td><td className="px-4 py-3"><button className="text-blue-600 hover:underline whitespace-nowrap" onClick={()=>navigate(row.source_url)}>Buka Sumber</button></td></tr>)}</tbody></table></div>}
      </div>
      {data&&(page>1||data.next_page)&&<div className="flex justify-end items-center gap-3"><Button variant="outline" disabled={loading||page===1} onClick={()=>setPage(v=>v-1)}>Sebelumnya</Button><span className="text-sm">Halaman {page} · {data.total} transaksi</span><Button variant="outline" disabled={loading||!data.next_page} onClick={()=>setPage(data.next_page)}>Berikutnya</Button></div>}
    </>}
    <Dialog open={expenseOpen} onOpenChange={setExpenseOpen}><DialogContent className="max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>Tambah Pengeluaran Petugas</DialogTitle><DialogDescription>Pilih laporan yang belum dibayar. Pengeluaran tercatat setelah bukti pembayaran berhasil disimpan.</DialogDescription></DialogHeader>
      {pendingLoading?<p className="text-sm">Memuat laporan...</p>:<label className="block text-sm space-y-2">Laporan petugas<select className="w-full rounded-xl border border-slate-200 p-2 bg-white" value={selected} onChange={e=>setSelected(e.target.value)} data-testid="finance-expense-report"><option value="">Pilih laporan</option>{pending.map(item=><option key={item.id} value={item.id}>{item.letter_nomor||item.id} · {item.petugas_name||'Tim petugas'} · {rupiah(item.payment_amount)}</option>)}</select></label>}
      {pendingError&&<p role="alert" className="text-sm text-red-600">{pendingError}</p>}
      {!pendingLoading&&!pendingError&&!pending.length&&<p className="text-sm text-slate-500">Semua laporan sudah dibayar atau belum ada laporan.</p>}
      {reportLoading?<Loader2 className="w-5 h-5 animate-spin"/>:report&&<ReportPayment key={report.id} report={report} admin onSaved={()=>{setExpenseOpen(false);setPage(1);setRefresh(v=>v+1);}}/>}
      <Button variant="outline" onClick={()=>navigate('/admin/laporan')}>Buka Menu Laporan Petugas</Button>
    </DialogContent></Dialog>
  </div>;
}
