import { Link } from "react-router-dom";
import { Car, MapPin, ChevronRight, FileCheck2, ClipboardPen } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { ACCOUNT_STATUS } from "@/lib/constants";

export default function TaskCard({ task, dataTestid }) {
  const account = task.account;
  const path = `/app/tugas/${account.id}`;
  return (
    <article className="brand-panel overflow-hidden">
      <Link to={path} data-testid={dataTestid} className="block p-4 active:bg-blue-50 transition-colors">
        <div className="flex items-center justify-between gap-2 mb-3">
          {!task.sudah_dilaporkan && account.status === "DITUGASKAN" ? (
            <span className="rounded-lg px-2.5 py-1 text-xs font-medium bg-amber-50 text-amber-800">Belum dikerjakan</span>
          ) : <StatusBadge map={ACCOUNT_STATUS} value={account.status} />}
          <ChevronRight className="w-4 h-4 text-blue-600 shrink-0" aria-hidden="true" />
        </div>
        <div className="brand-task-info">
          <h3 className="font-heading font-semibold text-slate-900">{account.nama_debitur}</h3>
          <p className="text-xs text-slate-500 font-mono mt-1">Kontrak {account.nomor_kontrak}</p>
          <p className="flex items-start gap-2 text-xs text-slate-700 mt-3"><Car className="w-4 h-4 text-blue-600 shrink-0" aria-hidden="true" /><span>{account.nomor_polisi} · {[account.merk, account.model].filter(Boolean).join(" ") || account.jenis_kendaraan}</span></p>
          <p className="flex items-start gap-2 text-xs text-slate-500 mt-2"><MapPin className="w-4 h-4 shrink-0" aria-hidden="true" /><span>{[account.kabupaten, account.provinsi].filter(Boolean).join(", ") || "Alamat belum tersedia"}</span></p>
          <p className="flex items-start gap-2 text-xs text-blue-600 mt-3 pt-3 border-t border-blue-50"><FileCheck2 className="w-4 h-4 shrink-0" aria-hidden="true" /><span>Surat tugas · {task.letter_nomor || "-"}</span></p>
        </div>
      </Link>
      <div className="px-4 pb-4">
        {task.sudah_dilaporkan ? (
          <p className="text-xs text-emerald-700 bg-emerald-50 rounded-xl px-3 py-2.5">✓ Laporan sudah dikirim</p>
        ) : task.can_report === false ? (
          <p className="text-xs text-amber-800 bg-amber-50 rounded-xl px-3 py-2.5">{task.blocked_reason}</p>
        ) : (
          <Link to={`${path}/laporan`} className="brand-action flex items-center justify-center gap-2 min-h-11 rounded-xl px-3 py-3 text-sm font-semibold" aria-label={`Buat laporan untuk ${account.nama_debitur}`}>
            <ClipboardPen className="w-4 h-4" aria-hidden="true" /> Buat laporan
          </Link>
        )}
      </div>
    </article>
  );
}
