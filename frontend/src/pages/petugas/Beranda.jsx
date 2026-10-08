import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import LoadError from "@/components/LoadError";
import { useAuth } from "@/context/AuthContext";
import BrandIdentity from "@/components/BrandIdentity";
import TaskCard from "@/components/TaskCard";
import EmptyState from "@/components/EmptyState";
import { ClipboardList, Clock, Activity, CheckCircle2, BadgeCheck, Loader2 } from "lucide-react";

export default function Beranda() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tugas, setTugas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setLoading(true); setError("");
    api.get("/my/tugas").then(({ data }) => setTugas(data)).catch((e) => setError(errMsg(e))).finally(() => setLoading(false));
  }, []);
  useEffect(() => {load();}, [load]);
  const summary = [
    { label: "Tugas Saya", value: tugas.length, icon: ClipboardList, style: "brand-summary-primary" },
    { label: "Belum Dikerjakan", value: tugas.filter((t) => !t.sudah_dilaporkan).length, icon: Clock, style: "brand-summary-pending" },
    { label: "Dalam Proses", value: tugas.filter((t) => t.account.status === "DALAM_PROSES").length, icon: Activity, style: "" },
    { label: "Ditemukan", value: tugas.filter((t) => t.account.status === "UNIT_DITEMUKAN").length, icon: CheckCircle2, style: "" },
  ];
  return (
    <div>
      <header className="brand-hero px-5 pt-6 pb-7">
        <BrandIdentity light className="mb-7" />
        <p className="text-white/90 text-sm">Selamat datang,</p>
        <h1 className="font-heading text-2xl font-semibold mt-1 break-words">{user?.name}</h1>
        <p className="flex items-center gap-2 text-xs text-white/90 mt-2"><BadgeCheck className="w-4 h-4 shrink-0" aria-hidden="true" />{user?.petugas_code} · {user?.tim}</p>
      </header>
      <div className="px-4 mt-4">
        <div className="grid grid-cols-2 gap-3" data-testid="petugas-summary">
          {summary.map((item) => (
            <div key={item.label} className={`brand-panel p-4 ${item.style}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs">{item.label}</p>
                <item.icon className="w-4 h-4 shrink-0" aria-hidden="true" />
              </div>
              <p className="brand-summary-value text-3xl font-semibold font-heading mt-2">{loading || error ? "—" : item.value}</p>
            </div>
          ))}
        </div>
      </div>
      <section className="px-4 mt-6 pb-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="font-heading font-semibold text-slate-900 text-lg">Tugas Saya</h2>
          <button onClick={() => navigate("/app/tugas")} className="min-h-11 text-sm text-blue-600 font-medium">Lihat Semua</button>
        </div>
        {loading ? (
          <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : error ? <LoadError message={error} onRetry={load} /> : tugas.length === 0 ? (
          <div className="brand-panel"><EmptyState icon={ClipboardList} title="Belum ada tugas" desc="Tugas baru akan muncul di sini." /></div>
        ) : (
          <div className="space-y-3">
            {tugas.slice(0, 5).map((task) => <TaskCard key={task.account.id} task={task} dataTestid={`tugas-card-${task.account.id}`} />)}
          </div>
        )}
      </section>
    </div>
  );
}
