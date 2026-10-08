import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import LoadError from "@/components/LoadError";
import { formatDateTime } from "@/lib/constants";
import { StatusBadge } from "@/components/StatusBadge";
import { REPORT_STATUS } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import {
  FileText, Car, ClipboardCheck, CheckCircle2, XCircle, Clock, CalendarDays, Activity, Eye,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const STAT_CONF = [
  { key: "surat_kuasa_aktif", tone: "blue", label: "Surat Kuasa Aktif", icon: FileText },
  { key: "total_akun", tone: "cyan", label: "Total Kontrak & Unit", icon: Car },
  { key: "tugas_aktif", tone: "purple", label: "Tugas Aktif", icon: ClipboardCheck },
  { key: "unit_ditemukan", tone: "green", label: "Unit Ditemukan", icon: CheckCircle2 },
  { key: "unit_tidak_ditemukan", tone: "rose", label: "Tidak Ditemukan", icon: XCircle },
  { key: "belum_dikerjakan", tone: "amber", label: "Belum Dikerjakan", icon: Clock },
  { key: "laporan_hari_ini", tone: "orange", label: "Laporan Hari Ini", icon: CalendarDays },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({});
  const [activity, setActivity] = useState([]);
  const [chart, setChart] = useState([]);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true); setError("");
    Promise.all([api.get("/dashboard/stats"),api.get("/dashboard/recent-activity"),api.get("/dashboard/reports-7days")])
      .then(([counts,recent,days]) => {setStats(counts.data);setActivity(recent.data);setChart(days.data);})
      .catch((e) => setError(errMsg(e))).finally(() => setLoading(false));
  }, []);
  useEffect(() => {load();}, [load]);
  if (error) return <div className="space-y-5"><h1 className="text-2xl font-semibold">Dashboard</h1><LoadError message={error} onRetry={load} /></div>;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="brand-hero rounded-2xl p-5 sm:p-7">
        <h1 className="font-heading text-2xl sm:text-3xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-white/90 mt-1">Ringkasan operasional lapangan hari ini.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4" data-testid="dashboard-stats">
        {STAT_CONF.map((s) => (
          <div key={s.key} className={`brand-panel p-4 sm:p-5 flex items-center justify-between gap-3 hover:shadow-md transition-all dashboard-stat dashboard-stat-${s.tone}`}>
            <div>
              <p className="text-xs stat-label font-medium">{s.label}</p>
              <p className={`text-2xl sm:text-3xl font-semibold font-heading mt-1 stat-value`} data-testid={`stat-${s.key}`}>{loading ? "—" : stats[s.key] ?? 0}</p>
            </div>
            <div className={`w-10 h-10 shrink-0 rounded-xl stat-icon flex items-center justify-center`}>
              <s.icon className="w-5 h-5" />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="brand-panel lg:col-span-2 min-w-0 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-5 h-5 text-blue-600" />
            <h2 className="font-heading font-semibold text-slate-800">Aktivitas Terbaru</h2>
          </div>
          {activity.length === 0 ? (
            <EmptyState icon={Activity} title="Belum ada aktivitas" desc="Laporan petugas akan muncul di sini." />
          ) : (
            <div className="overflow-x-auto -mx-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-400 uppercase tracking-wider border-b border-slate-100">
                    <th className="px-5 py-2 font-medium">Waktu</th>
                    <th className="px-3 py-2 font-medium">Petugas</th>
                    <th className="px-3 py-2 font-medium">No. Surat Tugas</th>
                    <th className="px-3 py-2 font-medium">Debitur</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-5 py-2 font-medium text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.map((a) => (
                    <tr key={a.id} className="border-b border-slate-50 hover:bg-slate-50/50">
                      <td className="px-5 py-3 text-slate-500 whitespace-nowrap">{formatDateTime(a.waktu)}</td>
                      <td className="px-3 py-3 font-medium text-slate-700">{a.petugas}</td>
                      <td className="px-3 py-3 font-mono text-xs text-slate-600">{a.nomor_surat_tugas}</td>
                      <td className="px-3 py-3 text-slate-700">{a.nama_debitur}</td>
                      <td className="px-3 py-3"><StatusBadge map={REPORT_STATUS} value={a.status} /></td>
                      <td className="px-5 py-3 text-right">
                        <button onClick={() => navigate(`/admin/laporan/${a.id}`)} className="text-blue-600 hover:text-blue-800" data-testid={`activity-view-${a.id}`}>
                          <Eye className="w-4 h-4 inline" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="brand-panel min-w-0 p-5">
          <h2 className="font-heading font-semibold text-slate-800 mb-1">Laporan 7 Hari Terakhir</h2>
          <p className="text-xs text-slate-400 mb-4">Jumlah laporan masuk per hari</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chart} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "#f8fafc" }} contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }} />
              <Bar dataKey="count" fill="#0066ff" radius={[6, 6, 0, 0]} name="Laporan" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
