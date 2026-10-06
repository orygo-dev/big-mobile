import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/StatusBadge";
import { SK_STATUS, ACCOUNT_STATUS, formatDate } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import { ArrowLeft, Plus, Loader2, Car, Pencil } from "lucide-react";
import { toast } from "sonner";

const EMPTY_ACC = {
  nomor_kontrak: "", nama_debitur: "", nik: "", telepon: "", alamat: "",
  provinsi: "", kabupaten: "", kecamatan: "", kelurahan: "", nomor_polisi: "",
  jenis_kendaraan: "", merk: "", model: "", tahun: "", warna: "",
  nomor_rangka: "", nomor_mesin: "", keterangan: "", latitude: "", longitude: "",
};

export default function SuratKuasaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [sk, setSk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [accOpen, setAccOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_ACC);
  const [saving, setSaving] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [skForm, setSkForm] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    api.get(`/surat-kuasa/${id}`).then(({ data }) => setSk(data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const saveAcc = async () => {
    if (!form.nomor_kontrak.trim() || !form.nama_debitur.trim()) { toast.error("Nomor kontrak dan nama debitur wajib"); return; }
    setSaving(true);
    try {
      await api.post("/akun", {
        ...form,
        client_id: sk.client_id, surat_kuasa_id: sk.id,
        latitude: form.latitude ? parseFloat(form.latitude) : null,
        longitude: form.longitude ? parseFloat(form.longitude) : null,
      });
      toast.success("Akun/unit ditambahkan");
      setAccOpen(false); setForm(EMPTY_ACC); load();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const saveSk = async () => {
    setSaving(true);
    try {
      await api.put(`/surat-kuasa/${id}`, {
        nomor: skForm.nomor, client_id: skForm.client_id, tanggal_surat: skForm.tanggal_surat,
        tanggal_berlaku: skForm.tanggal_berlaku, tanggal_berakhir: skForm.tanggal_berakhir,
        keterangan: skForm.keterangan, status: skForm.status, file_url: skForm.file_url || "",
      });
      toast.success("Surat Kuasa diperbarui"); setEditOpen(false); load();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  if (loading || !sk) return <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>;

  return (
    <div className="space-y-5 animate-fade-in">
      <button onClick={() => navigate("/admin/surat-kuasa")} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800" data-testid="sk-detail-back">
        <ArrowLeft className="w-4 h-4" /> Kembali
      </button>

      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-heading text-2xl font-bold text-slate-900 font-mono">{sk.nomor}</h1>
              <StatusBadge map={SK_STATUS} value={sk.status} />
            </div>
            <p className="text-slate-500 mt-1">{sk.client_name}</p>
          </div>
          <Button variant="outline" onClick={() => { setSkForm({ ...sk }); setEditOpen(true); }} className="rounded-xl" data-testid="sk-edit-button">
            <Pencil className="w-4 h-4 mr-1" /> Edit
          </Button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5 pt-5 border-t border-slate-100 text-sm">
          <div><p className="text-xs text-slate-400">Tanggal Surat</p><p className="font-medium text-slate-700">{formatDate(sk.tanggal_surat)}</p></div>
          <div><p className="text-xs text-slate-400">Berlaku</p><p className="font-medium text-slate-700">{formatDate(sk.tanggal_berlaku)}</p></div>
          <div><p className="text-xs text-slate-400">Berakhir</p><p className="font-medium text-slate-700">{formatDate(sk.tanggal_berakhir)}</p></div>
          <div><p className="text-xs text-slate-400">Total Akun</p><p className="font-medium text-slate-700">{sk.total_akun}</p></div>
        </div>
        {sk.keterangan && <p className="text-sm text-slate-500 mt-4 bg-slate-50 rounded-xl p-3">{sk.keterangan}</p>}
      </div>

      <div className="flex items-center justify-between">
        <h2 className="font-heading text-lg font-semibold text-slate-800">Daftar Akun / Unit</h2>
        <Button onClick={() => { setForm(EMPTY_ACC); setAccOpen(true); }} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="sk-add-akun-button">
          <Plus className="w-4 h-4 mr-1" /> Tambah Akun
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        {sk.accounts.length === 0 ? (
          <EmptyState icon={Car} title="Belum ada akun pada Surat Kuasa ini" desc="Tambahkan akun/unit untuk surat kuasa ini." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-400 uppercase tracking-wider">
                <tr className="text-left">
                  <th className="px-5 py-3 font-medium">Debitur</th>
                  <th className="px-3 py-3 font-medium">No. Kontrak</th>
                  <th className="px-3 py-3 font-medium">No. Polisi</th>
                  <th className="px-3 py-3 font-medium">Unit</th>
                  <th className="px-3 py-3 font-medium">Wilayah</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {sk.accounts.map((a) => (
                  <tr key={a.id} className="border-t border-slate-50 hover:bg-slate-50/50">
                    <td className="px-5 py-3 font-medium text-slate-800">{a.nama_debitur}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-600">{a.nomor_kontrak}</td>
                    <td className="px-3 py-3 font-mono text-slate-700">{a.nomor_polisi}</td>
                    <td className="px-3 py-3 text-slate-600">{a.merk} {a.model}</td>
                    <td className="px-3 py-3 text-slate-500 text-xs">{a.kabupaten}, {a.provinsi}</td>
                    <td className="px-5 py-3"><StatusBadge map={ACCOUNT_STATUS} value={a.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add account dialog */}
      <Dialog open={accOpen} onOpenChange={setAccOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="akun-dialog">
          <DialogHeader><DialogTitle className="font-heading">Tambah Akun / Unit</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
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
            <div><Label>Latitude (opsional)</Label><Input value={form.latitude} onChange={set("latitude")} className="mt-1.5 rounded-xl" /></div>
            <div><Label>Longitude (opsional)</Label><Input value={form.longitude} onChange={set("longitude")} className="mt-1.5 rounded-xl" /></div>
            <div className="sm:col-span-2"><Label>Keterangan Admin</Label><Textarea value={form.keterangan} onChange={set("keterangan")} className="mt-1.5 rounded-xl" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAccOpen(false)} className="rounded-xl">Batal</Button>
            <Button onClick={saveAcc} disabled={saving} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="akun-save-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit SK dialog */}
      {skForm && (
        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogContent className="sm:max-w-lg" data-testid="sk-edit-dialog">
            <DialogHeader><DialogTitle className="font-heading">Edit Surat Kuasa</DialogTitle></DialogHeader>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
              <div className="sm:col-span-2"><Label>Nomor</Label><Input value={skForm.nomor} onChange={(e) => setSkForm({ ...skForm, nomor: e.target.value })} className="mt-1.5 rounded-xl" /></div>
              <div><Label>Tanggal Berlaku</Label><Input type="date" value={skForm.tanggal_berlaku || ""} onChange={(e) => setSkForm({ ...skForm, tanggal_berlaku: e.target.value })} className="mt-1.5 rounded-xl" /></div>
              <div><Label>Tanggal Berakhir</Label><Input type="date" value={skForm.tanggal_berakhir || ""} onChange={(e) => setSkForm({ ...skForm, tanggal_berakhir: e.target.value })} className="mt-1.5 rounded-xl" /></div>
              <div><Label>Status</Label>
                <Select value={skForm.status} onValueChange={(v) => setSkForm({ ...skForm, status: v })}>
                  <SelectTrigger className="mt-1.5 rounded-xl"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="aktif">Aktif</SelectItem><SelectItem value="berakhir">Berakhir</SelectItem><SelectItem value="dicabut">Dicabut</SelectItem></SelectContent>
                </Select>
              </div>
              <div className="sm:col-span-2"><Label>Keterangan</Label><Textarea value={skForm.keterangan || ""} onChange={(e) => setSkForm({ ...skForm, keterangan: e.target.value })} className="mt-1.5 rounded-xl" /></div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditOpen(false)} className="rounded-xl">Batal</Button>
              <Button onClick={saveSk} disabled={saving} className="rounded-xl bg-blue-600 hover:bg-blue-700">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
