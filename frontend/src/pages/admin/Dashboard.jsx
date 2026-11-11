import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import LoadError from "@/components/LoadError";
import { formatDateTime, REPORT_STATUS } from "@/lib/constants";
import { StatusBadge } from "@/components/StatusBadge";
import EmptyState from "@/components/EmptyState";
import {
  FileText,
  Car,
  ClipboardList,
  SearchX,
  Clock,
  CalendarDays,
  Zap,
  Eye,
  Layers,
  Coins,
  Wallet,
  ChartNoAxesCombined,
  MessageCircle,
  ArrowRight,
  ChevronDown,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
const STATS = [
  ["surat_kuasa_aktif", "blue", "Surat Kuasa Aktif", FileText],
  ["total_akun", "cyan", "Total Kontrak & Unit", Layers],
  ["tugas_aktif", "purple", "Tugas Aktif", ClipboardList],
  ["unit_ditemukan", "green", "Unit Ditemukan", Car],
  ["unit_tidak_ditemukan", "rose", "Tidak Ditemukan", SearchX],
  ["belum_dikerjakan", "amber", "Belum Dikerjakan", Clock],
  ["laporan_hari_ini", "orange", "Laporan Hari Ini", CalendarDays],
];
const FINANCE = [
  ["income", "green", "Pemasukan Leasing Bulan Ini", Coins],
  ["expense", "orange", "Pembayaran Petugas Bulan Ini", Wallet],
  ["profit", "blue", "Profit Bulan Ini", ChartNoAxesCombined],
];
const money = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
function BusinessClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="dashboard-clock">
      <div>
        <CalendarDays />
        <p>
          <small>Hari Ini</small>
          <strong>
            {new Intl.DateTimeFormat("id-ID", {
              timeZone: "Asia/Jakarta",
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            }).format(now)}
          </strong>
        </p>
      </div>
      <div>
        <Clock />
        <p>
          <small>Pukul</small>
          <strong>
            {new Intl.DateTimeFormat("id-ID", {
              timeZone: "Asia/Jakarta",
              hour: "2-digit",
              minute: "2-digit",
              hourCycle: "h23",
            }).format(now)}{" "}
            WIB
          </strong>
        </p>
      </div>
    </div>
  );
}
function Ornament() {
  return (
    <svg className="finance-ornament" viewBox="0 0 120 60" aria-hidden="true">
      <path
        d="M0 57C10 42 12 57 22 45S36 50 44 35S61 43 70 24S86 39 98 18L119 0V60H0Z"
        fill="currentColor"
        opacity=".08"
      />
      <path
        d="M0 57C10 42 12 57 22 45S36 50 44 35S61 43 70 24S86 39 98 18L119 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}
export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState({
      stats: {},
      finance: {},
      activity: [],
      chart: [],
    }),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const request = useRef(null);
  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    try {
      const responses = await Promise.all(
        [
          "/dashboard/stats",
          "/dashboard/recent-activity",
          "/dashboard/reports-7days",
          "/dashboard/finance",
        ].map((path) => api.get(path, { signal: controller.signal })),
      );
      if (!controller.signal.aborted)
        setData({
          stats: responses[0].data,
          activity: responses[1].data,
          chart: responses[2].data,
          finance: responses[3].data,
        });
    } catch (e) {
      if (!controller.signal.aborted) setError(errMsg(e));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    load();
    return () => request.current?.abort();
  }, [load]);
  if (error)
    return (
      <div className="space-y-5">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <LoadError message={error} onRetry={load} />
      </div>
    );
  const { stats, finance, activity, chart } = data;
  return (
    <div className="admin-dashboard" aria-busy={loading}>
      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <h1>Dashboard</h1>
          <p>Ringkasan operasional dan laporan hari ini.</p>
          <button onClick={() => navigate("/admin/chat")}>
            <MessageCircle size={20} />
            Buka Kotak Masuk Chat
            <ArrowRight size={17} />
          </button>
        </div>
        <BusinessClock />
        <img
          className="dashboard-hero-art"
          src="/images/dashboard-operations.png"
          alt=""
        />
      </section>
      <div className="dashboard-finance-grid">
        {FINANCE.map(([key, tone, label, Icon]) => (
          <section key={key} className={`dashboard-finance metric-${tone}`}>
            <span className="metric-icon">
              <Icon />
            </span>
            <div className="metric-copy">
              <h2>{label}</h2>
              <p data-testid={`dashboard-finance-${key}`}>
                {loading ? "—" : money.format(Number(finance[key] ?? 0))}
              </p>
              <small>Periode {finance.month || "bulan berjalan"} · WIB</small>
            </div>
            <Ornament />
          </section>
        ))}
      </div>
      <div className="dashboard-metrics" data-testid="dashboard-stats">
        {STATS.map(([key, tone, label, Icon]) => (
          <section key={key} className={`dashboard-metric metric-${tone}`}>
            <span className="metric-icon">
              <Icon />
            </span>
            <div>
              <h2>{label}</h2>
              <p data-testid={`stat-${key}`}>
                {loading ? "—" : (stats[key] ?? 0)}
              </p>
            </div>
          </section>
        ))}
      </div>
      <div className="dashboard-bottom">
        <section className="dashboard-panel dashboard-activity">
          <div className="dashboard-panel-heading">
            <h2>
              <Zap />
              Aktivitas Terbaru
            </h2>
            <button onClick={() => navigate("/admin/laporan")}>
              Lihat Semua
              <ArrowRight size={14} />
            </button>
          </div>
          {loading ? (
            <p className="dashboard-loading" role="status">
              Memuat aktivitas…
            </p>
          ) : activity.length === 0 ? (
            <EmptyState
              icon={Zap}
              title="Belum ada aktivitas"
              desc="Laporan petugas akan muncul di sini."
            />
          ) : (
            <div className="dashboard-table-scroll">
              <table>
                <thead>
                  <tr>
                    {[
                      "Waktu",
                      "Petugas",
                      "No. Surat Tugas",
                      "Debitur",
                      "Status",
                      "Aksi",
                    ].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activity.map((a) => (
                    <tr key={a.id}>
                      <td>{formatDateTime(a.waktu)}</td>
                      <td>{a.petugas}</td>
                      <td>{a.nomor_surat_tugas}</td>
                      <td>{a.nama_debitur}</td>
                      <td>
                        <StatusBadge map={REPORT_STATUS} value={a.status} />
                      </td>
                      <td>
                        <button
                          aria-label={`Lihat laporan ${a.nomor_surat_tugas}`}
                          onClick={() => navigate(`/admin/laporan/${a.id}`)}
                          data-testid={`activity-view-${a.id}`}
                        >
                          <Eye size={17} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="dashboard-panel dashboard-chart">
          <div className="dashboard-panel-heading">
            <div>
              <h2>
                <ChartNoAxesCombined />
                Laporan 7 Hari Terakhir
              </h2>
              <p>Jumlah laporan masuk per hari</p>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button>
                  <CalendarDays size={14} />7 Hari Terakhir
                  <ChevronDown size={13} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={load}>
                  Perbarui data
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => navigate("/admin/laporan")}>
                  Lihat semua laporan
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          {loading ? (
            <p className="dashboard-loading" role="status">
              Memuat grafik…
            </p>
          ) : (
            <>
              <div
                className="dashboard-chart-canvas"
                role="img"
                aria-label={`Jumlah laporan per hari: ${chart.map((d) => `${d.label}: ${d.count}`).join(", ")}`}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chart}
                    margin={{ left: -20, right: 8, top: 10, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient
                        id="dashboard-bar"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop offset="0" stopColor="#006cff" />
                        <stop offset="1" stopColor="#20c5ff" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="4 4"
                      stroke="#e7eefb"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 11, fill: "#45618c" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: "#45618c" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "#f0f7ff" }}
                      contentStyle={{
                        borderRadius: 12,
                        border: "1px solid #dce8ff",
                        fontSize: 12,
                      }}
                    />
                    <Bar
                      dataKey="count"
                      fill="url(#dashboard-bar)"
                      radius={[7, 7, 0, 0]}
                      name="Laporan"
                      maxBarSize={54}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {chart.every((d) => !d.count) && (
                <p className="text-center text-xs text-slate-500">
                  Belum ada laporan dalam 7 hari terakhir.
                </p>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
