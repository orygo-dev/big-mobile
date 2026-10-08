import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { errMsg, fileUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/StatusBadge";
import { SK_STATUS, ACCOUNT_STATUS, formatDate } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import { ArrowLeft, Loader2, Car, Pencil, FileText, Download, Upload } from "lucide-react";
import { toast } from "sonner";

export default function SuratKuasaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [sk, setSk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [skForm, setSkForm] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(() => {
    setLoading(true);
    api.get(`/surat-kuasa/${id}`).then(({ data }) => setSk(data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  }, [id]);
  useEffect(() => { load(); }, [load]);

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

  const uploadFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.type !== "application/pdf") { toast.error("File Surat Kuasa harus PDF"); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(`/surat-kuasa/${id}/file`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Dokumen Surat Kuasa diunggah"); load();
    } catch (err) { toast.error(errMsg(err)); } finally { setUploading(false); }
  };

  if (loading || !sk) return <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>;

  return (
    <div className="space-y-5 animate-fade-in">
      <button onClick={() => navigate("/admin/surat-kuasa")} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800" data-testid="sk-detail-back">
        <ArrowLeft className="w-4 h-4" /> Kembali
      </button>

      <div className="brand-panel rounded-2xl border border-slate-200 p-6">
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
          <div><p className="text-xs text-slate-400">Total Unit</p><p className="font-medium text-slate-700">{sk.total_akun}</p></div>
        </div>
        {sk.keterangan && <p className="text-sm text-slate-500 mt-4 bg-slate-50 rounded-xl p-3">{sk.keterangan}</p>}

        {/* Dokumen Surat Kuasa */}
        <div className="mt-5 pt-5 border-t border-slate-100 flex items-center gap-2 flex-wrap">
          <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={uploadFile} data-testid="sk-file-input" />
          {sk.file_url ? (
            <>
              <Button variant="outline" onClick={() => setPreviewOpen(true)} className="rounded-xl" data-testid="sk-preview-button"><FileText className="w-4 h-4 mr-1 text-blue-600" /> Preview Surat Kuasa</Button>
              <a href={fileUrl(sk.file_url)} target="_blank" rel="noreferrer" download className="inline-flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-xl" data-testid="sk-download-button"><Download className="w-4 h-4" /> Download</a>
              <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={uploading} className="rounded-xl" data-testid="sk-replace-button">{uploading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />} Ganti Dokumen</Button>
            </>
          ) : (
            <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={uploading} className="rounded-xl" data-testid="sk-upload-button">{uploading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />} Unggah Dokumen PDF</Button>
          )}
        </div>
      </div>

      <div>
        <h2 className="font-heading text-lg font-semibold text-slate-800">Daftar Unit pada Surat Kuasa ini</h2>
        <p className="text-sm text-slate-400 mt-0.5">Tambah unit baru dilakukan di menu Kontrak &amp; Unit.</p>
      </div>

      <div className="brand-panel rounded-2xl border border-slate-200 overflow-hidden">
        {sk.accounts.length === 0 ? (
          <EmptyState icon={Car} title="Belum ada unit pada Surat Kuasa ini" desc="Tambahkan unit dari menu Kontrak & Unit." />
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

      {/* Preview dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="sm:max-w-3xl" data-testid="sk-preview-dialog">
          <DialogHeader><DialogTitle className="font-heading text-base">Preview Surat Kuasa {sk.nomor}</DialogTitle></DialogHeader>
          {sk.file_url && <iframe title="Surat Kuasa" src={fileUrl(sk.file_url)} className="w-full h-[70vh] rounded-xl border border-slate-200" />}
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
