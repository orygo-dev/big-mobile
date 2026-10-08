import { useCallback, useEffect, useState } from "react";
import api, { errMsg } from "@/lib/api";
import LoadError from "@/components/LoadError";
import TaskCard from "@/components/TaskCard";
import EmptyState from "@/components/EmptyState";
import { ClipboardList, Loader2 } from "lucide-react";

export default function Tugas() {
  const [tugas, setTugas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setLoading(true); setError("");
    api.get("/my/tugas").then(({ data }) => setTugas(data)).catch((e) => setError(errMsg(e))).finally(() => setLoading(false));
  }, []);
  useEffect(() => {load();}, [load]);
  return (
    <div>
      <header className="brand-hero px-5 pt-8 pb-5 sticky top-0 z-10">
        <h1 className="font-heading text-xl font-semibold">Daftar Tugas</h1>
        <p className="text-white/90 text-sm mt-1">{loading || error ? "Memuat data tugas" : `${tugas.length} tugas ditugaskan kepada Anda`}</p>
      </header>
      <div className="px-4 mt-4 pb-4">
        {loading ? (
          <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : error ? <LoadError message={error} onRetry={load} /> : tugas.length === 0 ? (
          <div className="brand-panel"><EmptyState icon={ClipboardList} title="Belum ada tugas" desc="Tugas baru akan muncul di sini." /></div>
        ) : (
          <div className="space-y-3">
            {tugas.map((task) => <TaskCard key={task.account.id} task={task} dataTestid={`tugas-list-card-${task.account.id}`} />)}
          </div>
        )}
      </div>
    </div>
  );
}
