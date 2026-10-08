import { Outlet, NavLink, useLocation } from "react-router-dom";
import { Home, ClipboardList, History, User, MessageCircle } from "lucide-react";
import ChatUnread from "@/components/ChatUnread";

const NAV = [
  { to: "/app", end: true, label: "Beranda", icon: Home, tid: "petugas-bottom-nav-beranda" },
  { to: "/app/tugas", label: "Tugas", icon: ClipboardList, tid: "petugas-bottom-nav-tugas" },
  { to: "/app/riwayat", label: "Riwayat", icon: History, tid: "petugas-bottom-nav-riwayat" },
  { to: "/app/chat", label: "Chat", icon: MessageCircle, tid: "petugas-bottom-nav-chat" },
  { to: "/app/profil", label: "Profil", icon: User, tid: "petugas-bottom-nav-profil" },
];

export default function PetugasLayout() {
  const loc = useLocation();
  // Task details and reports have their own footer action and back navigation.
  const chatThread = /^\/app\/chat\/[^/]+$/.test(loc.pathname);
  const hideNav = chatThread || loc.pathname.includes("/laporan") || /^\/app\/tugas\/[^/]+$/.test(loc.pathname);

  return (
    <div className="min-h-screen bg-blue-50 flex justify-center">
      <div className="brand-app w-full max-w-[460px] min-h-screen flex flex-col relative shadow-xl">
        <div className={`flex-1 overflow-y-auto ${chatThread ? '' : 'pb-24'}`}>
          <Outlet />
        </div>
        {!hideNav && (
          <nav className="brand-mobile-nav fixed bottom-0 w-full max-w-[460px] bg-white border-t border-blue-100 px-2 py-2 flex justify-around items-center z-40">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} data-testid={n.tid}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-1 flex-1 min-w-0 px-1 py-1.5 rounded-xl transition-all ${isActive ? "bg-blue-50 text-blue-600" : "text-slate-500"}`
                }>
                {({ isActive }) => (
                  <>
                    <div className={`p-1.5 rounded-xl transition-all ${isActive ? "bg-blue-50" : ""}`}><n.icon className="w-5 h-5" /></div>
                    <span className="text-[11px] font-medium">{n.label}</span>
                    {n.to === '/app/chat' && <ChatUnread />}
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
