import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { API, errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/constants";
import { Loader2, Printer, ArrowLeft } from "lucide-react";
import CompanyLetterhead from "@/components/CompanyLetterhead";

export default function SuratTugasPrint() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [letter, setLetter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [company, setCompany] = useState({});
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true); setError("");
    Promise.all([api.get(`/surat-tugas/${id}`), api.get("/company")])
      .then(([letterResponse, companyResponse]) => { setLetter(letterResponse.data); setCompany(companyResponse.data); })
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

      <div className="print-page w-[210mm] min-h-[297mm] bg-white mx-auto shadow-2xl p-[18mm] text-slate-900" style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>
        <CompanyLetterhead company={company} />

        <div className="text-center my-6">
          <h2 className="text-xl font-bold underline tracking-wide">SURAT TUGAS</h2>
          <p className="text-sm mt-1">Nomor: {letter.nomor}</p>
        </div>

        <p className="text-sm leading-relaxed">Yang bertanda tangan di bawah ini, pimpinan {company.nama}, dengan ini menugaskan:</p>

        <table className="text-sm my-4 w-full">
          <tbody>
            <tr><td className="py-1 w-40 align-top">Nama Petugas</td><td className="align-top">: <strong>{letter.petugas_name}</strong></td></tr>
            <tr><td className="py-1 align-top">ID Petugas</td><td className="align-top">: {letter.petugas_code}</td></tr>
            <tr><td className="py-1 align-top">Dasar Surat Kuasa</td><td className="align-top">: {letter.surat_kuasa_nomor}</td></tr>
            <tr><td className="py-1 align-top">Klien</td><td className="align-top">: {letter.client_name}</td></tr>
            <tr><td className="py-1 align-top">Tanggal Berlaku</td><td className="align-top">: {formatDate(letter.tanggal)} s/d {formatDate(letter.masa_berlaku)}</td></tr>
          </tbody>
        </table>

        <p className="text-sm leading-relaxed">Untuk melakukan penanganan terhadap akun/unit berikut:</p>

        <table className="text-xs w-full border border-slate-400 border-collapse my-3">
          <thead>
            <tr className="bg-slate-100">
              <th className="border border-slate-400 px-2 py-1.5 text-left">No</th>
              <th className="border border-slate-400 px-2 py-1.5 text-left">Nama Debitur</th>
              <th className="border border-slate-400 px-2 py-1.5 text-left">No. Kontrak</th>
              <th className="border border-slate-400 px-2 py-1.5 text-left">No. Polisi</th>
              <th className="border border-slate-400 px-2 py-1.5 text-left">Kendaraan</th>
            </tr>
          </thead>
          <tbody>
            {letter.accounts?.map((a, i) => (
              <tr key={a.id}>
                <td className="border border-slate-400 px-2 py-1.5">{i + 1}</td>
                <td className="border border-slate-400 px-2 py-1.5">{a.nama_debitur}</td>
                <td className="border border-slate-400 px-2 py-1.5">{a.nomor_kontrak}</td>
                <td className="border border-slate-400 px-2 py-1.5">{a.nomor_polisi}</td>
                <td className="border border-slate-400 px-2 py-1.5">{a.merk} {a.model} ({a.warna})</td>
              </tr>
            ))}
          </tbody>
        </table>

        {letter.catatan && <p className="text-sm mt-3"><strong>Keterangan:</strong> {letter.catatan}</p>}

        <p className="text-sm leading-relaxed mt-4">Demikian surat tugas ini dibuat untuk dilaksanakan dengan penuh tanggung jawab.</p>

        <div className="flex justify-between items-end mt-10">
          <div className="text-center">
            <p className="text-xs text-slate-600 mb-1">Pindai untuk verifikasi</p>
            <img src={qrSrc} alt="QR Verifikasi" className="w-28 h-28 border border-slate-200" crossOrigin="anonymous" />
          </div>
          <div className="text-center text-sm">
            <p>{company.city ? `${company.city}, ` : ""}{formatDate(letter.tanggal)}</p>
            <p className="mt-1">Pimpinan,</p>
            <div className="h-20" />
            <p className="font-bold underline">{company.director_name || company.nama}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
