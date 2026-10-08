import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Phone, Mail, Users, BadgeCheck, LogOut } from "lucide-react";
import { toast } from "sonner";
import { errMsg } from "@/lib/api";
import PasswordSettings from "@/components/PasswordSettings";

export default function Profil() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const doLogout = async () => {try {await logout(); navigate("/login", {replace: true});} catch (e) {toast.error(errMsg(e));}};

  const Row = ({ icon: Icon, label, value }) => (
    <div className="flex items-center gap-3 py-3 border-b border-slate-50 last:border-0">
      <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center"><Icon className="w-4 h-4 text-slate-500" /></div>
      <div><p className="text-xs text-slate-400">{label}</p><p className="text-sm font-medium text-slate-700">{value || "-"}</p></div>
    </div>
  );

  return (
    <div>
      <div className="brand-hero text-white px-5 pt-10 pb-20 text-center">
        <div className="w-24 h-24 rounded-full bg-white/20 flex items-center justify-center text-3xl font-semibold font-heading mx-auto border-4 border-white/40">
          {user?.name?.[0]?.toUpperCase()}
        </div>
        <h1 className="font-heading text-xl font-bold mt-3">{user?.name}</h1>
        <p className="text-slate-400 text-sm font-mono">{user?.petugas_code}</p>
        <span className="brand-account-status inline-flex items-center gap-1 mt-2 px-3 py-1 rounded-full text-xs font-semibold">
          <BadgeCheck className="w-3.5 h-3.5" /> {user?.status === "aktif" ? "Akun Aktif" : "Nonaktif"}
        </span>
      </div>

      <div className="px-4 -mt-12">
        <div className="brand-panel rounded-2xl p-4 shadow-sm border border-slate-100" data-testid="petugas-profil-card">
          <Row icon={Phone} label="Nomor HP" value={user?.telepon} />
          <Row icon={Mail} label="Email" value={user?.email} />
          <Row icon={Users} label="Tim / Area" value={user?.tim} />
        </div>

        <div className="mt-4"><PasswordSettings /></div>
        <Button onClick={doLogout} variant="outline" data-testid="petugas-logout-button"
          className="w-full mt-4 rounded-2xl border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700 py-6 font-semibold">
          <LogOut className="w-4 h-4 mr-2" /> Keluar
        </Button>
      </div>
    </div>
  );
}
