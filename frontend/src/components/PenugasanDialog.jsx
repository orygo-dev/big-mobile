import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, ClipboardList, CheckCircle2, FileText } from "lucide-react";
import { toast } from "sonner";

// 1 Penugasan = 1 Unit = 1 Petugas = 1 Surat Penugasan.
// `accountId` (optional) preselects a unit (e.g. from the Kontrak & Unit page).
export default function PenugasanDialog({ open, onOpenChange, accountId = null, onSuccess }) {
  const navigate = useNavigate();
  const requestKey = useRef(null);
  const [petugasList, setPetugasList] = useState([]);
  const [unitList, setUnitList] = useState([]);
  const [petugasId, setPetugasId] = useState("");
  const [unitId, setUnitId] = useState(accountId || "");
  const [validFrom, setValidFrom] = useState(new Date().toISOString().slice(0, 10));
  const [validUntil, setValidUntil] = useState("");
  const [catatan, setCatatan] = useState("");
  const [saving, setSaving] = useState(false);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [optionsError, setOptionsError] = useState("");
  const [result, setResult] = useState(null); // success payload

  useEffect(() => {
    if (!open) return;
    requestKey.current = crypto.randomUUID();
    setResult(null);
    setPetugasId(""); setCatatan(""); setValidUntil("");
    setValidFrom(new Intl.DateTimeFormat("en-CA", {timeZone: "Asia/Jakarta", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date()));
    setUnitId(accountId || "");
    setLoadingOptions(true); setOptionsError(""); setPetugasList([]); setUnitList([]);
    let cancelled = false;
    Promise.all([api.get("/petugas"), accountId ? Promise.resolve(null) : api.get("/akun", {params: {available: true, limit: 1000, page: 1}})])
      .then(([officers, units]) => { if (!cancelled) {setPetugasList(officers.data.filter((p) => p.status === "aktif")); setUnitList(units?.data.items || []);} })
      .catch((e) => {if (!cancelled) setOptionsError(errMsg(e));})
      .finally(() => {if (!cancelled) setLoadingOptions(false);});
    return () => {cancelled = true;};
  }, [open, accountId]);

  const submit = async () => {
    if (!unitId) { toast.error("Pilih satu unit terlebih dahulu"); return; }
    if (!petugasId) { toast.error("Pilih satu petugas terlebih dahulu"); return; }
    if (!validFrom || (validUntil && validUntil < validFrom)) {toast.error("Periksa tanggal mulai dan akhir penugasan"); return;}
    if (saving) return;
    setSaving(true);
    try {
      const { data } = await api.post("/penugasan", {
        petugas_id: petugasId,
        account_id: unitId,
        valid_from: validFrom,
        valid_until: validUntil || null,
        catatan,
      }, {headers: {"Idempotency-Key": requestKey.current}});
      toast.success("Penugasan berhasil dibuat");
      setResult(data);
      onSuccess?.(data);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const close = () => {
    if (saving) return;
    onOpenChange(false);
    setPetugasId(""); setUnitId(accountId || ""); setCatatan(""); setValidUntil("");
    setResult(null);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) close(); else onOpenChange(v); }}>
      <DialogContent className="sm:max-w-md" data-testid="penugasan-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-heading">
            <ClipboardList className="w-5 h-5 text-blue-600" /> Buat Penugasan
          </DialogTitle>
        </DialogHeader>

        {result ? (
          <div className="py-2 space-y-4" data-testid="penugasan-success-panel">
            <div className="flex flex-col items-center text-center gap-2 py-2">
              <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8 text-emerald-600" />
              </div>
              <p className="font-heading font-semibold text-slate-800">Penugasan berhasil dibuat</p>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-xl divide-y divide-slate-100 text-sm">
              <div className="flex justify-between px-3 py-2">
                <span className="text-slate-400">Penugasan ID</span>
                <span className="font-mono text-slate-700 text-xs" data-testid="penugasan-result-id">{result.assignment_number || result.assignment_id}</span>
              </div>
              <div className="flex justify-between px-3 py-2">
                <span className="text-slate-400">No. Surat Penugasan</span>
                <span className="font-mono font-semibold text-slate-800 text-xs" data-testid="penugasan-result-docnum">{result.document_number}</span>
              </div>
            </div>
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={close} className="rounded-xl">Tutup</Button>
              <Button onClick={() => { close(); navigate(`/admin/surat-tugas/${result.id}/dokumen`); }}
                className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="penugasan-lihat-surat-button">
                <FileText className="w-4 h-4 mr-1" /> Lihat Surat Penugasan
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <>
            <div className="space-y-4 py-2">
              {loadingOptions && <p className="text-sm text-blue-600">Memuat unit dan petugas…</p>}
              {optionsError && <p role="alert" className="text-sm text-red-600">{optionsError} Tutup dan buka kembali untuk mencoba lagi.</p>}
              <div>
                <Label>Pilih Unit</Label>
                {accountId ? (
                  <div className="mt-1.5 text-sm bg-blue-50 border border-blue-100 rounded-xl px-3 py-2.5 text-blue-800" data-testid="penugasan-unit-fixed">
                    Unit terpilih sudah ditetapkan.
                  </div>
                ) : (
                  <Select value={unitId} onValueChange={setUnitId}>
                    <SelectTrigger className="mt-1.5 rounded-xl" data-testid="penugasan-unit-select">
                      <SelectValue placeholder="-- Pilih unit tanpa penugasan aktif --" />
                    </SelectTrigger>
                    <SelectContent>
                      {unitList.length === 0 && <div className="px-3 py-2 text-sm text-slate-400">Tidak ada unit tersedia</div>}
                      {unitList.map((u) => (
                        <SelectItem key={u.id} value={u.id}>
                          {u.nama_debitur} · {u.nomor_polisi || "-"} · {u.nomor_kontrak}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
              <div>
                <Label>Pilih Petugas</Label>
                <Select value={petugasId} onValueChange={setPetugasId}>
                  <SelectTrigger className="mt-1.5 rounded-xl" data-testid="penugasan-petugas-select">
                    <SelectValue placeholder="-- Pilih Petugas --" />
                  </SelectTrigger>
                  <SelectContent>
                    {petugasList.map((p) => (
                      <SelectItem key={p.id} value={p.id}>{p.name} ({p.petugas_code})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Berlaku Dari</Label>
                  <Input type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} className="mt-1.5 rounded-xl" data-testid="penugasan-valid-from-input" />
                </div>
                <div>
                  <Label>Berlaku Sampai</Label>
                  <Input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} className="mt-1.5 rounded-xl" data-testid="penugasan-valid-until-input" />
                </div>
              </div>
              <div>
                <Label>Catatan untuk Petugas (opsional)</Label>
                <Textarea value={catatan} onChange={(e) => setCatatan(e.target.value)} placeholder="Instruksi tambahan..." className="mt-1.5 rounded-xl" data-testid="penugasan-catatan-input" />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={close} className="rounded-xl">Batal</Button>
              <Button onClick={submit} disabled={saving || loadingOptions || !!optionsError} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="penugasan-submit-button">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Buat Penugasan"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
