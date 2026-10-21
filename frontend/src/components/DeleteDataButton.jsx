import { useState } from "react";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Loader2, Trash2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

export default function DeleteDataButton({ endpoint, name, onDeleted, testId, description }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const remove = async () => {
    if (busy || reason.trim().length < 3) return;
    setBusy(true);
    try {
      setError("");
      try {
        await api.post(`${endpoint}/delete`, {reason: reason.trim()});
      } catch (error) {
        const status = error.response?.status;
        const missingRoute = status === 404 && error.response?.data?.detail === "Not Found";
        if (status !== 405 && !missingRoute) throw error;
        // Older backends may provide only REST DELETE. Never retry an ambiguous error.
        await api.delete(endpoint, {data: {reason: reason.trim()}});
      }
      toast.success("Data berhasil dihapus");
      setOpen(false); setReason("");
      onDeleted?.();
    } catch (error) { setError(errMsg(error)); }
    finally { setBusy(false); }
  };
  return <>
    <button type="button" aria-label={`Hapus ${name}`} title="Hapus data" data-testid={testId} onClick={() => {setOpen(true);setError("");setReason("");}} className="p-1.5 text-rose-600 hover:bg-rose-50 rounded-lg"><Trash2 className="w-4 h-4" /></button>
    <Dialog open={open} onOpenChange={(value) => { if (!busy) setOpen(value); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Hapus data?</DialogTitle><DialogDescription className="break-words">{name} akan dihapus permanen. {description || "Jika masih terkait data lain, hapus record terkait yang salah terlebih dahulu. Alasan penghapusan dicatat di Audit Log."}</DialogDescription></DialogHeader>
        <label className="block text-sm space-y-2">Alasan penghapusan<Textarea required minLength={3} maxLength={500} disabled={busy} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Contoh: salah input atau data duplikat" data-testid="delete-reason"/></label>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>Batal</Button>
          <Button variant="destructive" disabled={busy || reason.trim().length < 3} onClick={remove} data-testid="confirm-delete-button">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Hapus Permanen"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </>;
}
