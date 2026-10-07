import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useBranding } from "@/context/BrandingContext";
import { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const { appName, logo } = useBranding();
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
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "radial-gradient(circle at 20% 30%, #1E3A8A 0, transparent 40%), radial-gradient(circle at 80% 70%, #2563EB 0, transparent 40%)" }} />
      <div className="relative w-full max-w-md">
        <div className="flex items-center justify-center mb-6">
          {logo ? (
            <img src={logo} alt={appName} className="h-20 w-auto max-w-[260px] object-contain" data-testid="login-logo" />
          ) : (
            <h1 className="font-heading text-3xl font-extrabold text-white tracking-tight">{appName}</h1>
          )}
        </div>

        <div className="bg-white rounded-3xl shadow-2xl p-7 animate-fade-in">
          <h2 className="font-heading text-xl font-bold text-slate-900">Masuk ke Akun</h2>
          <p className="text-sm text-slate-500 mt-1 mb-6">Gunakan email dan password Anda.</p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="email" className="text-slate-700">Email</Label>
              <Input id="email" data-testid="login-email-input" type="email" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="nama@perusahaan.com"
                required className="mt-1.5 h-11 rounded-xl" />
            </div>
            <div>
              <Label htmlFor="password" className="text-slate-700">Password</Label>
              <div className="relative mt-1.5">
                <Input id="password" data-testid="login-password-input" type={show ? "text" : "password"}
                  value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••"
                  required className="h-11 rounded-xl pr-11" />
                <button type="button" onClick={() => setShow(!show)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div data-testid="login-error" className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
                {error}
              </div>
            )}

            <Button type="submit" data-testid="login-submit-button" disabled={loading}
              className="w-full h-11 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Masuk"}
            </Button>
          </form>

          <div className="mt-6 pt-5 border-t border-slate-100 text-xs text-slate-500 space-y-1">
            <p className="font-semibold text-slate-600">Akun demo:</p>
            <p>Admin: <span className="font-mono">admin@demo.com / admin123</span></p>
            <p>Petugas: <span className="font-mono">petugas@demo.com / petugas123</span></p>
          </div>
        </div>
      </div>
    </div>
  );
}
