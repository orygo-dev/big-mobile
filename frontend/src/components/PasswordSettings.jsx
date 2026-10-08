import {useState} from "react";
import {useNavigate} from "react-router-dom";
import {useAuth} from "@/context/AuthContext";
import api, {clearToken, errMsg} from "@/lib/api";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {toast} from "sonner";

export default function PasswordSettings() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const {setUser} = useAuth();
  const navigate = useNavigate();
  const save = async (event) => {
    event.preventDefault();
    if (next !== confirm) {toast.error("Konfirmasi password tidak cocok"); return;}
    setBusy(true);
    try {
      await api.post("/auth/password", {current_password: current, new_password: next});
      clearToken(); setUser(false); navigate("/login", {replace: true});
      toast.success("Password diubah. Silakan login kembali.");
    } catch (error) {toast.error(errMsg(error));} finally {setBusy(false);}
  };
  return <form onSubmit={save} className="brand-panel p-5 space-y-3" data-testid="password-settings">
    <h2 className="font-semibold text-slate-800">Keamanan akun</h2>
    <p className="text-xs text-slate-500">Gunakan minimal 12 karakter. Mengganti password mengakhiri seluruh sesi akun.</p>
    <label className="block text-sm">Password saat ini<Input type="password" required autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} /></label>
    <label className="block text-sm">Password baru<Input type="password" required minLength={12} maxLength={72} autoComplete="new-password" value={next} onChange={(event) => setNext(event.target.value)} /></label>
    <label className="block text-sm">Konfirmasi password baru<Input type="password" required minLength={12} maxLength={72} autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} /></label>
    <Button type="submit" disabled={busy}>{busy ? "Menyimpan…" : "Ganti password"}</Button>
  </form>;
}
