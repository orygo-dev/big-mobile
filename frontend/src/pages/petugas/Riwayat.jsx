import { useEffect, useState } from "react";
import api, { fileUrl, errMsg } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { REPORT_STATUS, formatDateTime } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import { History, Loader2, ImageIcon, MapPin } from "lucide-react";

const FILTERS = [
  { key: "all", label: "Semua" },
  { key: "UNIT_DITEMUKAN", label: "Ditemukan" },
  { key: "TIDAK_DITEMUKAN", label: "Tidak Ditemukan" },
  { key: "ALAMAT_TIDAK_SESUAI", label: "Alamat Tidak Sesuai" },
  { key: "PINDAH_ALAMAT", label: "Pindah Alamat" },
  { key: "UNIT_TIDAK_ADA", label: "Unit Tidak Ada" },
  { key: "LAINNYA", label: "Lainnya" },
];

export default function Riwayat() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError("");
    api.get("/my/riwayat", { params: { status: filter !== "all" ? filter : undefined } })
      .then(({ data }) => setItems(data)).catch((e) => setError(errMsg(e))).finally(() => setLoading(false));
  }, [filter, reload]);

  return (
    <div>
      <div className="brand-hero text-white px-5 pt-8 pb-5 sticky top-0 z-10">
        <h1 className="font-heading text-xl font-bold">Riwayat Laporan</h1>
        <p className="text-slate-400 text-sm mt-0.5">Laporan yang telah Anda kirim</p>
      </div>

      <div className="px-4 mt-4">
        <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)} data-testid={`riwayat-filter-${f.key}`}
              className={`px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${filter === f.key ? "bg-blue-600 text-white" : "bg-white text-slate-500 border border-slate-200"}`}>
              {f.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
        ) : error ? (
          <div role="alert" className="brand-panel p-4 mt-2 text-sm"><p>{error}</p><button className="text-blue-600 mt-2" onClick={() => setReload((value) => value + 1)}>Coba lagi</button></div>
        ) : items.length === 0 ? (
          <div className="brand-panel rounded-2xl border border-slate-100 mt-2"><EmptyState icon={History} title="Belum ada laporan" desc="Laporan yang Anda kirim akan tampil di sini." /></div>
        ) : (
          <div className="space-y-3 mt-2">
            {items.map((r) => (
              <div key={r.id} className="brand-panel rounded-2xl p-4 shadow-sm border border-slate-100" data-testid={`riwayat-card-${r.id}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-slate-800 text-sm">{r.nama_debitur}</p>
                    <p className="text-xs text-slate-400 font-mono">{r.nomor_polisi} · {r.letter_nomor}</p>
                  </div>
                  <StatusBadge map={REPORT_STATUS} value={r.status} />
                </div>
                <div className="flex items-center gap-3 mt-3 pt-3 border-t border-slate-50 text-xs text-slate-400">
                  <span>{formatDateTime(r.created_at)}</span>
                  {r.photos?.length > 0 && <span className="flex items-center gap-1"><ImageIcon className="w-3 h-3" /> {r.photos.length}</span>}
                  {r.latitude != null && r.longitude != null && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> GPS</span>}
                </div>
                {r.photos?.length > 0 && (
                  <div className="flex gap-2 mt-3 overflow-x-auto">
                    {r.photos.map((p, i) => <img key={i} src={fileUrl(p.url)} alt="" className="w-16 h-16 rounded-lg object-cover flex-shrink-0 border border-slate-100" />)}
                  </div>
                )}
                <p className="text-xs mt-3 text-blue-700">{r.reviewed ? "Sudah direview admin" : "Menunggu review admin"}</p>
                {r.catatan_admin && <div className="mt-2 rounded-xl bg-blue-50 p-3 text-sm text-slate-700"><p className="font-semibold mb-1">Catatan admin</p>{r.catatan_admin}</div>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
