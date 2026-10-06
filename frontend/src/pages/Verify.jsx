import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { API } from "@/lib/api";
import { formatDate } from "@/lib/constants";
import { Shield, CheckCircle2, XCircle, Loader2 } from "lucide-react";

export default function Verify() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/public/surat-tugas/${id}`).then(({ data }) => setData(data)).catch(() => setData({ valid: false })).finally(() => setLoading(false));
  }, [id]);

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 mb-6">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center"><Shield className="w-5 h-5 text-white" /></div>
          <span className="font-heading font-bold text-white text-lg">FieldCollector</span>
        </div>

        <div className="bg-white rounded-3xl shadow-2xl p-7 animate-fade-in">
          {loading ? (
            <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
          ) : (
            <>
              <div className="flex flex-col items-center text-center">
                {data.valid ? (
                  <><CheckCircle2 className="w-16 h-16 text-emerald-500" data-testid="public-verify-status-badge" />
                  <h1 className="font-heading text-xl font-bold text-slate-900 mt-3">Surat Tugas Valid</h1>
                  <p className="text-sm text-slate-500 mt-1">Dokumen ini terverifikasi dan masih aktif.</p></>
                ) : (
                  <><XCircle className="w-16 h-16 text-rose-500" data-testid="public-verify-status-badge" />
                  <h1 className="font-heading text-xl font-bold text-slate-900 mt-3">Tidak Valid</h1>
                  <p className="text-sm text-slate-500 mt-1">{data.message || "Surat tugas tidak aktif atau tidak ditemukan."}</p></>
                )}
              </div>

              {data.nomor && (
                <dl className="mt-6 pt-5 border-t border-slate-100 space-y-3 text-sm">
                  <div className="flex justify-between"><dt className="text-slate-400">Nomor Surat Tugas</dt><dd className="font-mono font-semibold text-slate-800">{data.nomor}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Nama Petugas</dt><dd className="font-medium text-slate-800">{data.petugas_name}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Perusahaan</dt><dd className="font-medium text-slate-800">{data.company_name}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Berlaku s/d</dt><dd className="font-medium text-slate-800">{formatDate(data.tanggal_berlaku)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Status</dt><dd className={`font-semibold ${data.valid ? "text-emerald-600" : "text-rose-600"}`}>{data.valid ? "Aktif" : data.status}</dd></div>
                </dl>
              )}
            </>
          )}
        </div>
        <p className="text-center text-xs text-slate-500 mt-5">Halaman verifikasi publik · Tidak menampilkan data sensitif.</p>
      </div>
    </div>
  );
}
