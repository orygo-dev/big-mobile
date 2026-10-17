import {useCallback, useEffect, useState} from "react";
import api, {errMsg} from "@/lib/api";
import {formatDateTime} from "@/lib/constants";
import {ScrollText, Loader2, RefreshCw} from "lucide-react";
import {Button} from "@/components/ui/button";
import LoadError from "@/components/LoadError";

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setLoading(true); setError("");
    return api.get("/audit-logs").then(({data}) => setLogs(data))
      .catch(e => setError(errMsg(e))).finally(() => setLoading(false));
  }, []);
  useEffect(() => {load();}, [load]);
  return <div className="space-y-5 animate-fade-in" data-testid="audit-log-page">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="font-heading text-2xl font-bold text-slate-900">Audit Log</h1>
        <p className="text-sm text-slate-500 mt-1">Riwayat aktivitas pengguna dalam aplikasi.</p></div>
      <Button variant="outline" disabled={loading} onClick={load}><RefreshCw className="w-4 h-4 mr-2"/>Perbarui</Button>
    </div>
    {error ? <LoadError message={error} onRetry={load}/> : (
      <div className="brand-panel rounded-2xl border border-slate-200 p-5">
        <div className="flex items-center gap-2 mb-4"><ScrollText className="w-5 h-5 text-blue-600" /><h2 className="font-heading font-semibold text-slate-800">Audit Log</h2></div>
        {loading ? (
          <div role="status" className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="w-5 h-5 animate-spin text-blue-600" />Memuat audit log…</div>
        ) : logs.length === 0 ? (
          <p className="text-sm text-slate-400">Belum ada aktivitas tercatat.</p>
        ) : (
          <div className="overflow-x-auto -mx-5">
            <table className="w-full min-w-[640px] text-sm">
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

)}
  </div>;
}
