import {useEffect, useMemo, useRef, useState} from "react";
import api, {errMsg} from "@/lib/api";
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Textarea} from "@/components/ui/textarea";
import {Button} from "@/components/ui/button";
import {Select,SelectTrigger,SelectValue,SelectContent,SelectItem} from "@/components/ui/select";
import {toast} from "sonner";

export default function AdminReportDialog({open,onOpenChange,onCreated}) {
  const [items,setItems]=useState([]),[next,setNext]=useState(null),[loading,setLoading]=useState(false),[loadError,setLoadError]=useState("");
  const [assignment,setAssignment]=useState(""),[amount,setAmount]=useState(""),[notes,setNotes]=useState(""),[photos,setPhotos]=useState([]),[proof,setProof]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const key=useRef(null);
  const previews=useMemo(()=>photos.map(file=>URL.createObjectURL(file)),[photos]);
  useEffect(()=>()=>previews.forEach(url=>URL.revokeObjectURL(url)),[previews]);
  async function load(page=1) {
    setLoading(true);setLoadError("");
    try {const {data}=await api.get('/laporan-options',{params:{page}});setItems(previous=>page===1?data.items:[...previous,...data.items.filter(item=>!previous.some(old=>old.assignment_id===item.assignment_id))]);setNext(data.next_page);}
    catch(failure){setLoadError(errMsg(failure));}finally{setLoading(false);}
  }
  useEffect(()=>{if(open){setAssignment("");setAmount("");setNotes("");setPhotos([]);setProof(null);setError("");key.current=null;load();}},[open]);
  const edit=()=>{key.current=null;setError("");};
  function select(event,payment=false) {
    const selected=[...event.target.files];event.target.value="";if(!selected.length)return;
    const allowed=payment?["image/jpeg","image/png","image/webp","application/pdf"]:["image/jpeg","image/png","image/webp"];
    if(selected.some(file=>!allowed.includes(file.type)||!file.size||file.size>8*1024*1024)){setError("Format file tidak sesuai atau ukuran melebihi 8 MB.");return;}
    if(!payment&&photos.length+selected.length>10){setError("Maksimal 10 gambar bukti laporan.");return;}
    edit();if(payment)setProof(selected[0]);else setPhotos(previous=>[...previous,...selected]);
  }
  async function submit(event) {
    event.preventDefault();if(busy)return;
    if(!assignment||!photos.length){setError("Pilih penugasan dan unggah minimal satu gambar bukti laporan.");return;}
    if([...photos,...(proof?[proof]:[])].reduce((sum,file)=>sum+file.size,0)>40*1024*1024){setError("Total seluruh file maksimal 40 MB.");return;}
    setBusy(true);setError("");
    try {
      if(!key.current)key.current=crypto.randomUUID();
      const body=new FormData();body.append("assignment_id",assignment);body.append("client_report_id",key.current);body.append("payment_amount",amount);body.append("catatan",notes);photos.forEach(file=>body.append("photos",file));if(proof)body.append("payment_proof",proof);
      let report;
      try {report=(await api.post('/laporan',body,{timeout:120000})).data;}
      catch(failure){const {data}=await api.get('/laporan',{params:{assignment_id:assignment}});report=data.find(item=>item.client_report_id===key.current);if(!report)throw failure;}
      toast.success("Laporan berhasil dibuat");onCreated(report);
    }catch(failure){setError(errMsg(failure));}finally{setBusy(false);}
  }
  return <Dialog open={open} onOpenChange={value=>{if(!busy){if(!value){setPhotos([]);setProof(null);}onOpenChange(value);}}}><DialogContent className="sm:max-w-xl max-h-[90dvh] overflow-y-auto"><DialogHeader><DialogTitle>Laporan Baru</DialogTitle><DialogDescription>Buat laporan penugasan dan catat pembayaran untuk seluruh tim.</DialogDescription></DialogHeader>
    <form onSubmit={submit} className="space-y-4">
      <label className="block text-sm font-medium">Penugasan</label>
      <Select value={assignment} onValueChange={value=>{edit();setAssignment(value);}} disabled={busy||loading}><SelectTrigger data-testid="admin-report-assignment"><SelectValue placeholder="Pilih penugasan yang belum memiliki laporan" /></SelectTrigger><SelectContent>{items.map(item=><SelectItem key={item.assignment_id} value={item.assignment_id}>{item.number} · {item.debtor_name} · {item.officer_count} petugas</SelectItem>)}</SelectContent></Select>
      {loading&&<p className="text-xs text-blue-600">Memuat penugasan…</p>}
      {loadError&&<p role="alert" className="text-sm text-rose-600">{loadError}<button type="button" onClick={()=>load()} className="ml-2 text-blue-600">Coba lagi</button></p>}
      {!loading&&!loadError&&!items.length&&<p className="text-sm text-slate-500">Tidak ada penugasan tanpa laporan pada halaman ini.</p>}
      {next&&<button type="button" disabled={loading} onClick={()=>load(next)} className="text-sm text-blue-600">Muat penugasan lainnya</button>}
      <label className="block text-sm font-medium">Bukti laporan (wajib)<Input type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={event=>select(event)} disabled={busy} data-testid="admin-report-photos" className="mt-2" /></label>
      <div className="grid grid-cols-3 gap-2">{photos.map((file,index)=><div key={index} className="border rounded-xl p-2"><img src={previews[index]} alt={`Bukti ${index+1}`} className="h-20 w-full object-cover rounded-lg" /><button type="button" disabled={busy} onClick={()=>{edit();setPhotos(previous=>previous.filter((_,i)=>i!==index));}} className="text-xs text-rose-600 mt-1">Hapus bukti {index+1}</button></div>)}</div>
      <p className="text-xs text-slate-500">Maksimal 10 gambar JPG/PNG/WEBP, 8 MB per file. Total semua file maksimal 40 MB.</p>
      <label className="block text-sm font-medium">Nominal pembayaran tim (Rp)<Input type="number" min="0.01" step="0.01" max="999999999999.99" required disabled={busy} value={amount} onChange={event=>{edit();setAmount(event.target.value);}} placeholder="Contoh: 500000" data-testid="admin-report-amount" className="mt-2" /></label>
      <label className="block text-sm font-medium">Bukti pembayaran (opsional)<Input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" disabled={busy} onChange={event=>select(event,true)} data-testid="admin-report-payment-proof" className="mt-2" /></label>
      {proof&&<div className="text-xs text-blue-700 flex gap-3"><span>{proof.name}</span><button type="button" disabled={busy} onClick={()=>{edit();setProof(null);}}>Hapus</button></div>}
      <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">{proof?"Bukti pembayaran tersedia. Laporan akan berstatus Selesai.":"Tanpa bukti pembayaran, laporan berstatus Menunggu Pembayaran. Bukti dapat diunggah kemudian."}</p>
      <label className="block text-sm font-medium">Catatan (opsional)<Textarea maxLength={4000} disabled={busy} value={notes} onChange={event=>{edit();setNotes(event.target.value);}} data-testid="admin-report-notes" className="mt-2" /></label>
      {error&&<p role="alert" className="text-sm text-rose-600">{error}</p>}
      <Button type="submit" disabled={busy||loading||!assignment} data-testid="admin-report-submit">{busy?"Menyimpan…":"Simpan Laporan"}</Button>
    </form>
  </DialogContent></Dialog>;
}
