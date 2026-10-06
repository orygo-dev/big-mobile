export const ACCOUNT_STATUS = {
  BELUM_DITUGASKAN: { label: "Belum Ditugaskan", cls: "bg-slate-100 text-slate-700 border-slate-200" },
  DITUGASKAN: { label: "Ditugaskan", cls: "bg-sky-100 text-sky-700 border-sky-200" },
  DALAM_PROSES: { label: "Dalam Proses", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  UNIT_DITEMUKAN: { label: "Unit Ditemukan", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  TIDAK_DITEMUKAN: { label: "Tidak Ditemukan", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  ALAMAT_TIDAK_SESUAI: { label: "Alamat Tidak Sesuai", cls: "bg-orange-100 text-orange-800 border-orange-200" },
  SELESAI: { label: "Selesai", cls: "bg-blue-100 text-blue-800 border-blue-200" },
};

export const REPORT_STATUS = {
  UNIT_DITEMUKAN: { label: "Unit Ditemukan", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  TIDAK_DITEMUKAN: { label: "Tidak Ditemukan", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  ALAMAT_TIDAK_SESUAI: { label: "Alamat Tidak Sesuai", cls: "bg-orange-100 text-orange-800 border-orange-200" },
  PINDAH_ALAMAT: { label: "Pindah Alamat", cls: "bg-orange-100 text-orange-800 border-orange-200" },
  UNIT_TIDAK_ADA: { label: "Unit Tidak Ada di Lokasi", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  LAINNYA: { label: "Lainnya", cls: "bg-slate-100 text-slate-700 border-slate-200" },
};

export const LETTER_STATUS = {
  draft: { label: "Draft", cls: "bg-slate-100 text-slate-700 border-slate-200" },
  aktif: { label: "Aktif", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  selesai: { label: "Selesai", cls: "bg-blue-100 text-blue-800 border-blue-200" },
  dibatalkan: { label: "Dibatalkan", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  kedaluwarsa: { label: "Kedaluwarsa", cls: "bg-amber-100 text-amber-800 border-amber-200" },
};

export const SK_STATUS = {
  aktif: { label: "Aktif", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  berakhir: { label: "Berakhir", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  dicabut: { label: "Dicabut", cls: "bg-rose-100 text-rose-800 border-rose-200" },
};

const MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];

export function formatDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function formatDateTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${hh}:${mm} WIB`;
}

export function formatTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d)) return "-";
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
