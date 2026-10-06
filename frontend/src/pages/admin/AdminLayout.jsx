import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Building2, FileText, Car, ClipboardList,
  FileCheck2, FileSearch, Users, Settings, LogOut, Shield, Menu, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/admin", end: true, label: "Dashboard", icon: LayoutDashboard, tid: "admin-sidebar-dashboard-link" },
  { to: "/admin/klien", label: "Klien", icon: Building2, tid: "admin-sidebar-klien-link" },
  { to: "/admin/surat-kuasa", label: "Surat Kuasa", icon: FileText, tid: "admin-sidebar-surat-kuasa-link" },
  { to: "/admin/akun", label: "Data Akun / Unit", icon: Car, tid: "admin-sidebar-akun-unit-link" },
  { to: "/admin/penugasan", label: "Penugasan", icon: ClipboardList, tid: "admin-sidebar-penugasan-link" },
  { to: "/admin/surat-tugas", label: "Surat Tugas", icon: FileCheck2, tid: "admin-sidebar-surat-tugas-link" },
  { to: "/admin/laporan", label: "Laporan Petugas", icon: FileSearch, tid: "admin-sidebar-laporan-link" },
  { to: "/admin/petugas", label: "Petugas", icon: Users, tid: "admin-sidebar-petugas-link" },
  { to: "/admin/pengaturan", label: "Pengaturan", icon: Settings, tid: "admin-sidebar-pengaturan-link" },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const doLogout = () => { logout(); navigate("/login", { replace: true }); };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      <div className="px-5 py-5 flex items-center gap-3 border-b border-slate-800">
        <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center">
          <Shield className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="font-heading font-bold text-white text-lg leading-none">FieldCollector</h1>
          <p className="text-[10px] text-slate-400 font-mono uppercase tracking-wider mt-1">Admin Panel</p>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} data-testid={n.tid} onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20" : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`
            }>
            <n.icon className="w-[18px] h-[18px]" />
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-slate-800">
        <button onClick={doLogout} data-testid="admin-logout-button"
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-300 hover:bg-rose-600 hover:text-white transition-all">
          <LogOut className="w-[18px] h-[18px]" /> Keluar
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans">
      {/* Desktop sidebar */}
      <aside className="w-64 bg-slate-900 flex-shrink-0 hidden md:flex flex-col fixed inset-y-0 left-0 z-30">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-slate-900"><SidebarContent /></aside>
        </div>
      )}

      <div className="flex-1 md:ml-64 flex flex-col min-w-0">
        <header className="h-16 bg-white/90 backdrop-blur-md border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setOpen(!open)} data-testid="admin-menu-toggle">
              {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </Button>
            <div>
              <p className="text-xs text-slate-400 font-mono uppercase tracking-wider">PT Garda Koleksi Nusantara</p>
              <p className="text-sm font-semibold text-slate-700">Panel Administrasi</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-semibold text-slate-800">{user?.name}</p>
              <p className="text-xs text-slate-400">{user?.email}</p>
            </div>
            <div className="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center font-semibold text-sm">
              {user?.name?.[0]?.toUpperCase()}
            </div>
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
