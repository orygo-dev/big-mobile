import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { ACCOUNT_STATUS } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import { Car, MapPin, ClipboardList, ChevronRight, Loader2 } from "lucide-react";

export default function Tugas() {
  const navigate = useNavigate();
  const [tugas, setTugas] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/my/tugas").then(({ data }) => setTugas(data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="bg-slate-900 text-white px-5 pt-8 pb-5 rounded-b-3xl sticky top-0 z-10">
        <h1 className="font-heading text-xl font-bold">Daftar Tugas</h1>
        <p className="text-slate-400 text-sm mt-0.5">{tugas.length} tugas ditugaskan kepada Anda</p>
      </div>

      <div className="px-4 mt-4">
        {loading ? (
          <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : tugas.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-100"><EmptyState icon={ClipboardList} title="Belum ada tugas" desc="Tugas baru akan muncul di sini." /></div>
        ) : (
          <div className="space-y-3">
            {tugas.map((t) => (
              <button key={t.account.id} onClick={() => navigate(`/app/tugas/${t.account.id}`)} data-testid={`tugas-list-card-${t.account.id}`}
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
                    <p className="font-mono font-semibold text-slate-700">{t.account.nomor_polisi} · {t.account.merk} {t.account.model}</p>
                    <p className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {t.account.kabupaten}, {t.account.provinsi}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-300" />
                </div>
                {t.sudah_dilaporkan && <p className="text-[11px] text-emerald-600 mt-2 font-medium">✓ Sudah dilaporkan</p>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
