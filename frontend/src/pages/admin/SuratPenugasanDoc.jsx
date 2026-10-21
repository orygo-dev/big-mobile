import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { API, errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, Printer, Download, ArrowLeft, Ban } from "lucide-react";
import { toast } from "sonner";
import FieldAssignmentLetter from "@/components/FieldAssignmentLetter";
import { useAuth } from "@/context/AuthContext";

export default function SuratPenugasanDoc() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const officerView = user.role === "petugas";
  const back = officerView ? "/app/tugas" : "/admin/surat-tugas";
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get(`${officerView ? "/my" : ""}/surat-tugas/${id}/document`).then(({ data }) => setDoc(data))
      .catch((e) => { toast.error(errMsg(e)); navigate(back); }).finally(() => setLoading(false));
  }, [id, navigate, officerView, back]);
  useEffect(() => { load(); }, [load]);

  const cancel = async () => {
    setBusy(true);
    try { await api.patch(`/surat-tugas/${id}/status`, { status: "dibatalkan" }); toast.success("Surat Tugas dibatalkan"); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const doPrint = (titleSuffix) => {
    const prev = document.title;
    document.title = (doc?.data?.letter?.document_number || doc?.st_nomor || "surat-penugasan") + (titleSuffix || "");
    window.print();
    setTimeout(() => { document.title = prev; }, 500);
  };

  if (loading || !doc) return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>;

  const finalized = doc.is_finalized;
  const qrSrc = `${API}/surat-tugas/${id}/qr`;

  return (
    <div className="doc-layout" style={{ minHeight: "100vh", background: "#e2e8f0", paddingBottom: 40 }}>
      <style>{`
        @page { size: A4; margin: 0; }
        @media print {
          body { background: #fff !important; }
          .doc-layout { padding-bottom: 0 !important; background: #fff !important; }
          .doc-toolbar { display: none !important; }
          .doc-page { box-shadow: none !important; margin: 0 !important; page-break-after: always; }
          .doc-page:last-child { page-break-after: auto; }
        }
        .doc-page { width: 210mm; min-height: 297mm; background: #fff; margin: 16px auto; padding: 18mm; position: relative; box-shadow: 0 10px 30px rgba(0,0,0,.15); font-family: Arial, Helvetica, sans-serif; font-size: 10.5px; color: #111; line-height: 1.5; box-sizing: border-box; }
        .doc-h2 { font-weight: 800; font-size: 11px; margin: 12px 0 5px; }
        .doc-page ol { margin: 4px 0 4px 0; padding-left: 18px; }
        .doc-page ol li { margin-bottom: 3px; }
        .spec-table td { padding: 1px 0; }
        .chk { width: 100%; border-collapse: collapse; font-size: 8.5px; }
        .chk th, .chk td { border: 1px solid #555; padding: 2px 3px; }
        .chk th { background: #f1f1f1; text-align: center; font-weight: 700; }
        .chk .cbox { width: 16px; height: 12px; }
        .wm { position: absolute; top: 46%; left: 50%; transform: translate(-50%,-50%); font-size: 120px; font-weight: 900; color: rgba(192,33,31,.06); font-family: Arial; pointer-events: none; }
      `}</style>

      {/* Toolbar */}
      <div className="doc-toolbar" style={{ maxWidth: "210mm", margin: "0 auto", padding: "16px 8px 0" }}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <button onClick={() => navigate(back)} className="flex items-center gap-1.5 text-sm text-slate-700 hover:text-slate-900" data-testid="doc-back">
            <ArrowLeft className="w-4 h-4" /> Kembali
          </button>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${finalized ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`} data-testid="doc-status-badge">
              {doc.letter_status==='menunggu_approval' ? "MENUNGGU APPROVAL OWNER" : finalized ? "ACTIVE / FINALIZED" : "DRAFT / PREVIEW"}
            </span>
            {user.role==='owner'&&doc.letter_status==='menunggu_approval'&&<Button disabled={busy} data-testid="doc-approve-button" onClick={async()=>{setBusy(true);try{await api.post(`/penugasan/${doc.assignment_id}/approve`);window.dispatchEvent(new Event('big-mobile-approval-changed'));toast.success('Surat tugas disetujui');await load();}catch(e){toast.error(errMsg(e));}finally{setBusy(false);}}}>Approve Surat Tugas</Button>}
            <Button onClick={() => doPrint("")} variant="outline" className="rounded-xl" data-testid="doc-print-button"><Printer className="w-4 h-4 mr-1" /> Cetak</Button>
            <Button onClick={() => doPrint(".pdf")} className="rounded-xl bg-slate-900 hover:bg-slate-800" data-testid="doc-download-button"><Download className="w-4 h-4 mr-1" /> Download PDF</Button>
            {!officerView && ['aktif','menunggu_approval'].includes(doc.letter_status) && (
              <Button onClick={cancel} disabled={busy} variant="outline" className="rounded-xl border-rose-200 text-rose-600 hover:bg-rose-50" data-testid="doc-cancel-button"><Ban className="w-4 h-4 mr-1" /> Batalkan</Button>
            )}
          </div>
        </div>
      </div>

      <FieldAssignmentLetter doc={doc} qrSrc={qrSrc} />

    </div>
  );
}
