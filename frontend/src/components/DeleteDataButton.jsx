import { useState } from "react";
import api, { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function DeleteDataButton({ endpoint, name, onDeleted, testId }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const remove = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api.delete(endpoint);
      toast.success("Data berhasil dihapus");
      setOpen(false);
      onDeleted();
    } catch (error) { toast.error(errMsg(error)); }
    finally { setBusy(false); }
  };
  return <>
    <button type="button" aria-label={`Hapus ${name}`} title="Hapus data" data-testid={testId} onClick={() => setOpen(true)} className="p-1.5 text-rose-600 hover:bg-rose-50 rounded-lg"><Trash2 className="w-4 h-4" /></button>
    <Dialog open={open} onOpenChange={(value) => { if (!busy) setOpen(value); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Hapus data?</DialogTitle><DialogDescription className="break-words">{name} akan dihapus permanen. Data yang sudah digunakan dalam penugasan atau laporan tidak dapat dihapus.</DialogDescription></DialogHeader>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>Batal</Button>
          <Button variant="destructive" disabled={busy} onClick={remove} data-testid="confirm-delete-button">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Hapus Permanen"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </>;
}
