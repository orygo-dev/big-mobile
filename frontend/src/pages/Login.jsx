import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useBranding } from "@/context/BrandingContext";
import { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Eye, EyeOff, Layers, ArrowRight, LockKeyhole } from "lucide-react";
import LoginBackground from "@/components/LoginBackground";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const { appName, logo, loginBackground } = useBranding();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      const u = await login(email.trim(), password);
      toast.success(`Selamat datang, ${u.name}`);
      navigate(u.role === "admin" ? "/admin" : "/app", { replace: true });
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-shell">
      <LoginBackground preset={loginBackground.preset} imageUrl={loginBackground.image_url} />
      <section className="login-card relative w-full max-w-md" aria-labelledby="login-heading">
        <div className="flex items-center justify-center mb-7">
          {logo ? (
            <img src={logo} alt={appName} className="h-14 w-auto max-w-[260px] object-contain" data-testid="login-logo" />
          ) : (
            <div className="flex items-center gap-3 min-w-0"><span className="brand-mark p-2.5 rounded-xl shrink-0"><Layers className="w-6 h-6" aria-hidden="true" /></span><span className="font-heading text-2xl font-semibold text-slate-900 tracking-tight break-words min-w-0">{appName}</span></div>
          )}
        </div>

        <div>
          <p className="login-eyebrow">WORKSPACE OPERASIONAL</p>
          <h1 id="login-heading" className="font-heading text-3xl font-semibold text-slate-900 tracking-tight mt-2">Selamat datang kembali</h1>
          <p className="text-sm text-slate-500 mt-2 mb-7">Masuk untuk mengelola penugasan dan laporan lapangan Anda.</p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="email" className="text-slate-700">Email</Label>
              <Input id="email" data-testid="login-email-input" type="email" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="nama@perusahaan.com"
                autoComplete="username" required className="mt-1.5 h-11 rounded-xl" />
            </div>
            <div>
              <Label htmlFor="password" className="text-slate-700">Password</Label>
              <div className="relative mt-1.5">
                <Input id="password" data-testid="login-password-input" type={show ? "text" : "password"}
                  value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••"
                  autoComplete="current-password" required className="h-11 rounded-xl pr-11" />
                <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Sembunyikan password" : "Tampilkan password"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div role="alert" data-testid="login-error" className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
                {error}
              </div>
            )}

            <Button type="submit" data-testid="login-submit-button" disabled={loading}
              className="brand-action w-full h-12 rounded-xl font-semibold">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Masuk ke aplikasi <ArrowRight className="w-4 h-4" /></>}
            </Button>
          </form>

          <p className="flex items-center justify-center gap-2 mt-6 pt-5 border-t border-blue-50 text-xs text-slate-500"><LockKeyhole className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />Akses hanya untuk pengguna terdaftar</p>
        </div>
      </section>
    </main>
  );
}
