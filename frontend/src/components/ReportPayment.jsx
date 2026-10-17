import {useEffect, useRef, useState} from "react";
import api, {errMsg, fileUrl} from "@/lib/api";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {toast} from "sonner";

export const PAYMENT_STATUS = {
  MENUNGGU_PEMBAYARAN: {label: "Menunggu Pembayaran", className: "bg-amber-100 text-amber-800"},
  SELESAI: {label: "Selesai", className: "bg-emerald-100 text-emerald-800"},
  BELUM_DICATAT: {label: "Belum Dicatat", className: "bg-slate-100 text-slate-600"},
};
export const rupiah = value => value == null || value === "" ? "Belum dicatat" : new Intl.NumberFormat("id-ID", {style:"currency",currency:"IDR",maximumFractionDigits:2}).format(Number(value));
export function PaymentBadge({status}) {
  const item = PAYMENT_STATUS[status] || PAYMENT_STATUS.BELUM_DICATAT;
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold whitespace-nowrap ${item.className}`} data-testid="payment-status">{item.label}</span>;
}

export default function ReportPayment({report, admin = false, onSaved, compact = false}) {
  const [file, setFile] = useState(null), [amount, setAmount] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const pending = useRef(null);
  useEffect(() => {if (window.location.hash === "#pembayaran") document.getElementById("pembayaran")?.scrollIntoView({block:"center"});}, []);
  const choose = event => {
    const selected = event.target.files?.[0]; event.target.value="";
    if (!selected) return;
    if (!["image/jpeg","image/png","image/webp","application/pdf"].includes(selected.type) || selected.size > 8*1024*1024 || !selected.size) {setError("Gunakan JPG, PNG, WEBP, atau PDF maksimal 8 MB.");return;}
    pending.current=null; setFile(selected); setError("");
  };
  const submit = async event => {
    event.preventDefault(); if (busy || !file) return;
    setBusy(true);setError("");
    try {
      if (!pending.current) pending.current=crypto.randomUUID();
      const body=new FormData();body.append("payment_request_id",pending.current);body.append("file",file);
      if (!report.payment_amount) body.append("payment_amount",amount);
      try { await api.post(`/laporan/${report.id}/payment`,body,{timeout:120000}); }
      catch (failure) {
        const {data}=await api.get(`/laporan/${report.id}`);
        if (data.payment_request_id!==pending.current || !data.payment_proof) throw failure;
      }
      setFile(null);pending.current=null;toast.success("Bukti pembayaran tersimpan. Laporan selesai.");onSaved?.();
    } catch (failure) {setError(errMsg(failure));}
    finally {setBusy(false);}
  };
  return <section id={admin?"pembayaran":undefined} className={compact?"mt-3 space-y-2 border-t border-slate-100 pt-3":"brand-panel rounded-2xl border border-slate-200 p-5 space-y-3"}>
    <div className="flex items-center justify-between gap-3 flex-wrap"><h2 className="font-heading font-semibold text-slate-800">Pembayaran Tim</h2>{!compact&&<PaymentBadge status={report.payment_status} />}</div>
    <p className="text-xl font-bold text-slate-900" data-testid="payment-amount">{rupiah(report.payment_amount)}</p>
    <p className="text-xs text-slate-500">Nominal total untuk satu penugasan/tim.</p>
    {report.payment_proof ? <a href={fileUrl(report.payment_proof.url)} target="_blank" rel="noopener noreferrer" className="block break-all rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800" data-testid="payment-proof-link">Buka bukti pembayaran · {report.payment_proof.name || "Bukti pembayaran"}</a> : admin ? <form onSubmit={submit} className="space-y-3">
      {!report.payment_amount && <label className="block text-sm">Nominal pembayaran tim (Rp)<Input type="number" min="0.01" step="0.01" max="999999999999.99" required value={amount} onChange={event=>{setAmount(event.target.value);pending.current=null;}} data-testid="payment-legacy-amount" /></label>}
      <label className="block text-sm text-slate-700">Unggah bukti pembayaran<Input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" disabled={busy} onChange={choose} data-testid="payment-proof-input" className="mt-2" /></label>
      <p className="text-xs text-slate-500">JPG, PNG, WEBP, atau PDF, maksimal 8 MB. Setelah tersimpan, status menjadi Selesai.</p>
      {file && <p className="text-sm text-blue-700 break-all">{file.name}</p>}
      {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
      <Button type="submit" disabled={busy || !file} data-testid="payment-save">{busy ? "Menyimpan…" : "Simpan Bukti Pembayaran"}</Button>
    </form> : <p className="text-sm text-slate-600">{report.payment_status ? "Bukti pembayaran belum diunggah oleh admin." : "Data pembayaran laporan lama belum dicatat oleh admin."}</p>}
  </section>;
}
