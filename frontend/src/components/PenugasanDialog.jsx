import { useState, useEffect } from "react";
import api, { errMsg } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, ClipboardList } from "lucide-react";
import { toast } from "sonner";

export default function PenugasanDialog({ open, onOpenChange, accountIds, onSuccess }) {
  const [petugasList, setPetugasList] = useState([]);
  const [petugasId, setPetugasId] = useState("");
  const [tanggalTugas, setTanggalTugas] = useState(new Date().toISOString().slice(0, 10));
  const [masaBerlaku, setMasaBerlaku] = useState("");
  const [catatan, setCatatan] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      api.get("/petugas").then(({ data }) => setPetugasList(data.filter((p) => p.status === "aktif"))).catch(() => {});
    }
  }, [open]);

  const submit = async () => {
    if (!petugasId) { toast.error("Pilih petugas terlebih dahulu"); return; }
    if (saving) return;
    setSaving(true);
    try {
      const { data } = await api.post("/penugasan", {
        petugas_id: petugasId,
        account_ids: accountIds,
        tanggal_tugas: tanggalTugas,
        masa_berlaku: masaBerlaku || null,
        catatan,
      });
      toast.success(`Surat Tugas ${data.nomor} berhasil dibuat`);
      onOpenChange(false);
      setPetugasId(""); setCatatan(""); setMasaBerlaku("");
      onSuccess?.(data);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="penugasan-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-heading">
            <ClipboardList className="w-5 h-5 text-blue-600" /> Buat Penugasan
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="text-sm bg-blue-50 border border-blue-100 rounded-xl px-3 py-2 text-blue-800">
            {accountIds.length} akun/unit terpilih akan dimasukkan ke dalam Surat Tugas.
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
              <Label>Tanggal Tugas</Label>
              <Input type="date" value={tanggalTugas} onChange={(e) => setTanggalTugas(e.target.value)} className="mt-1.5 rounded-xl" data-testid="penugasan-tanggal-input" />
            </div>
            <div>
              <Label>Masa Berlaku</Label>
              <Input type="date" value={masaBerlaku} onChange={(e) => setMasaBerlaku(e.target.value)} className="mt-1.5 rounded-xl" data-testid="penugasan-masa-input" />
            </div>
          </div>
          <div>
            <Label>Catatan untuk Petugas</Label>
            <Textarea value={catatan} onChange={(e) => setCatatan(e.target.value)} placeholder="Instruksi tambahan..." className="mt-1.5 rounded-xl" data-testid="penugasan-catatan-input" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="rounded-xl">Batal</Button>
          <Button onClick={submit} disabled={saving} className="rounded-xl bg-blue-600 hover:bg-blue-700" data-testid="penugasan-submit-button">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Buat Surat Tugas"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
