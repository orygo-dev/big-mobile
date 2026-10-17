import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatDateTime } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import { FileSearch, Loader2, Search, Eye, ImageIcon } from "lucide-react";
import {Button} from "@/components/ui/button";
import AdminReportDialog from "@/components/AdminReportDialog";
import {PaymentBadge, PAYMENT_STATUS, rupiah} from "@/components/ReportPayment";

export default function LaporanPetugas() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [petugasFilter, setPetugasFilter] = useState("all");
  const [tanggal, setTanggal] = useState("");
  const [petugasList, setPetugasList] = useState([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api.get("/laporan", { params: {
      search: search || undefined,
      payment_status: statusFilter !== "all" ? statusFilter : undefined,
      petugas_id: petugasFilter !== "all" ? petugasFilter : undefined,
      tanggal: tanggal || undefined,
    }}).then(({ data }) => setItems(data)).catch((e) => setError(errMsg(e))).finally(() => setLoading(false));
  }, [search, statusFilter, petugasFilter, tanggal]);

  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [load]);
  useEffect(() => { api.get("/petugas").then(({ data }) => setPetugasList(data)); }, []);

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
        <h1 className="font-heading text-2xl font-bold text-slate-900">Laporan Lapangan</h1>
        <p className="text-sm text-slate-500 mt-1">Laporan yang dibuat admin, bukti lapangan, dan pembayaran per penugasan/tim.</p>
        </div>
        <Button onClick={()=>setOpen(true)} data-testid="laporan-create-button">Laporan Baru</Button>
      </div>

      <div className="brand-panel rounded-2xl border border-slate-200 p-4 flex flex-col lg:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari debitur, polisi, surat tugas..." className="pl-9 rounded-xl" data-testid="laporan-search-input" />
        </div>
        <Select value={petugasFilter} onValueChange={setPetugasFilter}>
          <SelectTrigger className="rounded-xl lg:w-44" data-testid="laporan-petugas-filter"><SelectValue placeholder="Petugas" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Semua Petugas</SelectItem>{petugasList.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="rounded-xl lg:w-44" data-testid="laporan-status-filter"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Semua Pembayaran</SelectItem>{Object.keys(PAYMENT_STATUS).map((s) => <SelectItem key={s} value={s}>{PAYMENT_STATUS[s].label}</SelectItem>)}</SelectContent>
        </Select>
        <Input type="date" value={tanggal} onChange={(e) => setTanggal(e.target.value)} className="rounded-xl lg:w-40" data-testid="laporan-tanggal-filter" />
      </div>

      <div className="brand-panel rounded-2xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : error ? <div role="alert" className="p-5 text-sm"><p>{error}</p><Button onClick={load} variant="outline" className="mt-3">Coba lagi</Button></div> : items.length === 0 ? (
          <EmptyState icon={FileSearch} title="Belum ada laporan" desc="Klik Laporan Baru untuk membuat laporan penugasan dan mencatat pembayaran tim." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider">
                <tr className="text-left">
                  <th className="px-5 py-3 font-medium">Tanggal Dibuat</th>
                  <th className="px-3 py-3 font-medium">Tanggal Selesai</th>
                  <th className="px-3 py-3 font-medium">Petugas</th>
                  <th className="px-3 py-3 font-medium">Surat Tugas</th>
                  <th className="px-3 py-3 font-medium">Debitur</th>
                  <th className="px-3 py-3 font-medium">No. Polisi</th>
                  <th className="px-3 py-3 font-medium">Status Pembayaran</th>
                  <th className="px-3 py-3 font-medium">Nominal Tim</th>
                  <th className="px-3 py-3 font-medium">Foto</th>
                  <th className="px-5 py-3 font-medium text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-t border-slate-50 hover:bg-slate-50/50" data-testid={`laporan-row-${r.id}`}>
                    <td className="px-5 py-3 text-slate-500 whitespace-nowrap">{formatDateTime(r.created_at)}</td>
                    <td className="px-3 py-3 text-slate-500 whitespace-nowrap">{r.payment_status === "SELESAI" && r.payment_recorded_at ? formatDateTime(r.payment_recorded_at) : ""}</td>
                    <td className="px-3 py-3 font-medium text-slate-700">{r.petugas_name}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-600">{r.letter_nomor}</td>
                    <td className="px-3 py-3 text-slate-700">{r.nama_debitur}</td>
                    <td className="px-3 py-3 font-mono text-slate-700">{r.nomor_polisi}</td>
                    <td className="px-3 py-3"><PaymentBadge status={r.payment_status} /></td>
                    <td className="px-3 py-3 whitespace-nowrap">{rupiah(r.payment_amount)}</td>
                    <td className="px-3 py-3">
                      {r.photos?.length ? <span className="inline-flex items-center gap-1 text-xs text-slate-600"><ImageIcon className="w-3.5 h-3.5" />{r.photos.length}</span> : <span className="text-xs text-slate-400">-</span>}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button onClick={() => navigate(`/admin/laporan/${r.id}`)} className="text-blue-600 hover:text-blue-800 p-1.5" data-testid={`laporan-view-${r.id}`}><Eye className="w-4 h-4" /></button>
                      {!r.payment_proof && <button onClick={()=>navigate(`/admin/laporan/${r.id}#pembayaran`)} className="text-xs font-semibold text-orange-700 ml-2" data-testid={`laporan-pay-${r.id}`}>Upload Bukti Pembayaran</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <AdminReportDialog open={open} onOpenChange={setOpen} onCreated={report=>{setOpen(false);navigate(`/admin/laporan/${report.id}`);}} />
    </div>
  );
}
