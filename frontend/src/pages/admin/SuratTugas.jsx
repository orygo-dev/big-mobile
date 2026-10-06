import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/StatusBadge";
import { LETTER_STATUS, formatDate } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FileCheck2, Loader2, Search, Printer, MoreVertical, QrCode } from "lucide-react";
import { toast } from "sonner";

export default function SuratTugas() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const load = () => {
    setLoading(true);
    api.get("/surat-tugas", { params: { search: search || undefined, status: statusFilter !== "all" ? statusFilter : undefined } })
      .then(({ data }) => setItems(data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  };
  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [search, statusFilter]);

  const changeStatus = async (l, status) => {
    try { await api.patch(`/surat-tugas/${l.id}/status`, { status }); toast.success("Status diperbarui"); load(); }
    catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="font-heading text-2xl font-bold text-slate-900">Surat Tugas</h1>
        <p className="text-sm text-slate-500 mt-1">Daftar surat tugas yang telah diterbitkan.</p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari nomor surat tugas..." className="pl-9 rounded-xl" data-testid="st-search-input" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="rounded-xl sm:w-44" data-testid="st-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Semua Status</SelectItem>
            {Object.keys(LETTER_STATUS).map((s) => <SelectItem key={s} value={s}>{LETTER_STATUS[s].label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : items.length === 0 ? (
          <EmptyState icon={FileCheck2} title="Belum ada Surat Tugas" desc="Surat tugas akan muncul setelah penugasan dibuat." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider">
                <tr className="text-left">
                  <th className="px-5 py-3 font-medium">No. Surat Tugas</th>
                  <th className="px-3 py-3 font-medium">Petugas</th>
                  <th className="px-3 py-3 font-medium">Klien</th>
                  <th className="px-3 py-3 font-medium">Unit</th>
                  <th className="px-3 py-3 font-medium">Tanggal</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {items.map((l) => (
                  <tr key={l.id} className="border-t border-slate-50 hover:bg-slate-50/50" data-testid={`st-row-${l.id}`}>
                    <td className="px-5 py-3 font-mono text-xs font-semibold text-slate-800">{l.nomor}</td>
                    <td className="px-3 py-3 text-slate-700">{l.petugas_name}</td>
                    <td className="px-3 py-3 text-slate-600">{l.client_name}</td>
                    <td className="px-3 py-3 text-slate-600">{l.accounts?.length || 0}</td>
                    <td className="px-3 py-3 text-slate-500">{formatDate(l.tanggal)}</td>
                    <td className="px-3 py-3"><StatusBadge map={LETTER_STATUS} value={l.status} /></td>
                    <td className="px-5 py-3 text-right whitespace-nowrap">
                      <button onClick={() => navigate(`/admin/surat-tugas/${l.id}/print`)} className="text-slate-500 hover:text-blue-600 p-1.5" title="Cetak" data-testid={`st-print-${l.id}`}>
                        <Printer className="w-4 h-4" />
                      </button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button className="text-slate-500 hover:text-slate-800 p-1.5" data-testid={`st-menu-${l.id}`}><MoreVertical className="w-4 h-4" /></button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => navigate(`/admin/surat-tugas/${l.id}/print`)}><Printer className="w-4 h-4 mr-2" /> Cetak / Download</DropdownMenuItem>
                          <DropdownMenuItem onClick={() => window.open(`/verifikasi/${l.id}`, "_blank")}><QrCode className="w-4 h-4 mr-2" /> Halaman Verifikasi</DropdownMenuItem>
                          <DropdownMenuItem onClick={() => changeStatus(l, "selesai")}>Tandai Selesai</DropdownMenuItem>
                          <DropdownMenuItem onClick={() => changeStatus(l, "dibatalkan")} className="text-rose-600">Batalkan</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
