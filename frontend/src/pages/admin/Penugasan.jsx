import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import { LETTER_STATUS, formatDate } from "@/lib/constants";
import EmptyState from "@/components/EmptyState";
import PenugasanDialog from "@/components/PenugasanDialog";
import { ClipboardList, Loader2, Plus, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function Penugasan() {
  const navigate = useNavigate();
  const [letters, setLetters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/surat-tugas").then(({ data }) => setLetters(data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="font-heading text-2xl font-bold text-slate-900">Penugasan</h1>
          <p className="text-sm text-slate-500 mt-1">Satu penugasan = satu unit = satu petugas = satu Surat Penugasan.</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="penugasan-create-button">
          <Plus className="w-4 h-4 mr-1" /> Buat Penugasan
        </Button>
      </div>

      {loading ? (
        <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
      ) : letters.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200"><EmptyState icon={ClipboardList} title="Belum ada penugasan" desc="Klik Buat Penugasan untuk menugaskan satu unit kepada seorang petugas." /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {letters.map((l) => (
            <div key={l.id} className="bg-white rounded-2xl border border-slate-200 p-5" data-testid={`penugasan-card-${l.id}`}>
              <div className="flex items-start justify-between">
                <p className="font-mono text-sm font-semibold text-slate-800">{l.document_number || l.nomor}</p>
                <StatusBadge map={LETTER_STATUS} value={l.status} />
              </div>
              <div className="mt-3 space-y-1 text-sm">
                <p className="text-slate-700"><span className="text-slate-400">Petugas:</span> {l.petugas_name} ({l.petugas_code})</p>
                <p className="text-slate-700"><span className="text-slate-400">Pemberi Kuasa:</span> {l.client_name}</p>
                <p className="text-slate-700"><span className="text-slate-400">Unit:</span> {l.accounts?.[0]?.nama_debitur || "-"} · {l.accounts?.[0]?.nomor_polisi || "-"}</p>
                <p className="text-slate-500 text-xs mt-1">Dibuat {formatDate(l.tanggal)}</p>
              </div>
              <button onClick={() => navigate(`/admin/surat-tugas/${l.id}/dokumen`)} className="mt-4 text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1" data-testid={`penugasan-view-st-${l.id}`}>
                Lihat Surat Penugasan <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      <PenugasanDialog open={dialogOpen} onOpenChange={setDialogOpen} onSuccess={() => load()} />
    </div>
  );
}
