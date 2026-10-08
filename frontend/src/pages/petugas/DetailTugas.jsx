import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { errMsg, fileUrl } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { ACCOUNT_STATUS } from "@/lib/constants";
import { ArrowLeft, MapPin, Navigation, FileText, Phone, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function DetailTugas() {
  const { accountId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/my/tugas/${accountId}`).then(({ data }) => setData(data))
      .catch((e) => { toast.error(errMsg(e)); navigate("/app/tugas"); }).finally(() => setLoading(false));
  }, [accountId, navigate]);

  if (loading || !data) return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>;
  const a = data.account;

  const openMaps = () => {
    const url = a.latitude != null && a.longitude != null ? `https://www.google.com/maps?q=${a.latitude},${a.longitude}` : `https://www.google.com/maps/search/${encodeURIComponent(a.alamat)}`;
    window.open(url, "_blank");
  };

  const Row = ({ label, value, mono }) => (
    <div className="flex justify-between gap-4 py-2 border-b border-slate-50 last:border-0">
      <span className="text-xs text-slate-400">{label}</span>
      <span className={`text-sm text-slate-700 text-right ${mono ? "font-mono" : "font-medium"}`}>{value || "-"}</span>
    </div>
  );

  return (
    <div>
      <div className="brand-hero text-white px-5 pt-8 pb-5 sticky top-0 z-10">
        <button onClick={() => navigate("/app/tugas")} className="flex items-center gap-1.5 text-sm text-slate-300 mb-3" data-testid="detail-tugas-back"><ArrowLeft className="w-4 h-4" /> Kembali</button>
        <div className="flex items-center justify-between">
          <div><h1 className="font-heading text-xl font-bold">{a.nama_debitur}</h1><p className="text-slate-400 text-xs font-mono mt-0.5">{data.letter_nomor}</p></div>
          <StatusBadge map={ACCOUNT_STATUS} value={a.status} />
        </div>
      </div>

      <div className="px-4 mt-4 space-y-4">
        <div className="brand-panel rounded-2xl p-4 shadow-sm border border-slate-100">
          <h2 className="font-heading font-semibold text-slate-800 text-sm mb-2">Informasi Tugas</h2>
          <Row label="No. Surat Tugas" value={data.letter_nomor} mono />
          <Row label="No. Surat Kuasa" value={data.surat_kuasa_nomor} mono />
          <Row label="Klien" value={data.client_name} />
          <Row label="No. Kontrak" value={a.nomor_kontrak} mono />
          <Row label="Mulai berlaku" value={data.valid_from} />
          <Row label="Berlaku sampai" value={data.valid_until || "Tidak ditentukan"} />
        </div>

        <div className="brand-panel rounded-2xl p-4 shadow-sm border border-slate-100">
          <h2 className="font-heading font-semibold text-slate-800 text-sm mb-2">Data Unit</h2>
          <Row label="No. Polisi" value={a.nomor_polisi} mono />
          <Row label="Jenis Unit" value={a.jenis_kendaraan} />
          <Row label="Merk / Tipe" value={`${a.merk} ${a.model}`} />
          <Row label="Tahun" value={a.tahun} />
          <Row label="Warna" value={a.warna} />
        </div>

        <div className="brand-panel rounded-2xl p-4 shadow-sm border border-slate-100">
          <h2 className="font-heading font-semibold text-slate-800 text-sm mb-2">Kontak & Alamat</h2>
          <div className="flex items-start gap-2 text-sm text-slate-700 py-2">
            <MapPin className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
            <span>{a.alamat}, {a.kelurahan}, {a.kecamatan}, {a.kabupaten}, {a.provinsi}</span>
          </div>
          {a.telepon && <div className="flex items-center gap-2 text-sm text-slate-700 py-1"><Phone className="w-4 h-4 text-slate-400" /> {a.telepon}</div>}
        </div>

        {data.catatan_admin && (
          <div className="bg-amber-50 border border-amber-100 rounded-2xl p-4">
            <p className="text-xs font-semibold text-amber-800 mb-1">Catatan Admin</p>
            <p className="text-sm text-amber-900">{data.catatan_admin}</p>
          </div>
        )}

        <button onClick={openMaps} className="w-full flex items-center justify-center gap-2 bg-white border border-slate-200 text-slate-700 font-semibold py-3.5 rounded-2xl active:scale-[0.98] transition-transform" data-testid="detail-tugas-maps-button">
          <Navigation className="w-4 h-4 text-blue-600" /> Buka Maps
        </button>
        {data.surat_kuasa_file && <a href={fileUrl(data.surat_kuasa_file)} target="_blank" rel="noopener noreferrer" className="w-full flex items-center justify-center gap-2 rounded-2xl border border-blue-200 bg-blue-50 py-3.5 font-semibold text-blue-700" data-testid="detail-tugas-surat-kuasa"><FileText className="h-4 w-4" />Buka Surat Kuasa</a>}
        <button onClick={() => navigate(`/app/chat/${data.assignment_id}`)} className="w-full rounded-2xl bg-blue-600 text-white py-3.5 font-semibold" data-testid="detail-tugas-chat">Chat dengan admin</button>
      </div>

      <div className="brand-footer fixed bottom-0 w-full max-w-[460px] p-4 z-50">
        {data.existing_report ? (
          <div className="w-full bg-emerald-50 border border-emerald-200 text-emerald-700 font-semibold py-3.5 rounded-2xl text-center text-sm">
            ✓ Laporan sudah dikirim
          </div>
        ) : data.can_report === false ? (
          <p className="bg-amber-50 text-amber-800 rounded-2xl p-3 text-sm text-center">{data.blocked_reason}</p>
        ) : (
          <button onClick={() => navigate(`/app/tugas/${accountId}/laporan`)}
            className="brand-action w-full font-semibold py-3.5 rounded-2xl active:scale-[0.98] transition-all flex items-center justify-center gap-2"
            data-testid="detail-tugas-buat-laporan-button">
            <FileText className="w-5 h-5" /> Buat Laporan
          </button>
        )}
      </div>
    </div>
  );
}
