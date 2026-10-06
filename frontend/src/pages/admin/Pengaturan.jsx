import { useEffect, useState } from "react";
import api from "@/lib/api";
import { formatDateTime } from "@/lib/constants";
import { Building2, ScrollText, Loader2 } from "lucide-react";

export default function Pengaturan() {
  const [company, setCompany] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/company").then(({ data }) => setCompany(data)).catch(() => {}),
      api.get("/audit-logs").then(({ data }) => setLogs(data)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-5 animate-fade-in max-w-4xl">
      <div>
        <h1 className="font-heading text-2xl font-bold text-slate-900">Pengaturan</h1>
        <p className="text-sm text-slate-500 mt-1">Informasi perusahaan dan log aktivitas sistem.</p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5">
        <div className="flex items-center gap-2 mb-4"><Building2 className="w-5 h-5 text-blue-600" /><h2 className="font-heading font-semibold text-slate-800">Profil Perusahaan</h2></div>
        {company ? (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div><dt className="text-xs text-slate-400">Nama</dt><dd className="font-medium text-slate-700">{company.nama}</dd></div>
            <div><dt className="text-xs text-slate-400">Telepon</dt><dd className="text-slate-700">{company.telepon}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs text-slate-400">Alamat</dt><dd className="text-slate-700">{company.alamat}</dd></div>
            <div><dt className="text-xs text-slate-400">Email</dt><dd className="text-slate-700">{company.email}</dd></div>
          </dl>
        ) : <Loader2 className="w-5 h-5 animate-spin text-blue-600" />}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5">
        <div className="flex items-center gap-2 mb-4"><ScrollText className="w-5 h-5 text-blue-600" /><h2 className="font-heading font-semibold text-slate-800">Audit Log</h2></div>
        {loading ? (
          <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
        ) : logs.length === 0 ? (
          <p className="text-sm text-slate-400">Belum ada aktivitas tercatat.</p>
        ) : (
          <div className="overflow-x-auto -mx-5">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-slate-400 uppercase tracking-wider border-b border-slate-100">
                <th className="px-5 py-2 font-medium">Waktu</th><th className="px-3 py-2 font-medium">Pengguna</th>
                <th className="px-3 py-2 font-medium">Aktivitas</th><th className="px-5 py-2 font-medium">IP</th>
              </tr></thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-b border-slate-50">
                    <td className="px-5 py-2.5 text-slate-500 whitespace-nowrap">{formatDateTime(l.timestamp)}</td>
                    <td className="px-3 py-2.5 text-slate-700">{l.user_name || "-"}</td>
                    <td className="px-3 py-2.5 text-slate-600">{l.activity} <span className="text-xs text-slate-400">({l.entity})</span></td>
                    <td className="px-5 py-2.5 text-slate-400 font-mono text-xs">{l.ip_address || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
