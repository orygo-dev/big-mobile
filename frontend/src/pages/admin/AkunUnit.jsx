import DeleteDataButton from "@/components/DeleteDataButton";
import { useEffect, useState, useCallback } from "react";
import api, { errMsg, fileUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/StatusBadge";
import { ACCOUNT_STATUS } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import PenugasanDialog from "@/components/PenugasanDialog";
import { Car, Loader2, Search, ClipboardList, ChevronLeft, ChevronRight, Plus, FileText, Download, Upload, Pencil } from "lucide-react";
import { toast } from "sonner";

const STATUS_OPTS = Object.keys(ACCOUNT_STATUS);
const EMPTY_ACC = {
  nomor_kontrak: "", nama_debitur: "", nik: "", telepon: "", alamat: "",
  provinsi: "", kabupaten: "", kecamatan: "", kelurahan: "", nomor_polisi: "",
  jenis_kendaraan: "", merk: "", model: "", tahun: "", warna: "",
  nomor_rangka: "", nomor_mesin: "", stnk_name: "", keterangan: "",
  client_id: "", surat_kuasa_id: "",
};

export default function AkunUnit() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, limit: 10 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [clientFilter, setClientFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [provinsi, setProvinsi] = useState("");
  const [page, setPage] = useState(1);
  const [clients, setClients] = useState([]);
  const [skList, setSkList] = useState([]);
  const [assignId, setAssignId] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  // Add unit
  const [editing, setEditing] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_ACC);
  const [skFile, setSkFile] = useState(null);
  const [saving, setSaving] = useState(false);
  // Document preview
  const [preview, setPreview] = useState(null); // { url, label }

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
  useEffect(() => { api.get("/clients").then(({ data }) => setClients(data)).catch((e) => toast.error(errMsg(e))); }, []);
  useEffect(() => { api.get("/surat-kuasa").then(({ data }) => setSkList(data)).catch((e) => toast.error(errMsg(e))); }, []);
  useEffect(() => { setPage(1); }, [search, clientFilter, statusFilter, provinsi]);

  const openAssign = (id) => { setAssignId(id); setDialogOpen(true); };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const skForClient = skList.filter((s) => s.client_id === form.client_id);

  const saveUnit = async () => {
    if (!form.client_id) { toast.error("Pilih Pemberi Kuasa"); return; }
    if (!form.surat_kuasa_id) { toast.error("Pilih Surat Kuasa"); return; }
    if (!form.nomor_kontrak.trim() || !form.nama_debitur.trim()) { toast.error("Nomor kontrak dan nama debitur wajib"); return; }
    if (skFile && skFile.type !== "application/pdf") { toast.error("File Surat Kuasa harus PDF"); return; }
    setSaving(true);
    try {
      if (editing) await api.put(`/akun/${editing.id}`, form);
      else await api.post("/akun", { ...form, latitude: null, longitude: null });
      if (skFile) {
        const fd = new FormData();
        fd.append("file", skFile);
        try { await api.post(`/surat-kuasa/${form.surat_kuasa_id}/file`, fd); }
        catch (error) { toast.error(`Unit sudah tersimpan, tetapi dokumen gagal diunggah: ${errMsg(error)}`); }
      }
      toast.success(editing ? "Unit diperbarui" : "Unit ditambahkan");
      setAddOpen(false); setForm(EMPTY_ACC); setSkFile(null); load();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.limit));

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="font-heading text-2xl font-bold text-slate-900">Kontrak & Unit</h1>
          <p className="text-sm text-slate-500 mt-1">Tambah unit, kelola dokumen Surat Kuasa, dan tugaskan unit ke petugas.</p>
        </div>
        <Button onClick={() => { setEditing(null); setForm(EMPTY_ACC); setSkFile(null); setAddOpen(true); }} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="akun-add-unit-button">
          <Plus className="w-4 h-4 mr-1" /> Tambah Unit Baru
        </Button>
      </div>

      <div className="brand-panel rounded-2xl border border-slate-200 p-4 flex flex-col lg:flex-row gap-3 lg:items-center">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari debitur, kontrak, polisi..." className="pl-9 rounded-xl" data-testid="akun-search-input" />
        </div>
        <Select value={clientFilter} onValueChange={setClientFilter}>
          <SelectTrigger className="rounded-xl lg:w-48" data-testid="akun-client-filter"><SelectValue placeholder="Pemberi Kuasa" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Semua Pemberi Kuasa</SelectItem>{clients.map((c) => <SelectItem key={c.id} value={c.id}>{c.nama_perusahaan}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="rounded-xl lg:w-48" data-testid="akun-status-filter"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Semua Status</SelectItem>{STATUS_OPTS.map((s) => <SelectItem key={s} value={s}>{ACCOUNT_STATUS[s].label}</SelectItem>)}</SelectContent>
        </Select>
        <Input value={provinsi} onChange={(e) => setProvinsi(e.target.value)} placeholder="Wilayah/Provinsi" className="rounded-xl lg:w-40" data-testid="akun-wilayah-filter" />
      </div>

      <div className="brand-panel rounded-2xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : data.items.length === 0 ? (
          <EmptyState icon={Car} title="Tidak ada data kontrak/unit" desc="Klik Tambah Unit Baru untuk menambahkan unit." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider">
                <tr className="text-left">
                  <th className="px-5 py-3 font-medium">Debitur</th>
                  <th className="px-3 py-3 font-medium">No. Kontrak</th>
                  <th className="px-3 py-3 font-medium">No. Polisi</th>
                  <th className="px-3 py-3 font-medium">Unit</th>
                  <th className="px-3 py-3 font-medium">Pemberi Kuasa</th>
                  <th className="px-3 py-3 font-medium">Dok. Surat Kuasa</th>
                  <th className="px-3 py-3 font-medium">Petugas</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((a) => (
                  <tr key={a.id} className="border-t border-slate-50 hover:bg-slate-50/50" data-testid={`akun-row-${a.id}`}>
                    <td className="px-5 py-3 font-medium text-slate-800">{a.nama_debitur}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-600">{a.nomor_kontrak}</td>
                    <td className="px-3 py-3 font-mono text-slate-700">{a.nomor_polisi}</td>
                    <td className="px-3 py-3 text-slate-600">{a.merk} {a.model}</td>
                    <td className="px-3 py-3 text-slate-500 text-xs">{a.client_name}</td>
                    <td className="px-3 py-3">
                      {a.surat_kuasa_file ? (
                        <button onClick={() => setPreview({ url: a.surat_kuasa_file, label: a.surat_kuasa_nomor })}
                          className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs font-medium" data-testid={`akun-doc-${a.id}`}>
                          <FileText className="w-3.5 h-3.5" /> Lihat
                        </button>
                      ) : <span className="text-xs text-slate-300">-</span>}
                    </td>
                    <td className="px-3 py-3 text-slate-600 text-xs">{a.petugas_name || <span className="text-slate-300">-</span>}</td>
                    <td className="px-3 py-3"><StatusBadge map={ACCOUNT_STATUS} value={a.status} /></td>
                    <td className="px-5 py-3 text-right whitespace-nowrap">
                      <button aria-label="Edit kontrak/unit" data-testid={`akun-edit-${a.id}`} className="p-1.5 text-blue-600" onClick={() => { setEditing(a); setForm({ ...EMPTY_ACC, ...a }); setSkFile(null); setAddOpen(true); }}><Pencil className="w-4 h-4" /></button>
                      <DeleteDataButton endpoint={`/akun/${a.id}`} name={`${a.nomor_kontrak} — ${a.nama_debitur}`} onDeleted={() => { if (data.items.length === 1 && page > 1) setPage(page - 1); else load(); }} testId={`akun-delete-${a.id}`} />
                      {a.status === "BELUM_DITUGASKAN" ? (
                        <Button size="sm" onClick={() => openAssign(a.id)} className="rounded-lg bg-blue-600 hover:bg-blue-700 h-8" data-testid={`akun-tugaskan-${a.id}`}>
                          <ClipboardList className="w-3.5 h-3.5 mr-1" /> Tugaskan
                        </Button>
                      ) : (
                        <span className="text-xs text-slate-400">{a.petugas_name ? "Ditugaskan" : "-"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">Total {data.total} unit</p>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-xl" data-testid="akun-prev-page"><ChevronLeft className="w-4 h-4" /></Button>
          <span className="text-sm text-slate-600">Hal {page} / {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="rounded-xl" data-testid="akun-next-page"><ChevronRight className="w-4 h-4" /></Button>
        </div>
      </div>

      {/* Add Unit dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="akun-add-dialog">
          <DialogHeader><DialogTitle className="font-heading">{editing ? "Edit Kontrak & Unit" : "Tambah Unit Baru"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
            <div><Label>Pemberi Kuasa / Leasing *</Label>
              <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v, surat_kuasa_id: "" })}>
                <SelectTrigger className="mt-1.5 rounded-xl" data-testid="akun-add-client-select"><SelectValue placeholder="Pilih pemberi kuasa" /></SelectTrigger>
                <SelectContent>{clients.filter((c) => c.status === "aktif" || c.id === form.client_id).map((c) => <SelectItem key={c.id} value={c.id}>{c.nama_perusahaan}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Surat Kuasa *</Label>
              <Select value={form.surat_kuasa_id} onValueChange={(v) => setForm({ ...form, surat_kuasa_id: v })} disabled={!form.client_id}>
                <SelectTrigger className="mt-1.5 rounded-xl" data-testid="akun-add-sk-select"><SelectValue placeholder={form.client_id ? "Pilih surat kuasa" : "Pilih pemberi kuasa dulu"} /></SelectTrigger>
                <SelectContent>
                  {skForClient.length === 0 && <div className="px-3 py-2 text-sm text-slate-400">Tidak ada surat kuasa</div>}
                  {skForClient.map((s) => <SelectItem key={s.id} value={s.id}>{s.nomor}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div><Label>Nomor Kontrak *</Label><Input value={form.nomor_kontrak} onChange={set("nomor_kontrak")} className="mt-1.5 rounded-xl" data-testid="akun-kontrak-input" /></div>
            <div><Label>Nama Debitur *</Label><Input value={form.nama_debitur} onChange={set("nama_debitur")} className="mt-1.5 rounded-xl" data-testid="akun-debitur-input" /></div>
            <div><Label>NIK (opsional)</Label><Input value={form.nik} onChange={set("nik")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Nomor Telepon</Label><Input value={form.telepon} onChange={set("telepon")} className="mt-1.5 rounded-xl" /></div>
            <div className="sm:col-span-2"><Label>Alamat</Label><Textarea value={form.alamat} onChange={set("alamat")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Provinsi</Label><Input value={form.provinsi} onChange={set("provinsi")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Kabupaten/Kota</Label><Input value={form.kabupaten} onChange={set("kabupaten")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Kecamatan</Label><Input value={form.kecamatan} onChange={set("kecamatan")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Kelurahan/Desa</Label><Input value={form.kelurahan} onChange={set("kelurahan")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Nomor Polisi</Label><Input value={form.nomor_polisi} onChange={set("nomor_polisi")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Jenis Kendaraan</Label><Input value={form.jenis_kendaraan} onChange={set("jenis_kendaraan")} placeholder="Mobil / Motor" className="mt-1.5 rounded-xl" /></div>
            <div><Label>Merk</Label><Input value={form.merk} onChange={set("merk")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Model / Tipe</Label><Input value={form.model} onChange={set("model")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Tahun</Label><Input value={form.tahun} onChange={set("tahun")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Warna</Label><Input value={form.warna} onChange={set("warna")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>No. Rangka (opsional)</Label><Input value={form.nomor_rangka} onChange={set("nomor_rangka")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>No. Mesin (opsional)</Label><Input value={form.nomor_mesin} onChange={set("nomor_mesin")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>STNK atas nama</Label><Input value={form.stnk_name} onChange={set("stnk_name")} placeholder="Kosongkan = nama debitur" className="mt-1.5 rounded-xl" /></div>
            <div className="sm:col-span-2"><Label>Keterangan Admin</Label><Textarea value={form.keterangan} onChange={set("keterangan")} className="mt-1.5 rounded-xl" /></div>
            <div className="sm:col-span-2">
              <Label>Dokumen Surat Kuasa (PDF, opsional)</Label>
              <div className="mt-1.5 flex items-center gap-2">
                <label className="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white cursor-pointer hover:bg-slate-50 text-sm text-slate-600">
                  <Upload className="w-4 h-4" /> {skFile ? "Ganti file" : "Pilih file PDF"}
                  <input type="file" accept="application/pdf" className="hidden" data-testid="akun-sk-file-input"
                    onChange={(e) => setSkFile(e.target.files?.[0] || null)} />
                </label>
                {skFile && <span className="text-xs text-slate-500 truncate max-w-[200px]">{skFile.name}</span>}
              </div>
              <p className="text-[11px] text-slate-400 mt-1">File akan dilampirkan ke Surat Kuasa yang dipilih (maks 8MB).</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)} className="rounded-xl">Batal</Button>
            <Button onClick={saveUnit} disabled={saving} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="akun-save-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Document preview dialog */}
      <Dialog open={!!preview} onOpenChange={(v) => { if (!v) setPreview(null); }}>
        <DialogContent className="sm:max-w-3xl" data-testid="akun-doc-preview">
          <DialogHeader><DialogTitle className="font-heading text-base">Dokumen Surat Kuasa {preview?.label}</DialogTitle></DialogHeader>
          {preview && (
            <div className="space-y-3">
              <iframe title="Surat Kuasa" src={fileUrl(preview.url)} className="w-full h-[70vh] rounded-xl border border-slate-200" />
              <div className="flex justify-end">
                <a href={fileUrl(preview.url)} target="_blank" rel="noreferrer" download
                  className="inline-flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-xl" data-testid="akun-doc-download">
                  <Download className="w-4 h-4" /> Download PDF
                </a>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <PenugasanDialog open={dialogOpen} onOpenChange={setDialogOpen} accountId={assignId}
        onSuccess={() => { load(); }} />
    </div>
  );
}
