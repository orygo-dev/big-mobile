import { useEffect, useState } from "react";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import EmptyState from "@/components/EmptyState";
import { Building2, Plus, Pencil, Ban, Loader2, Search } from "lucide-react";
import { toast } from "sonner";

const EMPTY = { nama_perusahaan: "", alamat: "", telepon: "", email: "", nama_pic: "", nomor_pic: "", status: "aktif" };

export default function Klien() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/clients", { params: { search: search || undefined } })
      .then(({ data }) => setItems(data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  };
  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [search]);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (c) => { setEditing(c); setForm({ ...EMPTY, ...c }); setOpen(true); };

  const save = async () => {
    if (!form.nama_perusahaan.trim()) { toast.error("Nama perusahaan wajib diisi"); return; }
    setSaving(true);
    try {
      if (editing) await api.put(`/clients/${editing.id}`, form);
      else await api.post("/clients", form);
      toast.success(editing ? "Klien diperbarui" : "Klien ditambahkan");
      setOpen(false); load();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const deactivate = async (c) => {
    try { await api.patch(`/clients/${c.id}/deactivate`); toast.success("Klien dinonaktifkan"); load(); }
    catch (e) { toast.error(errMsg(e)); }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold text-slate-900">Klien</h1>
          <p className="text-sm text-slate-500 mt-1">Kelola data perusahaan klien.</p>
        </div>
        <Button onClick={openNew} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="admin-add-klien-button">
          <Plus className="w-4 h-4 mr-1" /> Tambah Klien
        </Button>
      </div>

      <div className="relative max-w-sm">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari nama klien..." className="pl-9 rounded-xl" data-testid="klien-search-input" />
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : items.length === 0 ? (
          <EmptyState icon={Building2} title="Belum ada klien" desc="Tambahkan klien pertama Anda." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider">
                <tr className="text-left">
                  <th className="px-5 py-3 font-medium">Perusahaan</th>
                  <th className="px-3 py-3 font-medium">PIC</th>
                  <th className="px-3 py-3 font-medium">Kontak</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id} className="border-t border-slate-50 hover:bg-slate-50/50" data-testid={`klien-row-${c.id}`}>
                    <td className="px-5 py-3">
                      <p className="font-semibold text-slate-800">{c.nama_perusahaan}</p>
                      <p className="text-xs text-slate-400">{c.alamat}</p>
                    </td>
                    <td className="px-3 py-3 text-slate-600">{c.nama_pic || "-"}<br /><span className="text-xs text-slate-400">{c.nomor_pic}</span></td>
                    <td className="px-3 py-3 text-slate-600">{c.telepon || "-"}<br /><span className="text-xs text-slate-400">{c.email}</span></td>
                    <td className="px-3 py-3">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${c.status === "aktif" ? "bg-emerald-100 text-emerald-800 border-emerald-200" : "bg-slate-100 text-slate-600 border-slate-200"}`}>
                        {c.status === "aktif" ? "Aktif" : "Nonaktif"}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right whitespace-nowrap">
                      <button onClick={() => openEdit(c)} className="text-slate-500 hover:text-blue-600 p-1.5" data-testid={`klien-edit-${c.id}`}><Pencil className="w-4 h-4" /></button>
                      {c.status === "aktif" && (
                        <button onClick={() => deactivate(c)} className="text-slate-500 hover:text-rose-600 p-1.5" data-testid={`klien-deactivate-${c.id}`}><Ban className="w-4 h-4" /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg" data-testid="klien-dialog">
          <DialogHeader><DialogTitle className="font-heading">{editing ? "Edit Klien" : "Tambah Klien"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
            <div className="sm:col-span-2"><Label>Nama Perusahaan *</Label><Input value={form.nama_perusahaan} onChange={set("nama_perusahaan")} className="mt-1.5 rounded-xl" data-testid="klien-nama-input" /></div>
            <div className="sm:col-span-2"><Label>Alamat</Label><Textarea value={form.alamat} onChange={set("alamat")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Telepon</Label><Input value={form.telepon} onChange={set("telepon")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Email</Label><Input value={form.email} onChange={set("email")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Nama PIC</Label><Input value={form.nama_pic} onChange={set("nama_pic")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Nomor PIC</Label><Input value={form.nomor_pic} onChange={set("nomor_pic")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger className="mt-1.5 rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="aktif">Aktif</SelectItem><SelectItem value="nonaktif">Nonaktif</SelectItem></SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="rounded-xl">Batal</Button>
            <Button onClick={save} disabled={saving} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="klien-save-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
