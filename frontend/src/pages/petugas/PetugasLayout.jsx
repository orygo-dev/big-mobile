import { Outlet, NavLink, useLocation } from "react-router-dom";
import { Home, ClipboardList, History, User } from "lucide-react";

const NAV = [
  { to: "/app", end: true, label: "Beranda", icon: Home, tid: "petugas-bottom-nav-beranda" },
  { to: "/app/tugas", label: "Tugas", icon: ClipboardList, tid: "petugas-bottom-nav-tugas" },
  { to: "/app/riwayat", label: "Riwayat", icon: History, tid: "petugas-bottom-nav-riwayat" },
  { to: "/app/profil", label: "Profil", icon: User, tid: "petugas-bottom-nav-profil" },
];

export default function PetugasLayout() {
  const loc = useLocation();
  // Hide bottom nav on report creation flow for focus
  const hideNav = loc.pathname.includes("/laporan");

  return (
    <div className="min-h-screen bg-slate-100 flex justify-center">
      <div className="w-full max-w-[460px] min-h-screen bg-slate-50 flex flex-col relative shadow-xl">
        <div className="flex-1 overflow-y-auto pb-24">
          <Outlet />
        </div>
        {!hideNav && (
          <nav className="fixed bottom-0 w-full max-w-[460px] bg-white/95 backdrop-blur-md border-t border-slate-200 px-2 py-2 flex justify-around items-center z-40">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} data-testid={n.tid}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-1 px-4 py-1.5 rounded-xl transition-all ${isActive ? "text-blue-600" : "text-slate-400"}`
                }>
                {({ isActive }) => (
                  <>
                    <div className={`p-1.5 rounded-xl transition-all ${isActive ? "bg-blue-50" : ""}`}><n.icon className="w-5 h-5" /></div>
                    <span className="text-[10px] font-medium">{n.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        )}
      </div>
    </div>
  );
}
