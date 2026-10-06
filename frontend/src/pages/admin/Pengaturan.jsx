import { useEffect, useState } from "react";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { formatDateTime } from "@/lib/constants";
import { Building2, ScrollText, Loader2, Pencil } from "lucide-react";
import { toast } from "sonner";

export default function Pengaturan() {
  const [company, setCompany] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = () => {
    api.get("/company").then(({ data }) => setCompany(data)).catch(() => {});
    api.get("/audit-logs").then(({ data }) => setLogs(data)).catch(() => {});
  };
  useEffect(() => { Promise.resolve(load()).finally(() => setLoading(false)); }, []);

  const openEdit = () => {
    setForm({
      nama: company.nama || "", alamat: company.alamat || "", telepon: company.telepon || "",
      email: company.email || "", city: company.city || "", director_name: company.director_name || "",
      director_position: company.director_position || "DIREKTUR", company_code: company.company_code || "",
      number_format: company.number_format || "{sequence}/{company_code}/{month_name}/{year}", logo: company.logo || "",
    });
    setOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try { const { data } = await api.put("/company", form); setCompany(data); toast.success("Profil perusahaan diperbarui"); setOpen(false); }
    catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-5 animate-fade-in max-w-4xl">
      <div>
        <h1 className="font-heading text-2xl font-bold text-slate-900">Pengaturan</h1>
        <p className="text-sm text-slate-500 mt-1">Informasi perusahaan, format nomor surat, dan log aktivitas.</p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2"><Building2 className="w-5 h-5 text-blue-600" /><h2 className="font-heading font-semibold text-slate-800">Profil Perusahaan</h2></div>
          {company && <Button variant="outline" size="sm" onClick={openEdit} className="rounded-xl" data-testid="company-edit-button"><Pencil className="w-4 h-4 mr-1" /> Edit</Button>}
        </div>
        {company ? (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div><dt className="text-xs text-slate-400">Nama</dt><dd className="font-medium text-slate-700">{company.nama}</dd></div>
            <div><dt className="text-xs text-slate-400">Kota/Kedudukan</dt><dd className="text-slate-700">{company.city || "-"}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs text-slate-400">Alamat</dt><dd className="text-slate-700">{company.alamat}</dd></div>
            <div><dt className="text-xs text-slate-400">Telepon</dt><dd className="text-slate-700">{company.telepon}</dd></div>
            <div><dt className="text-xs text-slate-400">Email</dt><dd className="text-slate-700">{company.email}</dd></div>
            <div><dt className="text-xs text-slate-400">Nama Direktur</dt><dd className="text-slate-700">{company.director_name || "-"}</dd></div>
            <div><dt className="text-xs text-slate-400">Jabatan</dt><dd className="text-slate-700">{company.director_position || "-"}</dd></div>
            <div><dt className="text-xs text-slate-400">Kode Perusahaan</dt><dd className="font-mono text-slate-700">{company.company_code || "-"}</dd></div>
            <div><dt className="text-xs text-slate-400">Format Nomor Surat</dt><dd className="font-mono text-xs text-slate-700">{company.number_format || "-"}</dd></div>
          </dl>
        ) : <Loader2 className="w-5 h-5 animate-spin text-blue-600" />}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5">
        <div className="flex items-center gap-2 mb-4"><ScrollText className="w-5 h-5 text-blue-600" /><h2 className="font-heading font-semibold text-slate-800">Audit Log</h2></div>
        {loading ? (
          <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
        ) : logs.length === 0 ? (
          <p className="text-sm text-slate-400">Belum ada aktivitas tercatat.</p>
        ) : (
          <div className="overflow-x-auto -mx-5">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-slate-400 uppercase tracking-wider border-b border-slate-100">
                <th className="px-5 py-2 font-medium">Waktu</th><th className="px-3 py-2 font-medium">Pengguna</th>
                <th className="px-3 py-2 font-medium">Aktivitas</th><th className="px-5 py-2 font-medium">IP</th>
              </tr></thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-b border-slate-50">
                    <td className="px-5 py-2.5 text-slate-500 whitespace-nowrap">{formatDateTime(l.timestamp)}</td>
                    <td className="px-3 py-2.5 text-slate-700">{l.user_name || "-"}</td>
                    <td className="px-3 py-2.5 text-slate-600">{l.activity} <span className="text-xs text-slate-400">({l.entity})</span></td>
                    <td className="px-5 py-2.5 text-slate-400 font-mono text-xs">{l.ip_address || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {form && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto" data-testid="company-dialog">
            <DialogHeader><DialogTitle className="font-heading">Edit Profil Perusahaan</DialogTitle></DialogHeader>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
              <div className="sm:col-span-2"><Label>Nama Perusahaan</Label><Input value={form.nama} onChange={set("nama")} className="mt-1.5 rounded-xl" data-testid="company-nama-input" /></div>
              <div className="sm:col-span-2"><Label>Alamat</Label><Textarea value={form.alamat} onChange={set("alamat")} className="mt-1.5 rounded-xl" /></div>
              <div><Label>Kota/Kedudukan</Label><Input value={form.city} onChange={set("city")} className="mt-1.5 rounded-xl" data-testid="company-city-input" /></div>
              <div><Label>Telepon</Label><Input value={form.telepon} onChange={set("telepon")} className="mt-1.5 rounded-xl" /></div>
              <div><Label>Email</Label><Input value={form.email} onChange={set("email")} className="mt-1.5 rounded-xl" /></div>
              <div><Label>Nama Direktur</Label><Input value={form.director_name} onChange={set("director_name")} className="mt-1.5 rounded-xl" data-testid="company-director-input" /></div>
              <div><Label>Jabatan Pemberi Tugas</Label><Input value={form.director_position} onChange={set("director_position")} className="mt-1.5 rounded-xl" /></div>
              <div><Label>Kode Perusahaan</Label><Input value={form.company_code} onChange={set("company_code")} placeholder="HSN" className="mt-1.5 rounded-xl" data-testid="company-code-input" /></div>
              <div className="sm:col-span-2"><Label>Format Nomor Surat</Label><Input value={form.number_format} onChange={set("number_format")} className="mt-1.5 rounded-xl font-mono text-xs" data-testid="company-format-input" />
                <p className="text-[11px] text-slate-400 mt-1">Placeholder: {"{sequence}"}, {"{company_code}"}, {"{month_name}"}, {"{year}"}</p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)} className="rounded-xl">Batal</Button>
              <Button onClick={save} disabled={saving} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="company-save-button">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
