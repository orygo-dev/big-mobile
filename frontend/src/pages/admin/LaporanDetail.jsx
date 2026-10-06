import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { errMsg, fileUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/StatusBadge";
import { REPORT_STATUS, formatDateTime } from "@/lib/constants";
import MapView from "@/components/MapView";
import { ArrowLeft, Loader2, MapPin, ExternalLink, User, Save, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function LaporanDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [r, setR] = useState(null);
  const [loading, setLoading] = useState(true);
  const [review, setReview] = useState("");
  const [saving, setSaving] = useState(false);
  const [lightbox, setLightbox] = useState(null);

  const load = () => {
    api.get(`/laporan/${id}`).then(({ data }) => { setR(data); setReview(data.catatan_admin || ""); })
      .catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  const submitReview = async () => {
    setSaving(true);
    try { await api.patch(`/laporan/${id}/review`, { catatan_admin: review }); toast.success("Catatan review tersimpan"); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  if (loading || !r) return <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>;
  const acc = r.account || {};
  const mapsUrl = r.latitude ? `https://www.google.com/maps?q=${r.latitude},${r.longitude}` : null;

  return (
    <div className="space-y-5 animate-fade-in max-w-5xl">
      <button onClick={() => navigate("/admin/laporan")} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800" data-testid="laporan-detail-back">
        <ArrowLeft className="w-4 h-4" /> Kembali
      </button>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold text-slate-900">Detail Laporan</h1>
          <p className="text-sm text-slate-500 mt-1 font-mono">{r.letter_nomor}</p>
        </div>
        <StatusBadge map={REPORT_STATUS} value={r.status} dataTestid="laporan-detail-status" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="space-y-5">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h2 className="font-heading font-semibold text-slate-800 mb-3">Data Tugas</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <div><dt className="text-xs text-slate-400">Debitur</dt><dd className="font-medium text-slate-700">{acc.nama_debitur}</dd></div>
              <div><dt className="text-xs text-slate-400">No. Kontrak</dt><dd className="font-mono text-slate-700">{acc.nomor_kontrak}</dd></div>
              <div><dt className="text-xs text-slate-400">No. Polisi</dt><dd className="font-mono text-slate-700">{acc.nomor_polisi}</dd></div>
              <div><dt className="text-xs text-slate-400">Kendaraan</dt><dd className="text-slate-700">{acc.merk} {acc.model}</dd></div>
              <div><dt className="text-xs text-slate-400">Klien</dt><dd className="text-slate-700">{r.client_name}</dd></div>
              <div><dt className="text-xs text-slate-400">Warna</dt><dd className="text-slate-700">{acc.warna}</dd></div>
              <div className="col-span-2"><dt className="text-xs text-slate-400">Alamat</dt><dd className="text-slate-700">{acc.alamat}</dd></div>
            </dl>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <div className="flex items-center gap-2 mb-3"><User className="w-4 h-4 text-blue-600" /><h2 className="font-heading font-semibold text-slate-800">Petugas & Catatan</h2></div>
            <p className="text-sm text-slate-700 font-medium">{r.petugas_name}</p>
            <p className="text-xs text-slate-400 mt-0.5">{formatDateTime(r.created_at)}</p>
            <p className="text-sm text-slate-600 mt-3 bg-slate-50 rounded-xl p-3">{r.catatan}</p>
            {r.lokasi_alasan && <p className="text-xs text-amber-700 mt-2 bg-amber-50 rounded-lg p-2">Alasan lokasi: {r.lokasi_alasan}</p>}
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h2 className="font-heading font-semibold text-slate-800 mb-3">Review Admin</h2>
            <Textarea value={review} onChange={(e) => setReview(e.target.value)} placeholder="Tambahkan catatan/review untuk laporan ini..." className="rounded-xl" data-testid="laporan-review-input" />
            <Button onClick={submitReview} disabled={saving} className="mt-3 rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="laporan-review-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" /> Simpan Review</>}
            </Button>
            {r.reviewed && <p className="text-xs text-emerald-600 mt-2 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Sudah direview</p>}
          </div>
        </div>

        <div className="space-y-5">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h2 className="font-heading font-semibold text-slate-800 mb-3">Foto Bukti ({r.photos?.length || 0})</h2>
            {r.photos?.length ? (
              <div className="grid grid-cols-2 gap-3">
                {r.photos.map((p, i) => (
                  <button key={i} onClick={() => setLightbox(fileUrl(p.url))} className="rounded-xl overflow-hidden border border-slate-200 aspect-square" data-testid={`laporan-photo-${i}`}>
                    <img src={fileUrl(p.url)} alt={`Bukti ${i + 1}`} className="w-full h-full object-cover hover:scale-105 transition-transform" />
                  </button>
                ))}
              </div>
            ) : <p className="text-sm text-slate-400">Tidak ada foto.</p>}
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-blue-600" /><h2 className="font-heading font-semibold text-slate-800">Lokasi</h2></div>
              {mapsUrl && <a href={mapsUrl} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline flex items-center gap-1" data-testid="laporan-maps-link">Google Maps <ExternalLink className="w-3 h-3" /></a>}
            </div>
            <MapView lat={r.latitude} lng={r.longitude} label={acc.nama_debitur} />
            {r.latitude && <p className="text-xs text-slate-400 mt-2 font-mono">{r.latitude}, {r.longitude}</p>}
          </div>
        </div>
      </div>

      {lightbox && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6" onClick={() => setLightbox(null)}>
          <img src={lightbox} alt="Foto bukti" className="max-w-full max-h-full rounded-xl" />
        </div>
      )}
    </div>
  );
}
