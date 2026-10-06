import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StatusBadge } from "@/components/StatusBadge";
import { ACCOUNT_STATUS } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import { Car, MapPin, ClipboardList, Clock, Activity, CheckCircle2, ChevronRight, Loader2 } from "lucide-react";

export default function Beranda() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tugas, setTugas] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/my/tugas").then(({ data }) => setTugas(data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const belum = tugas.filter((t) => !t.sudah_dilaporkan).length;
  const proses = tugas.filter((t) => t.account.status === "DALAM_PROSES").length;
  const ditemukan = tugas.filter((t) => t.account.status === "UNIT_DITEMUKAN").length;

  const SUMMARY = [
    { label: "Tugas Hari Ini", value: tugas.length, icon: ClipboardList, color: "bg-blue-500" },
    { label: "Belum Dikerjakan", value: belum, icon: Clock, color: "bg-amber-500" },
    { label: "Dalam Proses", value: proses, icon: Activity, color: "bg-sky-500" },
    { label: "Ditemukan", value: ditemukan, icon: CheckCircle2, color: "bg-emerald-500" },
  ];

  return (
    <div>
      <div className="bg-slate-900 text-white px-5 pt-8 pb-16 rounded-b-3xl">
        <p className="text-slate-400 text-sm">Selamat Datang,</p>
        <h1 className="font-heading text-2xl font-bold mt-0.5">{user?.name}</h1>
        <p className="text-xs text-slate-400 font-mono mt-1">{user?.petugas_code} · {user?.tim}</p>
      </div>

      <div className="px-4 -mt-10">
        <div className="grid grid-cols-2 gap-3" data-testid="petugas-summary">
          {SUMMARY.map((s) => (
            <div key={s.label} className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100">
              <div className={`w-9 h-9 rounded-xl ${s.color} flex items-center justify-center mb-2`}><s.icon className="w-4.5 h-4.5 text-white" /></div>
              <p className="text-2xl font-bold text-slate-900 font-heading">{s.value}</p>
              <p className="text-xs text-slate-500">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="px-4 mt-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-heading font-bold text-slate-800 text-lg">Tugas Saya</h2>
          <button onClick={() => navigate("/app/tugas")} className="text-sm text-blue-600 font-medium">Lihat Semua</button>
        </div>

        {loading ? (
          <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : tugas.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-100"><EmptyState icon={ClipboardList} title="Belum ada tugas hari ini" desc="Tugas baru akan muncul di sini." /></div>
        ) : (
          <div className="space-y-3">
            {tugas.slice(0, 5).map((t) => (
              <button key={t.account.id} onClick={() => navigate(`/app/tugas/${t.account.id}`)} data-testid={`tugas-card-${t.account.id}`}
                className="w-full text-left bg-white rounded-2xl p-4 shadow-sm border border-slate-100 active:scale-[0.98] transition-transform">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center"><Car className="w-4.5 h-4.5 text-blue-600" /></div>
                    <div>
                      <p className="font-semibold text-slate-800 text-sm">{t.account.nama_debitur}</p>
                      <p className="text-xs text-slate-400 font-mono">{t.account.nomor_kontrak}</p>
                    </div>
                  </div>
                  <StatusBadge map={ACCOUNT_STATUS} value={t.account.status} />
                </div>
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-50">
                  <div className="text-xs text-slate-500 space-y-0.5">
                    <p className="font-mono font-semibold text-slate-700">{t.account.nomor_polisi} · {t.account.jenis_kendaraan}</p>
                    <p className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {t.account.kabupaten}, {t.account.provinsi}</p>
                    <p className="font-mono text-[10px] text-slate-400">{t.letter_nomor}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-300" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
