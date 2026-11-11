import {
  LayoutDashboard,
  Building2,
  FileText,
  Layers,
  ClipboardList,
  FileCheck2,
  FileSearch,
  Users,
  Settings,
  MessageCircle,
  Wallet,
  ChartNoAxesCombined,
  FileSignature,
  ShieldCheck,
} from "lucide-react";

export const ADMIN_NAV_GROUPS = [
  {
    section: null,
    items: [
      {
        to: "/admin",
        end: true,
        label: "Dashboard",
        icon: LayoutDashboard,
        tid: "admin-sidebar-dashboard-link",
      },
    ],
  },
  {
    section: "Master Data",
    items: [
      {
        to: "/admin/klien",
        label: "Pemberi Kuasa / Leasing",
        icon: Building2,
        tid: "admin-sidebar-klien-link",
      },
      {
        to: "/admin/akun",
        label: "Kontrak & Unit",
        icon: Layers,
        tid: "admin-sidebar-akun-unit-link",
      },
      {
        to: "/admin/petugas",
        label: "Petugas",
        icon: Users,
        tid: "admin-sidebar-petugas-link",
      },
    ],
  },
  {
    section: "Operasional",
    items: [
      {
        to: "/admin/surat-kuasa",
        label: "Surat Kuasa",
        icon: FileText,
        tid: "admin-sidebar-surat-kuasa-link",
      },
      {
        to: "/admin/penugasan",
        label: "Penugasan",
        icon: ClipboardList,
        tid: "admin-sidebar-penugasan-link",
      },
      {
        to: "/admin/surat-tugas",
        label: "Surat Tugas",
        icon: FileCheck2,
        tid: "admin-sidebar-surat-tugas-link",
      },
      {
        to: "/admin/pks",
        label: "PKS",
        icon: FileSignature,
        tid: "admin-sidebar-pks-link",
      },
      {
        to: "/admin/laporan",
        label: "Laporan Lapangan",
        icon: FileSearch,
        tid: "admin-sidebar-laporan-link",
      },
      {
        to: "/admin/pembayaran-leasing",
        label: "Pembayaran Leasing",
        icon: Wallet,
        tid: "admin-sidebar-pembayaran-leasing-link",
      },
      {
        to: "/admin/keuangan",
        label: "Laporan Keuangan",
        icon: ChartNoAxesCombined,
        tid: "admin-sidebar-keuangan-link",
      },
      {
        to: "/admin/chat",
        label: "Chat",
        icon: MessageCircle,
        tid: "admin-sidebar-chat-link",
      },
    ],
  },
  {
    section: "Pengaturan",
    items: [
      {
        to: "/admin/pengaturan",
        label: "Pengaturan",
        icon: Settings,
        tid: "admin-sidebar-pengaturan-link",
      },
      {
        to: "/admin/audit-log",
        label: "Audit Log",
        icon: ShieldCheck,
        tid: "admin-sidebar-audit-log-link",
      },
    ],
  },
];
export function adminNavigation(role) {
  return ADMIN_NAV_GROUPS.map((group) => ({
    ...group,
    items: [
      ...group.items,
      ...(group.section === "Pengaturan" && role === "owner"
        ? [
            {
              to: "/admin/pengguna-admin",
              label: "Pengguna Admin",
              icon: Users,
              tid: "owner-admin-users-link",
            },
          ]
        : []),
    ],
  }));
}

export const CREATE_ACTIONS = [
  {
    to: "/admin/penugasan?create=1",
    label: "Penugasan Baru",
    icon: ClipboardList,
  },
  { to: "/admin/akun?create=1", label: "Kontrak & Unit Baru", icon: Layers },
  {
    to: "/admin/surat-kuasa?create=1",
    label: "Surat Kuasa Baru",
    icon: FileText,
  },
];
