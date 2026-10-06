import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { API, errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, Printer, Download, ArrowLeft, CheckCircle2, Ban, FileText } from "lucide-react";
import { toast } from "sonner";

const DAYS = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];

function fdate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}
function dayName(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? "" : DAYS[d.getDay()];
}
function fdatetime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return `${String(d.getDate()).padStart(2, "0")} ${MONTHS[d.getMonth()].slice(0, 3)} ${d.getFullYear()}, ${String(d.getHours()).padStart(2, "0")}.${String(d.getMinutes()).padStart(2, "0")} WIB`;
}
function subst(text, map) {
  if (!text) return "";
  return text.replace(/\{(\w+)\}/g, (_, k) => (map[k] != null ? map[k] : `{${k}}`));
}

const Logo = () => (
  <div style={{ width: 54, height: 54, flexShrink: 0, borderRadius: 8, background: "#C0211F", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 800, fontSize: 20, fontFamily: "Arial" }}>
    FC
  </div>
);

function DocHeader({ title, nomor }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, borderBottom: "3px solid #111", paddingBottom: 10, marginBottom: 14 }}>
      <Logo />
      <div style={{ flex: 1, textAlign: "center" }}>
        <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: 1 }}>{title}</div>
        <div style={{ fontSize: 12, marginTop: 2 }}>NO: {nomor}</div>
      </div>
      <div style={{ width: 54 }} />
    </div>
  );
}

function Footer({ data }) {
  const L = data.letter;
  return (
    <div style={{ position: "absolute", bottom: "12mm", left: "18mm", right: "18mm", borderTop: "1px solid #999", paddingTop: 4, fontSize: 8, color: "#444", display: "flex", justifyContent: "space-between", gap: 8 }}>
      <span>KODE GENERATE: {L.generate_code || "-"}</span>
      <span>DICETAK OLEH: {data.generated_by || "-"} · {fdatetime(data.generated_at)}</span>
    </div>
  );
}

export default function SuratPenugasanDoc() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get(`/surat-tugas/${id}/document`).then(({ data }) => setDoc(data))
      .catch((e) => { toast.error(errMsg(e)); navigate("/admin/surat-tugas"); }).finally(() => setLoading(false));
  }, [id, navigate]);
  useEffect(() => { load(); }, [load]);

  const finalize = async () => {
    setBusy(true);
    try { const { data } = await api.post(`/surat-tugas/${id}/finalize`); setDoc(data); toast.success("Dokumen difinalisasi. Nomor & kode terkunci."); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
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

  const d = doc.data;
  const t = doc.template || {};
  const finalized = doc.is_finalized;
  const firstAcc = d.accounts[0] || {};
  const map = {
    unit_count: d.accounts.length, finance_name: d.finance.name, contract_number: firstAcc.contract_number,
    company_name: d.company.name, valid_from: fdate(d.letter.valid_from), valid_until: fdate(d.letter.valid_until),
    day_name: dayName(d.letter.issue_date), date: fdate(d.letter.issue_date),
  };
  const qrSrc = `${API}/surat-tugas/${id}/qr`;

  const Row = ({ label, value }) => (
    <tr><td style={{ padding: "1px 0", width: 150, verticalAlign: "top" }}>{label}</td><td style={{ verticalAlign: "top" }}>: {value || "-"}</td></tr>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#e2e8f0", paddingBottom: 40 }}>
      <style>{`
        @page { size: A4; margin: 0; }
        @media print {
          body { background: #fff !important; }
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
          <button onClick={() => navigate("/admin/surat-tugas")} className="flex items-center gap-1.5 text-sm text-slate-700 hover:text-slate-900" data-testid="doc-back">
            <ArrowLeft className="w-4 h-4" /> Kembali
          </button>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${finalized ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`} data-testid="doc-status-badge">
              {finalized ? "ACTIVE / FINALIZED" : "DRAFT / PREVIEW"}
            </span>
            {!finalized && doc.letter_status === "aktif" && (
              <Button onClick={finalize} disabled={busy} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="doc-finalize-button">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <><CheckCircle2 className="w-4 h-4 mr-1" /> Finalisasi</>}
              </Button>
            )}
            <Button onClick={() => doPrint("")} variant="outline" className="rounded-xl" data-testid="doc-print-button"><Printer className="w-4 h-4 mr-1" /> Cetak</Button>
            <Button onClick={() => doPrint(".pdf")} className="rounded-xl bg-slate-900 hover:bg-slate-800" data-testid="doc-download-button"><Download className="w-4 h-4 mr-1" /> Download PDF</Button>
            {doc.letter_status === "aktif" && (
              <Button onClick={cancel} disabled={busy} variant="outline" className="rounded-xl border-rose-200 text-rose-600 hover:bg-rose-50" data-testid="doc-cancel-button"><Ban className="w-4 h-4 mr-1" /> Batalkan</Button>
            )}
          </div>
        </div>
        {!finalized && <p className="text-xs text-amber-700 mt-2 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Ini pratinjau. Klik Finalisasi untuk mengunci nomor surat, kode generate, dan QR verifikasi.</p>}
      </div>

      {/* PAGE 1 */}
      <div className="doc-page" data-testid="doc-page-1">
        <DocHeader title="SURAT PENUGASAN" nomor={d.letter.document_number || "(akan dibuat saat finalisasi)"} />
        <p style={{ margin: "8px 0 2px" }}>Saya yang bertanda tangan di bawah ini:</p>
        <table><tbody>
          <Row label="Nama" value={d.company.director_name} />
          <Row label="Jabatan" value={d.company.director_position} />
        </tbody></table>
        <p style={{ margin: "4px 0" }}>Dalam hal ini bertindak untuk dan atas nama <b>{d.company.name}</b> yang berkedudukan di {d.company.city || "-"}, selanjutnya disebut sebagai "PERSEROAN".</p>

        <p style={{ margin: "10px 0 2px" }}>Dengan ini memberikan tugas kepada:</p>
        <table><tbody>
          <Row label="Nama" value={d.officer.name} />
          <Row label="Nik" value={d.officer.nik} />
          <Row label="Jabatan" value={d.officer.position} />
          <Row label="No. Sertifikasi" value={`${d.officer.certification_number || "-"}${d.officer.certification_valid_until ? ` (berlaku s.d. ${fdate(d.officer.certification_valid_until)})` : ""}`} />
        </tbody></table>
        <p style={{ margin: "4px 0" }}>Selanjutnya disebut sebagai "PENERIMA TUGAS". PENERIMA TUGAS dalam menjalankan penugasan ini bertindak untuk dan atas nama "PERSEROAN", sebatas kewenangan yang diberikan dalam Surat Penugasan ini, untuk melaksanakan hal-hal sebagai berikut:</p>

        <div className="doc-h2">RUANG LINGKUP TUGAS</div>
        <ol>
          <li>
            {subst(t.ruang_lingkup_intro, map)}
            {d.accounts.map((a, i) => (
              <div key={i} style={{ margin: "4px 0 6px", paddingLeft: 4 }}>
                <table className="spec-table"><tbody>
                  <Row label="Debitur" value={a.debtor_name} />
                  <Row label="Alamat" value={a.debtor_address} />
                </tbody></table>
                <div style={{ margin: "3px 0 2px" }}>Dengan spesifikasi kendaraan sebagai berikut:</div>
                <table className="spec-table"><tbody>
                  <Row label="Jenis/Merk" value={a.brand} />
                  <Row label="Nomor Polisi" value={a.license_plate} />
                  <Row label="Nomor Rangka" value={a.chassis_number} />
                  <Row label="Nomor Mesin" value={a.engine_number} />
                  <Row label="Warna/Tahun Unit" value={`${a.color || "-"} / ${a.year || "-"}`} />
                </tbody></table>
              </div>
            ))}
          </li>
          <li>{subst(t.ruang_lingkup_closing, map)}</li>
        </ol>

        <div className="doc-h2">LARANGAN</div>
        <ol>{(t.larangan || []).map((x, i) => <li key={i}>{x}</li>)}</ol>
        <Footer data={d} />
      </div>

      {/* PAGE 2 */}
      <div className="doc-page" data-testid="doc-page-2">
        <DocHeader title="SURAT PENUGASAN" nomor={d.letter.document_number || "(akan dibuat saat finalisasi)"} />
        <div className="doc-h2">KEWAJIBAN DAN TANGGUNG JAWAB</div>
        <ol>{(t.kewajiban || []).map((x, i) => <li key={i}>{x}</li>)}</ol>

        <div className="doc-h2">BATAS KEWENANGAN DAN PELANGGARAN</div>
        {(t.batas_kewenangan || []).map((x, i) => <p key={i} style={{ margin: "3px 0" }}>{x}</p>)}

        <div className="doc-h2">MASA BERLAKU</div>
        <p style={{ margin: "3px 0" }}>{subst(t.masa_berlaku, map)}</p>

        <p style={{ margin: "18px 0 0" }}>{d.company.city || "-"}, {fdate(d.letter.issue_date)}</p>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
          <div style={{ textAlign: "center", width: "45%" }}>
            <div>PENERIMA TUGAS</div>
            <div style={{ height: 56 }} />
            <div style={{ fontWeight: 700 }}>({d.officer.name})</div>
          </div>
          <div style={{ textAlign: "center", width: "45%" }}>
            <div>PEMBERI TUGAS</div>
            <div>{d.company.director_position} {d.company.name}</div>
            <div style={{ height: 36 }} />
            <div style={{ fontWeight: 700 }}>({d.company.director_name})</div>
          </div>
        </div>

        <div className="doc-h2" style={{ marginTop: 24 }}>VERIFIKASI SURAT PENUGASAN</div>
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          {finalized ? <img src={qrSrc} alt="QR" style={{ width: 90, height: 90, border: "1px solid #ddd" }} crossOrigin="anonymous" data-testid="doc-qr" />
            : <div style={{ width: 90, height: 90, border: "1px dashed #bbb", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 8, color: "#999", textAlign: "center", padding: 4 }}>QR muncul setelah finalisasi</div>}
          <div style={{ fontSize: 9 }}>
            <div>Kode: <b>{d.letter.generate_code || "(belum dibuat)"}</b></div>
            <div style={{ marginTop: 4, maxWidth: 360 }}>{t.verifikasi_note}</div>
          </div>
        </div>
        <Footer data={d} />
      </div>

      {/* PAGE 3 — BASTK (per unit) */}
      {d.accounts.map((a, idx) => (
        <div className="doc-page" data-testid={`doc-page-bastk-${idx}`} key={idx}>
          <div className="wm">{d.company.company_code || "FC"}</div>
          <DocHeader title="BERITA ACARA SERAH TERIMA KENDARAAN" nomor={`Reg: ${d.letter.register_number || "(akan dibuat)"}${d.accounts.length > 1 ? `-${idx + 1}` : ""}`} />
          <p style={{ margin: "4px 0" }}>Pada hari ini, {dayName(d.letter.issue_date)}, {fdate(d.letter.issue_date)}, yang bertanda tangan di bawah ini:</p>
          <table className="spec-table"><tbody>
            <Row label="Nama" value={a.debtor_name || "-"} />
            <Row label="Alamat" value={a.debtor_address || "-"} />
            <Row label="No. KTP" value={a.debtor_nik || "-"} />
            <Row label="No. Telp" value={a.debtor_phone || "-"} />
          </tbody></table>
          <p style={{ margin: "6px 0" }}>{subst(t.bastk_handover, map)}</p>
          <table className="spec-table"><tbody>
            <Row label="Merk / Tipe" value={a.brand} />
            <Row label="Tahun / Warna" value={`${a.year || "-"} / ${a.color || "-"}`} />
            <Row label="STNK atas nama" value={a.stnk_name} />
            <Row label="Nomor Polisi" value={a.license_plate} />
            <Row label="No. Mesin" value={a.engine_number} />
            <Row label="No. Rangka" value={a.chassis_number} />
          </tbody></table>

          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            {[0, 1].map((side) => {
              const items = (t.checklist_items || []);
              const slice = side === 0 ? items.slice(0, 15) : items.slice(15);
              const offset = side === 0 ? 0 : 15;
              return (
                <table className="chk" key={side}>
                  <thead><tr><th>NO</th><th>KELENGKAPAN</th><th>ADA</th><th>TIDAK</th><th>IMITASI</th><th>KONDISI</th></tr></thead>
                  <tbody>
                    {slice.map((it, i) => (
                      <tr key={i}>
                        <td style={{ textAlign: "center" }}>{offset + i + 1}</td>
                        <td>{it}</td>
                        <td className="cbox"></td><td className="cbox"></td><td className="cbox"></td><td className="cbox"></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })}
          </div>

          <p style={{ margin: "8px 0", fontSize: 9.5 }}>{t.bastk_ketentuan}</p>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, textAlign: "center", fontSize: 9.5 }}>
            <div style={{ width: "24%" }}><div>YANG MENYERAHKAN</div><div style={{ height: 40 }} /><div>(-)</div><div>Debitur/Pemakai Unit</div></div>
            <div style={{ width: "24%" }}><div>YANG MENERIMA</div><div style={{ height: 40 }} /><div style={{ fontWeight: 700 }}>({d.officer.name})</div><div>{d.officer.position}</div><div>No. HP: {d.officer.phone || "-"}</div></div>
            <div style={{ width: "24%" }}><div>MENGETAHUI</div><div style={{ height: 40 }} /><div>(&nbsp;&nbsp;&nbsp;&nbsp;)</div><div>Suami/Istri/Saksi/Penjamin</div></div>
            <div style={{ width: "24%" }}><div>YANG MENERIMA</div><div style={{ height: 40 }} /><div>(&nbsp;&nbsp;&nbsp;&nbsp;)</div><div>Admin Coll</div></div>
          </div>

          <div style={{ marginTop: 10, fontSize: 9 }}>
            <div style={{ fontWeight: 700 }}>Catatan:</div>
            {(t.distribution || []).map((x, i) => <div key={i}>{subst(x, map)}</div>)}
          </div>
          <Footer data={d} />
        </div>
      ))}
    </div>
  );
}
