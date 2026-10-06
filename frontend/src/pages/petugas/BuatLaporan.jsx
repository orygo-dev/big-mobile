import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/StatusBadge";
import { REPORT_STATUS } from "@/lib/constants";
import {
  ArrowLeft, Camera, Plus, Trash2, MapPin, Loader2, CheckCircle2,
  AlertTriangle, RefreshCw, Send,
} from "lucide-react";
import { toast } from "sonner";

const STATUS_OPTIONS = [
  "UNIT_DITEMUKAN", "TIDAK_DITEMUKAN", "ALAMAT_TIDAK_SESUAI",
  "PINDAH_ALAMAT", "UNIT_TIDAK_ADA", "LAINNYA",
];

function pad(n) { return String(n).padStart(2, "0"); }
const MONTHS = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];

export default function BuatLaporan() {
  const { accountId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);

  const [status, setStatus] = useState("");
  const [catatan, setCatatan] = useState("");
  const [coords, setCoords] = useState(null); // {lat, lng}
  const [gpsState, setGpsState] = useState("idle"); // idle | loading | ok | denied
  const [gpsReason, setGpsReason] = useState("");
  const [now] = useState(new Date());
  const [photos, setPhotos] = useState([]); // [{blob, url}]
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    api.get(`/my/tugas/${accountId}`).then(({ data }) => {
      setData(data);
      if (data.existing_report) { toast.info("Laporan untuk tugas ini sudah dikirim."); navigate(`/app/tugas/${accountId}`); }
    }).catch((e) => { toast.error(errMsg(e)); navigate("/app/tugas"); }).finally(() => setLoading(false));
    captureGps();
    // eslint-disable-next-line
  }, [accountId]);

  const captureGps = () => {
    if (!navigator.geolocation) { setGpsState("denied"); return; }
    setGpsState("loading");
    navigator.geolocation.getCurrentPosition(
      (pos) => { setCoords({ lat: +pos.coords.latitude.toFixed(6), lng: +pos.coords.longitude.toFixed(6) }); setGpsState("ok"); },
      () => { setGpsState("denied"); },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const watermarkText = () => {
    const d = now;
    return [
      `${pad(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())} WIB`,
      `Petugas: ${user?.name}`,
      data?.letter_nomor || "",
      coords ? `${coords.lat}, ${coords.lng}` : "Lokasi tidak tersedia",
    ];
  };

  const processPhoto = (file) => new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const maxW = 1280;
      const scale = Math.min(1, maxW / img.width);
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, w, h);
      const lines = watermarkText();
      const fs = Math.max(14, Math.round(w * 0.028));
      const pad2 = Math.round(fs * 0.5);
      const boxH = lines.length * (fs + 6) + pad2 * 2;
      ctx.fillStyle = "rgba(15,23,42,0.6)";
      ctx.fillRect(0, h - boxH, w, boxH);
      ctx.fillStyle = "#ffffff";
      ctx.font = `600 ${fs}px Inter, sans-serif`;
      ctx.textBaseline = "top";
      lines.forEach((ln, i) => ctx.fillText(ln, pad2, h - boxH + pad2 + i * (fs + 6)));
      canvas.toBlob((blob) => resolve({ blob, url: URL.createObjectURL(blob) }), "image/jpeg", 0.85);
    };
    img.src = URL.createObjectURL(file);
  });

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (photos.length >= 5) { toast.error("Maksimal 5 foto"); return; }
    const processed = await processPhoto(file);
    setPhotos((p) => [...p, processed]);
  };

  const removePhoto = (i) => setPhotos((p) => p.filter((_, idx) => idx !== i));

  const validateStep1 = () => {
    if (!status) { toast.error("Pilih hasil kunjungan"); return false; }
    if (catatan.trim().length < 10) { toast.error("Catatan wajib minimal 10 karakter"); return false; }
    if (gpsState !== "ok" && gpsReason.trim().length < 5) { toast.error("Aktifkan GPS atau berikan alasan (min 5 karakter)"); return false; }
    return true;
  };

  const next = () => {
    if (step === 1) {
      if (!validateStep1()) return;
      if (status === "UNIT_DITEMUKAN") setStep(2);
      else setStep(3);
    } else if (step === 2) {
      if (status === "UNIT_DITEMUKAN" && photos.length < 1) { toast.error("Foto bukti wajib minimal 1"); return; }
      setStep(3);
    }
  };
  const back = () => { if (step === 3 && status !== "UNIT_DITEMUKAN") setStep(1); else setStep(step - 1); };

  const submit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("assignment_letter_id", data.letter_id);
      fd.append("account_id", accountId);
      fd.append("status", status);
      fd.append("catatan", catatan);
      if (coords) { fd.append("latitude", coords.lat); fd.append("longitude", coords.lng); }
      if (gpsState !== "ok") fd.append("lokasi_alasan", gpsReason);
      photos.forEach((p, i) => fd.append("photos", p.blob, `foto_${i + 1}.jpg`));
      await api.post("/laporan", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setDone(true);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !data) return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>;

  if (done) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-6 text-center animate-fade-in">
        <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center mb-4"><CheckCircle2 className="w-11 h-11 text-emerald-600" /></div>
        <h1 className="font-heading text-xl font-bold text-slate-900">Laporan berhasil dikirim.</h1>
        <p className="text-sm text-slate-500 mt-1">Terima kasih, laporan Anda telah tersimpan.</p>
        <button onClick={() => navigate("/app")} className="mt-6 bg-blue-600 text-white font-semibold px-6 py-3 rounded-2xl" data-testid="laporan-done-home">Kembali ke Beranda</button>
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-28">
      <div className="bg-slate-900 text-white px-5 pt-8 pb-5 rounded-b-3xl sticky top-0 z-10">
        <button onClick={() => step === 1 ? navigate(`/app/tugas/${accountId}`) : back()} className="flex items-center gap-1.5 text-sm text-slate-300 mb-3" data-testid="laporan-back">
          <ArrowLeft className="w-4 h-4" /> {step === 1 ? "Batal" : "Sebelumnya"}
        </button>
        <h1 className="font-heading text-xl font-bold">Buat Laporan</h1>
        <p className="text-slate-400 text-xs mt-0.5">{data.account.nama_debitur} · {data.account.nomor_polisi}</p>
        <div className="flex gap-2 mt-4">
          {[1, 2, 3].map((s) => <div key={s} className={`h-1.5 flex-1 rounded-full ${step >= s ? "bg-blue-500" : "bg-slate-700"}`} />)}
        </div>
      </div>

      <div className="px-4 mt-5">
        {step === 1 && (
          <div className="space-y-4 animate-fade-in">
            <div>
              <h2 className="font-heading font-semibold text-slate-800 mb-3">Hasil Kunjungan</h2>
              <div className="grid grid-cols-2 gap-2.5">
                {STATUS_OPTIONS.map((s) => (
                  <button key={s} onClick={() => setStatus(s)} data-testid={`laporan-status-${s}`}
                    className={`text-left px-3 py-3 rounded-2xl border text-sm font-medium transition-all ${status === s ? "border-blue-600 bg-blue-50 text-blue-700 ring-2 ring-blue-100" : "border-slate-200 bg-white text-slate-600"}`}>
                    {REPORT_STATUS[s].label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700">Catatan Petugas <span className="text-xs text-slate-400">(min 10 karakter)</span></label>
              <Textarea value={catatan} onChange={(e) => setCatatan(e.target.value)} placeholder="Jelaskan kondisi di lapangan..." className="mt-1.5 rounded-2xl min-h-24" data-testid="laporan-catatan-input" />
            </div>

            <div className="bg-white rounded-2xl p-4 border border-slate-100">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-blue-600" /><span className="text-sm font-medium text-slate-700">Lokasi Saat Ini</span></div>
                {gpsState === "loading" && <Loader2 className="w-4 h-4 animate-spin text-blue-600" />}
                {gpsState === "ok" && <span className="text-xs text-emerald-600 font-semibold">Terdeteksi</span>}
                {gpsState === "denied" && <button onClick={captureGps} className="text-xs text-blue-600 flex items-center gap-1" data-testid="laporan-gps-retry"><RefreshCw className="w-3 h-3" /> Coba lagi</button>}
              </div>
              <div className="text-xs text-slate-500 mt-2 space-y-0.5">
                <p>Tanggal: {pad(now.getDate())} {MONTHS[now.getMonth()]} {now.getFullYear()} · Jam: {pad(now.getHours())}:{pad(now.getMinutes())} WIB</p>
                {gpsState === "ok" && coords && <p className="font-mono text-slate-600">Lat: {coords.lat}, Lng: {coords.lng}</p>}
              </div>
              {gpsState === "denied" && (
                <div className="mt-3 bg-amber-50 border border-amber-100 rounded-xl p-3">
                  <p className="text-xs text-amber-800 flex items-center gap-1 mb-2"><AlertTriangle className="w-3.5 h-3.5" /> Lokasi belum diizinkan. Berikan alasan jika tetap melapor.</p>
                  <Textarea value={gpsReason} onChange={(e) => setGpsReason(e.target.value)} placeholder="Alasan GPS tidak tersedia..." className="rounded-xl text-sm min-h-16 bg-white" data-testid="laporan-gps-reason" />
                </div>
              )}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 animate-fade-in">
            <div>
              <h2 className="font-heading font-semibold text-slate-800">Foto Bukti</h2>
              <p className="text-xs text-slate-500 mt-0.5">Wajib minimal 1 foto (maks 5). Watermark otomatis ditambahkan.</p>
            </div>
            <input ref={fileRef} type="file" accept="image/*" capture="environment" onChange={onFile} className="hidden" data-testid="laporan-photo-input" />
            <div className="grid grid-cols-2 gap-3">
              {photos.map((p, i) => (
                <div key={i} className="relative rounded-2xl overflow-hidden border border-slate-200 aspect-square" data-testid={`laporan-photo-preview-${i}`}>
                  <img src={p.url} alt={`Foto ${i + 1}`} className="w-full h-full object-cover" />
                  <button onClick={() => removePhoto(i)} className="absolute top-2 right-2 w-8 h-8 rounded-full bg-rose-600 text-white flex items-center justify-center shadow-lg" data-testid={`laporan-photo-delete-${i}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              {photos.length < 5 && (
                <button onClick={() => fileRef.current?.click()} data-testid="petugas-take-photo-button"
                  className="aspect-square rounded-2xl border-2 border-dashed border-slate-300 flex flex-col items-center justify-center text-slate-400 bg-white active:scale-95 transition-transform">
                  {photos.length === 0 ? <Camera className="w-8 h-8" /> : <Plus className="w-8 h-8" />}
                  <span className="text-xs mt-1 font-medium">{photos.length === 0 ? "Ambil Foto" : "Tambah Foto"}</span>
                </button>
              )}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4 animate-fade-in">
            <h2 className="font-heading font-semibold text-slate-800">Review Laporan</h2>
            <div className="bg-white rounded-2xl p-4 border border-slate-100 space-y-3">
              <div className="flex items-center justify-between"><span className="text-xs text-slate-400">Status Temuan</span><StatusBadge map={REPORT_STATUS} value={status} /></div>
              <div className="flex items-center justify-between"><span className="text-xs text-slate-400">No. Surat Tugas</span><span className="text-sm font-mono text-slate-700">{data.letter_nomor}</span></div>
              <div className="flex items-center justify-between"><span className="text-xs text-slate-400">Tanggal / Jam</span><span className="text-sm text-slate-700">{pad(now.getDate())}/{pad(now.getMonth()+1)}/{now.getFullYear()} {pad(now.getHours())}:{pad(now.getMinutes())}</span></div>
              <div className="flex items-center justify-between"><span className="text-xs text-slate-400">Lokasi</span><span className="text-sm font-mono text-slate-700">{coords ? `${coords.lat}, ${coords.lng}` : "Manual"}</span></div>
              <div><span className="text-xs text-slate-400">Catatan</span><p className="text-sm text-slate-700 mt-1">{catatan}</p></div>
            </div>
            {photos.length > 0 && (
              <div>
                <p className="text-xs text-slate-400 mb-2">Foto Bukti ({photos.length})</p>
                <div className="grid grid-cols-3 gap-2">
                  {photos.map((p, i) => <img key={i} src={p.url} alt="" className="aspect-square rounded-xl object-cover border border-slate-100" />)}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="fixed bottom-0 w-full max-w-[460px] p-4 bg-gradient-to-t from-slate-50 via-slate-50 to-transparent">
        {step < 3 ? (
          <button onClick={next} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3.5 rounded-2xl shadow-lg active:scale-[0.98] transition-all" data-testid="laporan-next-button">
            Lanjut
          </button>
        ) : (
          <button onClick={submit} disabled={submitting} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-3.5 rounded-2xl shadow-lg active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-70" data-testid="petugas-submit-report-button">
            {submitting ? <Loader2 className="w-5 h-5 animate-spin" /> : <><Send className="w-5 h-5" /> Kirim Laporan</>}
          </button>
        )}
      </div>
    </div>
  );
}
