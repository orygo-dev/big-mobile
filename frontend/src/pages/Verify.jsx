import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { API } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/constants";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import BrandIdentity from "@/components/BrandIdentity";

export default function Verify() {
  const { id, code } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const url = code ? `${API}/public/verify/${code}` : `${API}/public/surat-tugas/${id}`;
    axios.get(url).then(({ data }) => setData(data)).catch(() => setData({ valid: false })).finally(() => setLoading(false));
  }, [id, code]);

  const statusLabel = data?.doc_status || (data?.valid ? "VALID" : (data?.status || "TIDAK VALID"));

  return (
    <div className="brand-login min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 mb-6">
          <BrandIdentity />
        </div>

        <div className="brand-panel brand-login-card p-6 sm:p-7 animate-fade-in">
          {loading ? (
            <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
          ) : (
            <>
              <div className="flex flex-col items-center text-center">
                {data.valid ? (
                  <><CheckCircle2 className="w-16 h-16 text-emerald-500" data-testid="public-verify-status-badge" />
                  <h1 className="font-heading text-xl font-bold text-slate-900 mt-3">Dokumen {statusLabel}</h1>
                  <p className="text-sm text-slate-500 mt-1">Dokumen ini terverifikasi dan tercatat di sistem.</p></>
                ) : (
                  <><XCircle className="w-16 h-16 text-rose-500" data-testid="public-verify-status-badge" />
                  <h1 className="font-heading text-xl font-bold text-slate-900 mt-3">{statusLabel}</h1>
                  <p className="text-sm text-slate-500 mt-1">{data.message || "Dokumen tidak aktif atau tidak ditemukan."}</p></>
                )}
              </div>

              {data.nomor && (
                <dl className="mt-6 pt-5 border-t border-slate-100 space-y-3 text-sm">
                  <div className="flex justify-between gap-4"><dt className="text-slate-400">Nomor Surat</dt><dd className="font-mono font-semibold text-slate-800 text-right">{data.nomor}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-slate-400">Perusahaan</dt><dd className="font-medium text-slate-800 text-right">{data.company_name}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-slate-400">Nama Petugas</dt><dd className="font-medium text-slate-800 text-right">{data.petugas_name}</dd></div>
                  {data.issued_at && <div className="flex justify-between gap-4"><dt className="text-slate-400">Diterbitkan</dt><dd className="font-medium text-slate-800 text-right">{formatDateTime(data.issued_at)}</dd></div>}
                  <div className="flex justify-between gap-4"><dt className="text-slate-400">Berlaku s/d</dt><dd className="font-medium text-slate-800 text-right">{formatDate(data.valid_until || data.tanggal_berlaku)}</dd></div>
                  {data.generate_code && <div className="flex justify-between gap-4"><dt className="text-slate-400">Kode Generate</dt><dd className="font-mono text-xs text-slate-600 text-right break-all">{data.generate_code}</dd></div>}
                  <div className="flex justify-between gap-4"><dt className="text-slate-400">Status</dt><dd className={`font-semibold ${data.valid ? "text-emerald-600" : "text-rose-600"}`}>{statusLabel}</dd></div>
                </dl>
              )}
            </>
          )}
        </div>
        <p className="text-center text-xs text-slate-500 mt-5">Halaman verifikasi publik · Data debitur tidak ditampilkan.</p>
      </div>
    </div>
  );
}
