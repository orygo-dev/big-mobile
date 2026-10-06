import { useEffect, useState, useCallback } from "react";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/StatusBadge";
import { ACCOUNT_STATUS } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import PenugasanDialog from "@/components/PenugasanDialog";
import { Car, Loader2, Search, ClipboardList, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";

const STATUS_OPTS = Object.keys(ACCOUNT_STATUS);

export default function AkunUnit() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, limit: 10 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [clientFilter, setClientFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [provinsi, setProvinsi] = useState("");
  const [page, setPage] = useState(1);
  const [clients, setClients] = useState([]);
  const [selected, setSelected] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api.get("/akun", { params: {
      search: search || undefined,
      client_id: clientFilter !== "all" ? clientFilter : undefined,
      status: statusFilter !== "all" ? statusFilter : undefined,
      provinsi: provinsi || undefined,
      page, limit: 10,
    }}).then(({ data }) => setData(data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  }, [search, clientFilter, statusFilter, provinsi, page]);

  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [load]);
  useEffect(() => { api.get("/clients").then(({ data }) => setClients(data)); }, []);
  useEffect(() => { setPage(1); }, [search, clientFilter, statusFilter, provinsi]);

  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const assignable = data.items.filter((a) => a.status === "BELUM_DITUGASKAN").map((a) => a.id);
  const allChecked = assignable.length > 0 && assignable.every((id) => selected.includes(id));
  const toggleAll = () => setSelected(allChecked ? selected.filter((id) => !assignable.includes(id)) : [...new Set([...selected, ...assignable])]);

  const totalPages = Math.max(1, Math.ceil(data.total / data.limit));

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="font-heading text-2xl font-bold text-slate-900">Data Akun / Unit</h1>
        <p className="text-sm text-slate-500 mt-1">Pilih beberapa akun untuk membuat penugasan.</p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-4 flex flex-col lg:flex-row gap-3 lg:items-center">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari debitur, kontrak, polisi..." className="pl-9 rounded-xl" data-testid="akun-search-input" />
        </div>
        <Select value={clientFilter} onValueChange={setClientFilter}>
          <SelectTrigger className="rounded-xl lg:w-48" data-testid="akun-client-filter"><SelectValue placeholder="Klien" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Semua Klien</SelectItem>{clients.map((c) => <SelectItem key={c.id} value={c.id}>{c.nama_perusahaan}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="rounded-xl lg:w-48" data-testid="akun-status-filter"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Semua Status</SelectItem>{STATUS_OPTS.map((s) => <SelectItem key={s} value={s}>{ACCOUNT_STATUS[s].label}</SelectItem>)}</SelectContent>
        </Select>
        <Input value={provinsi} onChange={(e) => setProvinsi(e.target.value)} placeholder="Wilayah/Provinsi" className="rounded-xl lg:w-40" data-testid="akun-wilayah-filter" />
      </div>

      {selected.length > 0 && (
        <div className="bg-blue-600 text-white rounded-2xl p-4 flex items-center justify-between animate-fade-in">
          <p className="font-medium text-sm">{selected.length} akun dipilih</p>
          <Button onClick={() => setDialogOpen(true)} className="rounded-xl bg-white text-blue-700 hover:bg-blue-50" data-testid="akun-buat-penugasan-button">
            <ClipboardList className="w-4 h-4 mr-1" /> Buat Penugasan
          </Button>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : data.items.length === 0 ? (
          <EmptyState icon={Car} title="Tidak ada data akun/unit" desc="Coba ubah filter atau tambahkan akun dari Surat Kuasa." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider">
                <tr className="text-left">
                  <th className="px-5 py-3 w-10"><Checkbox checked={allChecked} onCheckedChange={toggleAll} data-testid="akun-select-all" /></th>
                  <th className="px-3 py-3 font-medium">Debitur</th>
                  <th className="px-3 py-3 font-medium">No. Kontrak</th>
                  <th className="px-3 py-3 font-medium">No. Polisi</th>
                  <th className="px-3 py-3 font-medium">Unit</th>
                  <th className="px-3 py-3 font-medium">Klien</th>
                  <th className="px-3 py-3 font-medium">Wilayah</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((a) => (
                  <tr key={a.id} className="border-t border-slate-50 hover:bg-slate-50/50" data-testid={`akun-row-${a.id}`}>
                    <td className="px-5 py-3">
                      <Checkbox checked={selected.includes(a.id)} onCheckedChange={() => toggle(a.id)}
                        disabled={a.status !== "BELUM_DITUGASKAN"} data-testid={`akun-check-${a.id}`} />
                    </td>
                    <td className="px-3 py-3 font-medium text-slate-800">{a.nama_debitur}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-600">{a.nomor_kontrak}</td>
                    <td className="px-3 py-3 font-mono text-slate-700">{a.nomor_polisi}</td>
                    <td className="px-3 py-3 text-slate-600">{a.merk} {a.model}</td>
                    <td className="px-3 py-3 text-slate-500 text-xs">{a.client_name}</td>
                    <td className="px-3 py-3 text-slate-500 text-xs">{a.kabupaten}, {a.provinsi}</td>
                    <td className="px-5 py-3"><StatusBadge map={ACCOUNT_STATUS} value={a.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">Total {data.total} akun</p>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-xl" data-testid="akun-prev-page"><ChevronLeft className="w-4 h-4" /></Button>
          <span className="text-sm text-slate-600">Hal {page} / {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="rounded-xl" data-testid="akun-next-page"><ChevronRight className="w-4 h-4" /></Button>
        </div>
      </div>

      <PenugasanDialog open={dialogOpen} onOpenChange={setDialogOpen} accountIds={selected}
        onSuccess={() => { setSelected([]); load(); }} />
    </div>
  );
}
