import DeleteDataButton from "@/components/DeleteDataButton";
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
import {useAuth} from '@/context/AuthContext';

export default function Penugasan() {
  const navigate = useNavigate();
  const {user}=useAuth();
  const [approving,setApproving]=useState(null);
  async function approve(letter){
    if(approving)return;setApproving(letter.id);
    try{await api.post(`/penugasan/${letter.assignment_id}/approve`);toast.success('Surat tugas disetujui');window.dispatchEvent(new Event('big-mobile-approval-changed'));load();}
    catch(e){toast.error(errMsg(e));}finally{setApproving(null);}
  }
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
          <p className="text-sm text-slate-500 mt-1">Satu penugasan untuk satu unit, satu atau beberapa petugas, dan satu Surat Penugasan.</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="penugasan-create-button">
          <Plus className="w-4 h-4 mr-1" /> Buat Penugasan
        </Button>
      </div>

      {loading ? (
        <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
      ) : letters.length === 0 ? (
        <div className="brand-panel rounded-2xl border border-slate-200"><EmptyState icon={ClipboardList} title="Belum ada penugasan" desc="Klik Buat Penugasan untuk menugaskan satu unit kepada satu atau beberapa petugas." /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {letters.map((l) => (
            <div key={l.id} className="brand-panel rounded-2xl border border-slate-200 p-5" data-testid={`penugasan-card-${l.id}`}>
              <div className="flex items-start justify-between">
                <p className="font-mono text-sm font-semibold text-slate-800">{l.document_number || l.nomor}</p>
                <div className="flex items-center justify-end gap-1.5 flex-wrap">
                  <StatusBadge map={LETTER_STATUS} value={l.status} />
                  <span className="rounded-full bg-blue-100 text-blue-700 px-2 py-1 text-xs font-semibold whitespace-nowrap" data-testid={`penugasan-officer-count-${l.id}`}>{l.petugas_count || l.petugas_ids?.length || 1} Petugas</span>
                </div>
              </div>
              <div className="mt-3 space-y-1 text-sm">
                <p className="text-slate-700"><span className="text-slate-400">Petugas:</span> {l.petugas?.length ? l.petugas.map(p => `${p.name} (${p.petugas_code})`).join(", ") : l.petugas_name}</p>
                <p className="text-slate-700"><span className="text-slate-400">Pemberi Kuasa:</span> {l.client_name}</p>
                <p className="text-slate-700"><span className="text-slate-400">Unit:</span> {l.accounts?.[0]?.nama_debitur || "-"} · {l.accounts?.[0]?.nomor_polisi || "-"}</p>
                <p className="text-slate-500 text-xs mt-1">Dibuat {formatDate(l.tanggal)}</p>
              </div>
              <div className="mt-3 flex justify-end"><DeleteDataButton endpoint={l.assignment_id ? `/penugasan/${l.assignment_id}` : `/surat-tugas/${l.id}`} name={`Penugasan ${l.document_number || l.nomor}`} testId={`penugasan-delete-${l.id}`} description="Surat tugas dan percakapan terkait ikut dihapus; unit dilepas jika masih aktif pada penugasan ini. Hapus laporan terkait terlebih dahulu. Pesan WhatsApp yang sudah dikirim tidak dapat ditarik kembali." onDeleted={()=>{load();window.dispatchEvent(new Event('big-mobile-approval-changed'));window.dispatchEvent(new Event('big-mobile-chat-read'));}}/></div>
              <button onClick={() => navigate(`/admin/surat-tugas/${l.id}/dokumen`)} className="mt-4 text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1" data-testid={`penugasan-view-st-${l.id}`}>
                Lihat Surat Penugasan <ArrowRight className="w-3.5 h-3.5" />
              </button>
              {user.role==='owner'&&l.status==='menunggu_approval'&&<Button className="mt-3" disabled={!!approving} onClick={()=>approve(l)} data-testid={`penugasan-approve-${l.id}`}>{approving===l.id?'Menyetujui...':'Approve Surat Tugas'}</Button>}
              {l.assignment_id && l.status!=='menunggu_approval' && <button onClick={() => navigate(`/admin/chat/${l.assignment_id}`)} className="mt-3 rounded-xl bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700" data-testid={`penugasan-chat-${l.id}`}>Chat petugas</button>}
            </div>
          ))}
        </div>
      )}

      <PenugasanDialog open={dialogOpen} onOpenChange={setDialogOpen} onSuccess={() => {load();window.dispatchEvent(new Event('big-mobile-approval-changed'));}} />
    </div>
  );
}
