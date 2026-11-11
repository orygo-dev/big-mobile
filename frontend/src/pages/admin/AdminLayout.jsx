import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useContext, useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useBranding } from "@/context/BrandingContext";
import {
  AdminInboxContext,
  AdminInboxProvider,
} from "@/context/AdminInboxContext";
import {
  Layers,
  LogOut,
  Menu,
  Search,
  Bell,
  Plus,
  ChevronDown,
  Settings,
  MessageCircle,
  ClipboardList,
} from "lucide-react";
import { toast } from "sonner";
import { errMsg } from "@/lib/api";
import ChatUnread from "@/components/ChatUnread";
import ApprovalBadge from "@/components/ApprovalBadge";
import { adminNavigation, CREATE_ACTIONS } from "@/lib/admin-navigation";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Command,
  CommandInput,
  CommandList,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import "@/styles/admin-dashboard.css";

function Waves({ bottom = false }) {
  return (
    <svg
      className={`admin-waves ${bottom ? "admin-waves-bottom" : ""}`}
      viewBox="0 0 274 120"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path fill="#a9dbff" d="M0 0H274V25C180 120 75 6 0 54Z" />
      <path
        fill="#51b5ef"
        opacity=".7"
        d="M0 32C100 0 195 122 274 24V55C170 134 76 25 0 68Z"
      />
      <path
        fill="#008bfb"
        opacity=".7"
        d="M0 60C110 18 193 131 274 51V77C172 148 67 61 0 82Z"
      />
    </svg>
  );
}
function Sidebar({ onNavigate, onLogout }) {
  const { user } = useAuth();
  const { appName, logo } = useBranding();
  return (
    <div className="admin-sidebar-inner">
      <div className="admin-brand">
        {logo ? (
          <img src={logo} alt="" data-testid="sidebar-logo" />
        ) : (
          <Layers size={40} />
        )}
        <div>
          <strong>{appName}</strong>
          <span>Administrative System</span>
        </div>
      </div>
      <Waves />
      <nav aria-label="Navigasi administrasi">
        {adminNavigation(user?.role).map((group, i) => (
          <div className="admin-nav-group" key={i}>
            {group.section && <p>{group.section}</p>}
            {group.items.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                data-testid={n.tid}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `admin-nav-link ${isActive ? "is-active" : ""}`
                }
              >
                <n.icon size={19} />
                <span>{n.label}</span>
                {n.to === "/admin/chat" && <ChatUnread />}
                {n.to === "/admin/penugasan" && user?.role === "owner" && (
                  <ApprovalBadge />
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <button
        className="admin-sidebar-logout"
        onClick={onLogout}
        data-testid="admin-logout-button"
      >
        <LogOut size={18} />
        Keluar
      </button>
      <Waves bottom />
    </div>
  );
}
const SEARCH_TARGETS = [
  ["/admin/akun", "Kontrak & Unit"],
  ["/admin/petugas", "Petugas"],
  ["/admin/surat-tugas", "Surat Tugas"],
  ["/admin/surat-kuasa", "Surat Kuasa"],
  ["/admin/laporan", "Laporan Lapangan"],
];
function AdminShell() {
  const { user, logout } = useAuth();
  const { companyName, appName } = useBranding();
  const inbox = useContext(AdminInboxContext);
  const navigate = useNavigate();
  const [drawer, setDrawer] = useState(false),
    [searchOpen, setSearchOpen] = useState(false),
    [query, setQuery] = useState(""),
    [loggingOut, setLoggingOut] = useState(false);
  useEffect(() => {
    const key = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const go = (path) => {
    setDrawer(false);
    setSearchOpen(false);
    setQuery("");
    navigate(path);
  };
  const doLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setLoggingOut(false);
    }
  };
  return (
    <div className="admin-shell">
      <aside className="admin-sidebar admin-sidebar-desktop">
        <Sidebar onNavigate={() => setDrawer(false)} onLogout={doLogout} />
      </aside>
      <Sheet open={drawer} onOpenChange={setDrawer}>
        <SheetContent
          side="left"
          className="admin-sidebar admin-mobile-sidebar"
        >
          <SheetTitle className="sr-only">Menu administrasi</SheetTitle>
          <SheetDescription className="sr-only">
            Navigasi aplikasi dan pengaturan akun.
          </SheetDescription>
          <Sidebar onNavigate={() => setDrawer(false)} onLogout={doLogout} />
        </SheetContent>
      </Sheet>
      <div className="admin-workspace">
        <header className="admin-header">
          <button
            className="admin-icon-button admin-mobile-menu"
            aria-label="Buka menu"
            aria-expanded={drawer}
            onClick={() => setDrawer(true)}
            data-testid="admin-menu-toggle"
          >
            <Menu />
          </button>
          <div className="admin-company">
            <strong>{companyName || appName}</strong>
            <span>Panel Administrasi</span>
          </div>
          <button
            className="admin-global-search"
            onClick={() => setSearchOpen(true)}
            aria-label="Cari data aplikasi"
          >
            <Search size={19} />
            <span>Cari data, kontrak, unit, petugas, atau laporan...</span>
            <kbd>Ctrl K</kbd>
          </button>
          <div className="admin-header-actions">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="admin-icon-button admin-notification"
                  aria-label="Notifikasi"
                >
                  <Bell size={23} />
                  {inbox.chat + inbox.approvals > 0 && <i />}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-72">
                <DropdownMenuLabel>Notifikasi</DropdownMenuLabel>
                <DropdownMenuItem onSelect={() => go("/admin/chat")}>
                  <MessageCircle className="mr-2 h-4 w-4" />
                  {inbox.loading
                    ? "Memuat pesan…"
                    : `${inbox.chat} pesan belum dibaca`}
                </DropdownMenuItem>
                {user?.role === "owner" && (
                  <DropdownMenuItem onSelect={() => go("/admin/penugasan")}>
                    <ClipboardList className="mr-2 h-4 w-4" />
                    {inbox.loading
                      ? "Memuat penugasan…"
                      : `${inbox.approvals} menunggu persetujuan`}
                  </DropdownMenuItem>
                )}
                {inbox.error && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onSelect={inbox.refresh}>
                      Gagal memuat notifikasi. Coba lagi
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="admin-create-button" aria-label="Buat Baru">
                  <Plus size={20} />
                  <span>Buat Baru</span>
                  <ChevronDown size={15} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {CREATE_ACTIONS.map((a) => (
                  <DropdownMenuItem key={a.to} onSelect={() => go(a.to)}>
                    <a.icon className="mr-2 h-4 w-4" />
                    {a.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="admin-profile" aria-label="Menu akun">
                  <span className="admin-avatar">
                    {user?.name?.[0]?.toUpperCase() || "A"}
                  </span>
                  <span className="admin-profile-copy">
                    <strong>{user?.name}</strong>
                    <small>{user?.email}</small>
                  </span>
                  <ChevronDown size={15} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>{user?.name}</DropdownMenuLabel>
                <DropdownMenuItem onSelect={() => go("/admin/pengaturan")}>
                  <Settings className="mr-2 h-4 w-4" />
                  Pengaturan
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem disabled={loggingOut} onSelect={doLogout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Keluar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="admin-main">
          <Outlet />
        </main>
      </div>
      <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
        <DialogContent className="p-0 overflow-hidden">
          <DialogTitle className="sr-only">Cari data aplikasi</DialogTitle>
          <DialogDescription className="sr-only">
            Masukkan kata kunci dan pilih jenis data.
          </DialogDescription>
          <Command shouldFilter={false}>
            <CommandInput
              value={query}
              onValueChange={setQuery}
              placeholder="Cari kontrak, unit, petugas, atau laporan…"
            />
            <CommandList>
              <CommandGroup
                heading={
                  query.trim()
                    ? "Pilih jenis data yang ingin dicari"
                    : "Buka menu"
                }
              >
                {query.trim()
                  ? SEARCH_TARGETS.map(([path, label]) => (
                      <CommandItem
                        key={path}
                        onSelect={() =>
                          go(
                            `${path}?search=${encodeURIComponent(query.trim())}`,
                          )
                        }
                      >
                        <Search className="mr-2 h-4 w-4" />
                        Cari “{query.trim()}” di {label}
                      </CommandItem>
                    ))
                  : adminNavigation(user?.role)
                      .flatMap((g) => g.items)
                      .map((n) => (
                        <CommandItem key={n.to} onSelect={() => go(n.to)}>
                          <n.icon className="mr-2 h-4 w-4" />
                          {n.label}
                        </CommandItem>
                      ))}
              </CommandGroup>
            </CommandList>
          </Command>
          <p className="px-4 pb-3 text-xs text-slate-500">
            Masukkan kata kunci dan pilih jenis data.
          </p>
        </DialogContent>
      </Dialog>
    </div>
  );
}
export default function AdminLayout() {
  return (
    <AdminInboxProvider>
      <AdminShell />
    </AdminInboxProvider>
  );
}
