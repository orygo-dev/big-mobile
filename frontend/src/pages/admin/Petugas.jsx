import { useEffect, useState } from "react";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import EmptyState from "@/components/EmptyState";
import { Users, Plus, Pencil, Loader2 } from "lucide-react";
import { toast } from "sonner";

const EMPTY = { name: "", email: "", password: "", telepon: "", tim: "", status: "aktif" };

export default function Petugas() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/petugas").then(({ data }) => setItems(data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (p) => { setEditing(p); setForm({ ...EMPTY, ...p, password: "" }); setOpen(true); };

  const save = async () => {
    if (!form.name.trim() || !form.email.trim()) { toast.error("Nama dan email wajib diisi"); return; }
    if (!editing && !form.password) { toast.error("Password wajib untuk petugas baru"); return; }
    setSaving(true);
    try {
      if (editing) await api.put(`/petugas/${editing.id}`, form);
      else await api.post("/petugas", form);
      toast.success(editing ? "Petugas diperbarui" : "Petugas ditambahkan");
      setOpen(false); load();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold text-slate-900">Petugas</h1>
          <p className="text-sm text-slate-500 mt-1">Kelola akun petugas lapangan.</p>
        </div>
        <Button onClick={openNew} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="admin-add-petugas-button">
          <Plus className="w-4 h-4 mr-1" /> Tambah Petugas
        </Button>
      </div>

      {loading ? (
        <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200"><EmptyState icon={Users} title="Belum ada petugas" desc="Tambahkan petugas lapangan." /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map((p) => (
            <div key={p.id} className="bg-white rounded-2xl border border-slate-200 p-5" data-testid={`petugas-card-${p.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-full bg-blue-600 text-white flex items-center justify-center font-semibold">{p.name?.[0]?.toUpperCase()}</div>
                  <div>
                    <p className="font-semibold text-slate-800">{p.name}</p>
                    <p className="text-xs text-slate-400 font-mono">{p.petugas_code}</p>
                  </div>
                </div>
                <button onClick={() => openEdit(p)} className="text-slate-400 hover:text-blue-600 p-1" data-testid={`petugas-edit-${p.id}`}><Pencil className="w-4 h-4" /></button>
              </div>
              <div className="mt-4 space-y-1 text-sm text-slate-600">
                <p>{p.email}</p>
                <p>{p.telepon || "-"} · {p.tim || "-"}</p>
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${p.status === "aktif" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{p.status === "aktif" ? "Aktif" : "Nonaktif"}</span>
                  <span className="text-xs text-slate-400">{p.total_tugas} tugas aktif</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md" data-testid="petugas-dialog">
          <DialogHeader><DialogTitle className="font-heading">{editing ? "Edit Petugas" : "Tambah Petugas"}</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div><Label>Nama Lengkap *</Label><Input value={form.name} onChange={set("name")} className="mt-1.5 rounded-xl" data-testid="petugas-nama-input" /></div>
            <div><Label>Email *</Label><Input type="email" value={form.email} onChange={set("email")} className="mt-1.5 rounded-xl" data-testid="petugas-email-input" /></div>
            <div><Label>Password {editing && <span className="text-xs text-slate-400">(kosongkan jika tidak diubah)</span>}</Label><Input type="password" value={form.password} onChange={set("password")} className="mt-1.5 rounded-xl" data-testid="petugas-password-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Telepon</Label><Input value={form.telepon} onChange={set("telepon")} className="mt-1.5 rounded-xl" /></div>
              <div><Label>Tim / Area</Label><Input value={form.tim} onChange={set("tim")} className="mt-1.5 rounded-xl" /></div>
            </div>
            <div><Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger className="mt-1.5 rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="aktif">Aktif</SelectItem><SelectItem value="nonaktif">Nonaktif</SelectItem></SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="rounded-xl">Batal</Button>
            <Button onClick={save} disabled={saving} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="petugas-save-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
