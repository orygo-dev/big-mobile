import {useEffect, useState} from "react";
import api, {errMsg} from "@/lib/api";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {toast} from "sonner";

const labels={PENDING:"Antrean",SENDING:"Sedang dikirim",ACCEPTED:"Diterima Fonnte",FAILED:"Gagal",UNKNOWN:"Periksa di Fonnte",SKIPPED:"Dilewati"};
export default function FonnteSettings(){
 const [form,setForm]=useState(null),[token,setToken]=useState(""),[rows,setRows]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const load=async()=>{try{const [settings,history]=await Promise.all([api.get("/whatsapp/settings"),api.get("/whatsapp/notifications")]);setForm(settings.data);setRows(history.data);setError("");}catch(e){setError(errMsg(e));}};
 useEffect(()=>{load();},[]);
 const save=async(e)=>{e.preventDefault();setBusy(true);try{const result=await api.put("/whatsapp/settings",{enabled:form.enabled,owner_phone:form.owner_phone,owner_template:form.owner_template,payment_template:form.payment_template,token});setForm(result.data);setToken("");toast.success("Pengaturan WhatsApp disimpan");}catch(e){toast.error(errMsg(e));}finally{setBusy(false);}};
 const retry=async(id)=>{setBusy(true);try{await api.post(`/whatsapp/notifications/${id}/retry`);await load();toast.success("Pesan masuk antrean ulang");}catch(e){toast.error(errMsg(e));}finally{setBusy(false);}};
 const field=(key,value)=>setForm({...form,[key]:value});
 return <section className="brand-panel p-5 space-y-4" data-testid="fonnte-settings"><h2 className="font-semibold text-slate-800">Notifikasi WhatsApp · Fonnte</h2>
 <p className="text-sm text-slate-500">Kirim permintaan approval ke owner dan informasi pembayaran kepada seluruh petugas dalam tim. Hubungkan perangkat WhatsApp di Fonnte sebelum mengaktifkan.</p>
 {error&&<p role="alert" className="text-red-600">{error} <button type="button" onClick={load}>Muat ulang</button></p>}
 {form&&<form onSubmit={save} className="space-y-3"><label className="flex gap-2 items-center"><input type="checkbox" checked={form.enabled} onChange={e=>field("enabled",e.target.checked)}/>Aktifkan notifikasi otomatis</label>
 <label className="block text-sm">Token Fonnte<Input type="password" autoComplete="new-password" value={token} onChange={e=>setToken(e.target.value)} placeholder={form.token_configured?"Token tersimpan; kosongkan untuk mempertahankan":"Masukkan token perangkat Fonnte"}/></label>
 <label className="block text-sm">Nomor WhatsApp owner<Input value={form.owner_phone} onChange={e=>field("owner_phone",e.target.value)} placeholder="081234567890" maxLength={32}/></label>
 {[['owner_template','Format pesan approval owner'],['payment_template','Format pesan pembayaran petugas']].map(([key,label])=><label className="block text-sm" key={key}>{label}<textarea className="w-full rounded-lg border p-3 min-h-28" required maxLength={4000} value={form[key]} onChange={e=>field(key,e.target.value)}/></label>)}
 <p className="text-xs text-slate-500">Placeholder: {"{perusahaan}, {nomor_penugasan}, {admin}, {nama_petugas}, {nominal_tim}, {tanggal_pembayaran}, {jumlah_petugas}"}. Nominal pembayaran adalah total tim. Nomor petugas mengikuti data Petugas. Notifikasi hanya untuk kejadian baru saat fitur aktif.</p>
 <Button disabled={busy} type="submit">{busy?"Memproses…":"Simpan pengaturan WhatsApp"}</Button></form>}
 <div className="flex justify-between items-center"><h3 className="font-medium">50 notifikasi terbaru</h3><Button type="button" variant="outline" disabled={busy} onClick={load}>Perbarui</Button></div>
 <p className="text-xs text-slate-500">Diterima Fonnte berarti masuk antrean penyedia, belum memastikan pesan diterima di ponsel. Hasil ambigu harus diperiksa pada riwayat Fonnte untuk menghindari pesan ganda.</p>
 <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-sm"><thead><tr className="text-left border-b"><th className="p-2">Tanggal</th><th>Penerima</th><th>Jenis</th><th>Status</th><th/></tr></thead><tbody>{rows.map(row=><tr className="border-b" key={row.id}><td className="p-2 whitespace-nowrap">{new Date(row.created_at).toLocaleString('id-ID')}</td><td>{row.recipient_name}<div className="text-xs text-slate-500">{row.target||'Nomor belum diisi'}</div></td><td>{row.event==='approval'?'Approval':'Pembayaran tim'}</td><td><span className={row.status==='FAILED'||row.status==='UNKNOWN'?'text-red-600':'text-blue-700'}>{labels[row.status]||row.status}</span>{row.error&&<p className="text-xs max-w-xs">{row.error}</p>}</td><td>{row.status==='FAILED'&&<Button disabled={busy} variant="outline" onClick={()=>retry(row.id)}>Coba ulang</Button>}</td></tr>)}{rows.length===0&&<tr><td colSpan={5} className="p-3 text-slate-500">Belum ada notifikasi.</td></tr>}</tbody></table></div></section>;
}
