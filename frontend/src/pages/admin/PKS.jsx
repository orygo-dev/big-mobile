import DeleteDataButton from "@/components/DeleteDataButton";
import {useEffect, useRef, useState} from "react";
import api, {errMsg, fileUrl} from "@/lib/api";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription} from "@/components/ui/dialog";
import EmptyState from "@/components/EmptyState";
import {FileSignature, Loader2, Search, Check} from "lucide-react";
import {toast} from "sonner";

const STATES={
  AKTIF:{label:'Aktif',color:'bg-emerald-100 text-emerald-800'},
  MENDEKATI_EXPIRED:{label:'Mendekati Expired',color:'bg-orange-100 text-orange-800'},
  EXPIRED:{label:'Expired',color:'bg-red-100 text-red-800'},
  BELUM_AKTIF:{label:'Belum Aktif',color:'bg-blue-100 text-blue-800'},
  BELUM_MEMILIKI:{label:'Belum Memiliki PKS',color:'bg-slate-100 text-slate-600'},
};
const dateLabel=value=>value?new Intl.DateTimeFormat('id-ID',{day:'numeric',month:'long',year:'numeric',timeZone:'Asia/Jakarta'}).format(new Date(value+'T00:00:00+07:00')):'—';
function Badge({state,officer=false}){
  const item=STATES[state]||STATES.BELUM_MEMILIKI;
  const label=officer&&state!=='BELUM_MEMILIKI'?`Memiliki PKS · ${item.label}`:item.label;
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${item.color}`}>{label}</span>;
}

function NewPKS({open,onOpenChange,onSaved}){
  const [search,setSearch]=useState(''),[page,setPage]=useState(1),[options,setOptions]=useState([]),[next,setNext]=useState(null),[loading,setLoading]=useState(false),[loadError,setLoadError]=useState(''),[reload,setReload]=useState(0);
  const [selected,setSelected]=useState(null),[duration,setDuration]=useState('1'),[unit,setUnit]=useState('TAHUN'),[dates,setDates]=useState(null),[datesLoading,setDatesLoading]=useState(false),[datesError,setDatesError]=useState('');
  const [file,setFile]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');const key=useRef(null);
  const [officerOpen,setOfficerOpen]=useState(false);
  const officerPicker=useRef(null),officerInput=useRef(null);
  const validDuration=/^\d+$/.test(duration)&&Number(duration)>=1&&Number(duration)<=(unit==='TAHUN'?50:600);
  useEffect(()=>{
    if(!open||!officerOpen)return;
    let active=true;setLoading(true);setLoadError('');
    const timer=setTimeout(()=>api.get('/pks/officers',{params:{search,page}}).then(({data})=>{if(active){setOptions(previous=>page===1?data.items:[...previous,...data.items.filter(item=>!previous.some(old=>old.id===item.id))]);setNext(data.next_page);}}).catch(e=>{if(active)setLoadError(errMsg(e));}).finally(()=>{if(active)setLoading(false);}),250);
    return ()=>{active=false;clearTimeout(timer);};
  },[open,officerOpen,search,page,reload]);
  useEffect(()=>{
    if(!officerOpen)return;
    const closeOutside=event=>{if(!officerPicker.current?.contains(event.target))setOfficerOpen(false);};
    document.addEventListener('pointerdown',closeOutside);
    return ()=>document.removeEventListener('pointerdown',closeOutside);
  },[officerOpen]);
  function openOfficers(){
    if(busy||officerOpen)return;
    if(selected){setSearch('');setPage(1);setOptions([]);}
    setOfficerOpen(true);
  }
  function chooseOfficer(item){
    setSelected(item);setSearch('');setPage(1);setOptions([]);setOfficerOpen(false);edit();officerInput.current?.focus();
  }
  function pickerKeys(event){
    if(event.key==='Escape'&&officerOpen){event.preventDefault();event.stopPropagation();setOfficerOpen(false);officerInput.current?.focus();}
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
      event.preventDefault();
      if(!officerOpen){openOfficers();return;}
      const choices=[...officerPicker.current.querySelectorAll('[role="option"]:not(:disabled)')];
      if(!choices.length)return;
      const index=choices.indexOf(document.activeElement);
      choices[index<0?(event.key==='ArrowDown'?0:choices.length-1):(index+(event.key==='ArrowDown'?1:-1)+choices.length)%choices.length].focus();
    }
    if(event.key==='Enter'&&event.target===officerInput.current){event.preventDefault();if(!officerOpen)openOfficers();}
  }
  useEffect(()=>{
    if(!open)return;
    setDates(null);setDatesError('');
    if(!validDuration){setDatesLoading(false);return;}
    let active=true;setDatesLoading(true);
    const timer=setTimeout(()=>api.get('/pks/period',{params:{duration:Number(duration),unit}}).then(({data})=>{if(active)setDates(data);}).catch(e=>{if(active)setDatesError(errMsg(e));}).finally(()=>{if(active)setDatesLoading(false);}),250);
    return ()=>{active=false;clearTimeout(timer);};
  },[open,duration,unit,validDuration,reload]);
  function edit(){key.current=null;setError('');}
  async function save(event){
    event.preventDefault();if(busy)return;
    if(!selected||!file||!validDuration||!dates){setError('Pilih petugas, isi durasi yang valid, dan unggah PDF PKS.');return;}
    setBusy(true);setError('');
    try{
      if(!key.current)key.current=crypto.randomUUID();
      const body=new FormData();body.append('officer_id',selected.id);body.append('duration',duration);body.append('unit',unit);body.append('submission_id',key.current);body.append('file',file);
      await api.post('/pks',body,{timeout:120000});toast.success('PKS petugas berhasil disimpan');onSaved();
    }catch(e){setError(errMsg(e));}finally{setBusy(false);}
  }
  return <Dialog open={open} onOpenChange={value=>{if(!busy)onOpenChange(value);}}><DialogContent onEscapeKeyDown={event=>{if(officerOpen){event.preventDefault();setOfficerOpen(false);officerInput.current?.focus();}}} className="max-h-[90vh] overflow-y-auto sm:max-w-xl"><DialogHeader><DialogTitle>PKS Baru</DialogTitle><DialogDescription>Pilih petugas dan durasi, lalu unggah dokumen PKS yang sudah disiapkan.</DialogDescription></DialogHeader>
    <form onSubmit={save} className="space-y-4">
      <div className="space-y-2"><label htmlFor="pks-officer-search" className="text-sm font-medium">Petugas</label>
        <div ref={officerPicker} className="relative" onKeyDown={pickerKeys} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget))setOfficerOpen(false);}}>
          <Search className="w-4 h-4 absolute top-3 left-3 text-slate-400"/>
          <Input ref={officerInput} id="pks-officer-search" role="combobox" aria-expanded={officerOpen} aria-controls="pks-officer-options" aria-autocomplete="list" autoComplete="off" placeholder="Cari nama atau kode petugas..." disabled={busy} value={officerOpen?search:(selected?.name||search)} onClick={openOfficers} onChange={e=>{setSearch(e.target.value);setSelected(null);setPage(1);setOptions([]);setOfficerOpen(true);edit();}} className="pl-9" data-testid="pks-officer-search"/>
          {officerOpen&&<div className="absolute z-30 top-full mt-1 w-full rounded-xl border border-slate-200 bg-white shadow-lg max-h-56 overflow-y-auto">
            <div id="pks-officer-options" role="listbox" aria-label="Daftar petugas PKS" className="divide-y divide-slate-100">{options.map(item=><button type="button" role="option" aria-selected={selected?.id===item.id} key={item.id} disabled={busy} onClick={()=>chooseOfficer(item)} className={`w-full text-left p-3 flex items-center justify-between gap-3 ${selected?.id===item.id?'bg-blue-50':'hover:bg-slate-50'}`} data-testid={`pks-officer-${item.id}`}><div className="min-w-0"><p className="text-sm font-medium break-words">{item.name}</p><p className="text-xs text-slate-500">{item.petugas_code}</p><Badge state={item.pks_status} officer/></div>{selected?.id===item.id&&<Check className="w-4 h-4 shrink-0 text-blue-600"/>}</button>)}{loading&&<p className="p-3 text-sm text-slate-500">Memuat petugas...</p>}{!loading&&!loadError&&!options.length&&<p className="p-3 text-sm text-slate-500">Petugas tidak ditemukan.</p>}</div>
            {next&&!loading&&<Button type="button" variant="outline" className="m-2" disabled={busy} onClick={()=>setPage(next)}>Muat petugas lainnya</Button>}
            {loadError&&<div role="alert" className="p-3 text-sm text-red-600"><p>{loadError}</p><Button type="button" variant="outline" onClick={()=>setReload(v=>v+1)}>Coba lagi</Button></div>}
          </div>}
        </div>
        {selected&&<div className="rounded-xl bg-blue-50 p-3 text-sm" data-testid="pks-selected-officer"><strong>{selected.name}</strong>{selected.pks_end_date&&<p className="mt-1 text-xs">PKS sebelumnya berlaku sampai {dateLabel(selected.pks_end_date)}. Dokumen sebelumnya tetap tersimpan.</p>}</div>}
      </div>
      <div className="grid grid-cols-2 gap-3"><label className="text-sm font-medium space-y-2" htmlFor="pks-duration">Durasi<Input id="pks-duration" type="number" min="1" max={unit==='TAHUN'?50:600} step="1" required disabled={busy} value={duration} onChange={e=>{setDuration(e.target.value);edit();}} data-testid="pks-duration"/></label><label className="text-sm font-medium space-y-2" htmlFor="pks-unit">Satuan<select id="pks-unit" disabled={busy} value={unit} onChange={e=>{setUnit(e.target.value);edit();}} className="block w-full h-10 border border-slate-200 rounded-xl px-3 bg-white" data-testid="pks-unit"><option value="TAHUN">Tahun</option><option value="BULAN">Bulan</option></select></label></div>
      {!validDuration&&<p className="text-sm text-red-600">Isi durasi bulat 1–50 tahun atau 1–600 bulan.</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3"><label htmlFor="pks-start" className="text-sm font-medium space-y-2">Tanggal Mulai<Input id="pks-start" readOnly value={datesLoading?'Menghitung...':dateLabel(dates?.start_date)} className="bg-slate-50" data-testid="pks-start"/></label><label htmlFor="pks-end" className="text-sm font-medium space-y-2">Berlaku Sampai<Input id="pks-end" readOnly value={datesLoading?'Menghitung...':dateLabel(dates?.end_date)} className="bg-slate-50" data-testid="pks-end"/></label></div>
      <p className="text-xs text-slate-500">Tanggal otomatis berdasarkan tanggal penyimpanan (WIB) dan durasi. Kedua tanggal tidak dapat diedit.</p>
      {datesError&&<div role="alert" className="text-sm text-red-600"><p>{datesError}</p><Button type="button" variant="outline" onClick={()=>setReload(v=>v+1)}>Hitung ulang</Button></div>}
      <label htmlFor="pks-file" className="block space-y-2 text-sm font-medium">File PKS<Input id="pks-file" type="file" required disabled={busy} accept="application/pdf,.pdf" data-testid="pks-file" onChange={e=>{edit();const chosen=e.target.files?.[0];if(chosen&&((chosen.type&&chosen.type!=='application/pdf')||!chosen.size||chosen.size>8*1024*1024)){setFile(null);e.target.value='';setError('Gunakan PDF maksimal 8 MB.');return;}setFile(chosen||null);}}/></label><p className="text-xs text-slate-500">PDF maksimal 8 MB. Dokumen disimpan secara privat.</p>
      {error&&<p role="alert" className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={()=>onOpenChange(false)}>Batal</Button><Button type="submit" disabled={busy||!selected||!file||!validDuration||!dates||datesLoading} data-testid="pks-save">{busy?<><Loader2 className="w-4 h-4 mr-2 animate-spin"/>Menyimpan...</>:'Simpan PKS'}</Button></div>
    </form>
  </DialogContent></Dialog>;
}

export default function PKS(){
  const [items,setItems]=useState([]),[search,setSearch]=useState(''),[state,setState]=useState(''),[page,setPage]=useState(1),[next,setNext]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[refresh,setRefresh]=useState(0),[open,setOpen]=useState(false);
  useEffect(()=>{
    let active=true;setLoading(true);setError('');
    const timer=setTimeout(()=>api.get('/pks',{params:{search,state,page}}).then(({data})=>{if(active){setItems(data.items);setNext(data.next_page);}}).catch(e=>{if(active)setError(errMsg(e));}).finally(()=>{if(active)setLoading(false);}),250);
    return ()=>{active=false;clearTimeout(timer);};
  },[search,state,page,refresh]);
  // Refresh computed statuses when the browser remains open across a WIB date boundary.
  useEffect(()=>{const timer=setInterval(()=>setRefresh(v=>v+1),60000);return ()=>clearInterval(timer);},[]);
  return <div className="space-y-5 animate-fade-in">
    <div className="flex items-center justify-between gap-3 flex-wrap"><div><h1 className="font-heading text-2xl font-bold text-slate-900">PKS Petugas</h1><p className="text-sm text-slate-500 mt-1">Perjanjian kerja sama petugas, dokumen, dan masa berlaku.</p></div><Button onClick={()=>setOpen(true)} data-testid="pks-create">PKS Baru</Button></div>
    <div className="brand-panel rounded-2xl border border-slate-200 p-4 flex flex-wrap gap-3"><Input placeholder="Cari nama petugas..." value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}} className="flex-1 min-w-40" data-testid="pks-search"/><select value={state} onChange={e=>{setState(e.target.value);setPage(1);}} className="border border-slate-200 rounded-xl px-3 py-2 bg-white text-sm" aria-label="Filter status PKS"><option value="">Semua Status</option>{Object.entries(STATES).filter(([key])=>key!=='BELUM_MEMILIKI').map(([key,item])=><option value={key} key={key}>{item.label}</option>)}</select></div>
    <p className="text-xs text-slate-500">Mendekati Expired: tersisa 0–30 hari. PKS berlaku sampai akhir tanggal berakhir (WIB). Riwayat PKS lama tetap tersimpan.</p>
    <div className="brand-panel rounded-2xl border border-slate-200 overflow-hidden">{loading?<div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600"/></div>:error?<div role="alert" className="p-5 space-y-3"><p>{error}</p><Button variant="outline" onClick={()=>setRefresh(v=>v+1)}>Coba lagi</Button></div>:!items.length?<EmptyState icon={FileSignature} title="Belum ada PKS" desc="Klik PKS Baru untuk mengunggah perjanjian petugas atau sesuaikan filter."/>:<div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider"><tr className="text-left">{['Petugas','Tanggal Mulai','Berlaku Sampai','Durasi','Status','Dokumen','Aksi'].map(label=><th className="px-4 py-3 font-medium" key={label}>{label}</th>)}</tr></thead><tbody>{items.map(item=><tr key={item.id} className="border-t border-slate-100" data-testid="pks-row"><td className="px-4 py-3 font-medium">{item.officer_name}<p className="text-xs text-slate-500">{item.officer_code}</p></td><td className="px-4 py-3 whitespace-nowrap">{dateLabel(item.start_date)}</td><td className="px-4 py-3 whitespace-nowrap">{dateLabel(item.end_date)}</td><td className="px-4 py-3 whitespace-nowrap">{item.duration} {item.duration_unit==='TAHUN'?'tahun':'bulan'}</td><td className="px-4 py-3"><Badge state={item.status}/></td><td className="px-4 py-3"><a href={fileUrl(item.url)} target="_blank" rel="noopener noreferrer" className="font-semibold text-blue-600 hover:underline whitespace-nowrap">Lihat PKS</a></td><td className="px-4 py-3"><DeleteDataButton endpoint={`/pks/${item.id}`} name={`PKS ${item.officer_name}`} testId={`pks-delete-${item.id}`} description="File PKS dihapus dan label kepemilikan PKS petugas dihitung ulang dari dokumen yang tersisa." onDeleted={()=>{if(items.length===1&&page>1)setPage(page-1);else setRefresh(v=>v+1);}}/></td></tr>)}</tbody></table></div>}</div>
    {(page>1||next)&&<div className="flex justify-end gap-3 items-center"><Button variant="outline" disabled={loading||page===1} onClick={()=>setPage(v=>v-1)}>Sebelumnya</Button><span className="text-sm">Halaman {page}</span><Button variant="outline" disabled={loading||!next} onClick={()=>setPage(next)}>Berikutnya</Button></div>}
    {open&&<NewPKS open={open} onOpenChange={setOpen} onSaved={()=>{setOpen(false);setPage(1);setRefresh(v=>v+1);}}/>}
  </div>;
}
