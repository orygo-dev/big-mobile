import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { formatDateTime } from "@/lib/constants";
import { StatusBadge } from "@/components/StatusBadge";
import { REPORT_STATUS } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import {
  FileText, Car, ClipboardCheck, CheckCircle2, XCircle, Clock, CalendarDays, Activity, Eye,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const STAT_CONF = [
  { key: "surat_kuasa_aktif", label: "Surat Kuasa Aktif", icon: FileText, color: "text-blue-600", bg: "bg-blue-50" },
  { key: "total_akun", label: "Total Kontrak & Unit", icon: Car, color: "text-indigo-600", bg: "bg-indigo-50" },
  { key: "tugas_aktif", label: "Tugas Aktif", icon: ClipboardCheck, color: "text-sky-600", bg: "bg-sky-50" },
  { key: "unit_ditemukan", label: "Unit Ditemukan", icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50" },
  { key: "unit_tidak_ditemukan", label: "Tidak Ditemukan", icon: XCircle, color: "text-rose-600", bg: "bg-rose-50" },
  { key: "belum_dikerjakan", label: "Belum Dikerjakan", icon: Clock, color: "text-amber-600", bg: "bg-amber-50" },
  { key: "laporan_hari_ini", label: "Laporan Hari Ini", icon: CalendarDays, color: "text-violet-600", bg: "bg-violet-50" },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({});
  const [activity, setActivity] = useState([]);
  const [chart, setChart] = useState([]);

  useEffect(() => {
    api.get("/dashboard/stats").then(({ data }) => setStats(data)).catch(() => {});
    api.get("/dashboard/recent-activity").then(({ data }) => setActivity(data)).catch(() => {});
    api.get("/dashboard/reports-7days").then(({ data }) => setChart(data)).catch(() => {});
  }, []);

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="font-heading text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Ringkasan operasional lapangan hari ini.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4" data-testid="dashboard-stats">
        {STAT_CONF.map((s) => (
          <div key={s.key} className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 flex items-center justify-between hover:shadow-md transition-all">
            <div>
              <p className="text-xs text-slate-500 font-medium">{s.label}</p>
              <p className="text-2xl sm:text-3xl font-bold text-slate-900 font-heading mt-1" data-testid={`stat-${s.key}`}>{stats[s.key] ?? 0}</p>
            </div>
            <div className={`w-10 h-10 rounded-xl ${s.bg} flex items-center justify-center`}>
              <s.icon className={`w-5 h-5 ${s.color}`} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-5">
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

        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <h2 className="font-heading font-semibold text-slate-800 mb-1">Laporan 7 Hari Terakhir</h2>
          <p className="text-xs text-slate-400 mb-4">Jumlah laporan masuk per hari</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chart} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "#f8fafc" }} contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }} />
              <Bar dataKey="count" fill="#2563EB" radius={[6, 6, 0, 0]} name="Laporan" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
