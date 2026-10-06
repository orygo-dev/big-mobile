import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/StatusBadge";
import { SK_STATUS, formatDate } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import { FileText, Plus, Loader2, Search, ChevronRight } from "lucide-react";
import { toast } from "sonner";

const EMPTY = { nomor: "", client_id: "", tanggal_surat: "", tanggal_berlaku: "", tanggal_berakhir: "", keterangan: "", status: "aktif", file_url: "" };

export default function SuratKuasa() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/surat-kuasa", { params: { search: search || undefined } })
      .then(({ data }) => setItems(data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  };
  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [search]);
  useEffect(() => { api.get("/clients").then(({ data }) => setClients(data.filter((c) => c.status === "aktif"))); }, []);

  const save = async () => {
    if (!form.nomor.trim() || !form.client_id) { toast.error("Nomor dan klien wajib diisi"); return; }
    setSaving(true);
    try {
      await api.post("/surat-kuasa", form);
      toast.success("Surat Kuasa ditambahkan");
      setOpen(false); setForm(EMPTY); load();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold text-slate-900">Surat Kuasa</h1>
          <p className="text-sm text-slate-500 mt-1">Kelola surat kuasa dari klien dan akun/unit terkait.</p>
        </div>
        <Button onClick={() => { setForm(EMPTY); setOpen(true); }} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="admin-add-surat-kuasa-button">
          <Plus className="w-4 h-4 mr-1" /> Tambah Surat Kuasa
        </Button>
      </div>

      <div className="relative max-w-sm">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari nomor surat kuasa..." className="pl-9 rounded-xl" data-testid="sk-search-input" />
      </div>

      {loading ? (
        <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200"><EmptyState icon={FileText} title="Belum ada Surat Kuasa" desc="Tambahkan surat kuasa pertama." /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map((sk) => (
            <button key={sk.id} onClick={() => navigate(`/admin/surat-kuasa/${sk.id}`)} data-testid={`sk-card-${sk.id}`}
              className="text-left bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md hover:border-blue-300 transition-all group">
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center"><FileText className="w-5 h-5 text-blue-600" /></div>
                <StatusBadge map={SK_STATUS} value={sk.status} />
              </div>
              <p className="font-mono text-sm font-semibold text-slate-800 mt-3">{sk.nomor}</p>
              <p className="text-sm text-slate-500 mt-0.5">{sk.client_name}</p>
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-100">
                <span className="text-xs text-slate-400">{sk.total_akun} akun · berlaku s/d {formatDate(sk.tanggal_berakhir)}</span>
                <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-blue-600" />
              </div>
            </button>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg" data-testid="sk-dialog">
          <DialogHeader><DialogTitle className="font-heading">Tambah Surat Kuasa</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
            <div className="sm:col-span-2"><Label>Nomor Surat Kuasa *</Label><Input value={form.nomor} onChange={set("nomor")} placeholder="SK/FIN/2026/0101" className="mt-1.5 rounded-xl" data-testid="sk-nomor-input" /></div>
            <div className="sm:col-span-2"><Label>Klien *</Label>
              <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                <SelectTrigger className="mt-1.5 rounded-xl" data-testid="sk-client-select"><SelectValue placeholder="Pilih klien" /></SelectTrigger>
                <SelectContent>{clients.map((c) => <SelectItem key={c.id} value={c.id}>{c.nama_perusahaan}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Tanggal Surat</Label><Input type="date" value={form.tanggal_surat} onChange={set("tanggal_surat")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Tanggal Berlaku</Label><Input type="date" value={form.tanggal_berlaku} onChange={set("tanggal_berlaku")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Tanggal Berakhir</Label><Input type="date" value={form.tanggal_berakhir} onChange={set("tanggal_berakhir")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger className="mt-1.5 rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="aktif">Aktif</SelectItem><SelectItem value="berakhir">Berakhir</SelectItem><SelectItem value="dicabut">Dicabut</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="sm:col-span-2"><Label>Keterangan</Label><Textarea value={form.keterangan} onChange={set("keterangan")} className="mt-1.5 rounded-xl" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="rounded-xl">Batal</Button>
            <Button onClick={save} disabled={saving} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="sk-save-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
