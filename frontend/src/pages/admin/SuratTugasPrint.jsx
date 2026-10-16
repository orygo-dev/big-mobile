import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { API, errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, Printer, ArrowLeft } from "lucide-react";
import FieldAssignmentLetter from "@/components/FieldAssignmentLetter";

export default function SuratTugasPrint() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [letter, setLetter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true); setError("");
    api.get(`/surat-tugas/${id}/document`)
      .then(({data}) => setLetter(data))
      .catch((e) => setError(errMsg(e))).finally(() => setLoading(false));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  if (error) return <div role="alert" className="p-8 text-center"><p>{error}</p><Button onClick={load}>Coba lagi</Button></div>;
  if (loading || !letter) return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>;

  const qrSrc = `${API}/surat-tugas/${id}/qr`;

  return (
    <div className="min-h-screen bg-slate-100 py-6">
      <div className="no-print max-w-[210mm] mx-auto px-4 mb-4 flex items-center justify-between">
        <button onClick={() => navigate("/admin/surat-tugas")} className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900">
          <ArrowLeft className="w-4 h-4" /> Kembali
        </button>
        <Button onClick={() => window.print()} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="admin-print-surat-tugas-button">
          <Printer className="w-4 h-4 mr-1" /> Cetak / Simpan PDF
        </Button>
      </div>

      <style>{`
        @page { size: A4; margin: 0; }
        .doc-page { width: 210mm; min-height: 297mm; margin: 0 auto; background: white; box-sizing: border-box; font-family: Arial, Helvetica, sans-serif; color: #111; }
        @media print { .no-print { display: none !important; } body { background: white !important; } }
      `}</style>
      <FieldAssignmentLetter doc={letter} qrSrc={qrSrc} />
    </div>
  );
}
