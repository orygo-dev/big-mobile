import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errMsg } from "@/lib/api";
import LoadError from "@/components/LoadError";
import { formatDateTime, REPORT_STATUS } from "@/lib/constants";
import { StatusBadge } from "@/components/StatusBadge";
import EmptyState from "@/components/EmptyState";
import {percentageLabel, sparkline} from "@/lib/dashboard-metrics";
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
import heroArtwork from "./dashboard-operations.webp";
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
function TrendLine({series,metric,label}) {
  const points=sparkline(series.map(day=>day[metric]));
  if(!points)return null;
  return <svg className="finance-ornament" viewBox="0 0 120 52" role="img" aria-label={`Grafik kumulatif ${label.toLowerCase()} dalam bulan berjalan`}><polygon points={`2,52 ${points} 118,52`} fill="currentColor" opacity=".1"/><polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round"/></svg>;
}
function ReportsChart({days}) {
  const maximum = Math.max(4, ...days.map(day => day.count));
  const step = Math.ceil(maximum / 4);
  const ticks = [4, 3, 2, 1, 0].map(value => value * step);

  return (
    <div className="reports-chart" aria-hidden="true">
      <div className="reports-chart-grid">
        {ticks.map(tick => <div key={tick}><span>{tick}</span></div>)}
      </div>
      <div className="reports-chart-days" style={{gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))`}}>
        {days.map(({label, count}, index) => (
          <div className="reports-chart-day" key={label} title={`${label}: ${count} laporan`}>
            <div className="reports-chart-bar" style={{height: `${count / ticks[0] * 100}%`}}>
              <span data-testid={`report-bar-label-${index}`}>{count}</span>
            </div>
            <span className="reports-chart-date">{label}</span>
          </div>
        ))}
      </div>
    </div>
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
  const [trends,setTrends]=useState(null),[trendsLoading,setTrendsLoading]=useState(true);
  const request = useRef(null);
  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    setTrends(null);setTrendsLoading(true);
    // Comparative analytics must never block the existing dashboard totals or workflows.
    api.get('/dashboard/finance-trends',{signal:controller.signal}).then(({data})=>{if(!controller.signal.aborted)setTrends(data);}).catch(()=>{}).finally(()=>{if(!controller.signal.aborted)setTrendsLoading(false);});
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
          <span className="dashboard-eyebrow">Dashboard</span>
          <h1>Ringkasan Operasional BIG Mobile</h1>
          <p>Pantau kinerja, operasional, dan laporan harian secara real-time.</p>
          <button onClick={() => navigate("/admin/chat")}>
            <MessageCircle size={20} />
            Buka Kotak Masuk Chat
            <ArrowRight size={17} />
          </button>
        </div>
        <BusinessClock />
        <img
          className="dashboard-hero-art"
          src={heroArtwork}
          alt=""
        />
      </section>
      <div className="dashboard-finance-grid">
        {FINANCE.map(([key, tone, label, Icon]) => {
          const metric=trends?.month===finance.month&&Number(trends?.metrics?.[key]?.current)===Number(finance[key])?trends.metrics[key]:null;
          const comparison=metric?`Dibanding ${trends.previous_start} s.d. ${trends.previous_end} (WIB). Sebelumnya ${money.format(Number(metric.previous))}.${metric.baseline_zero&&metric.percentage===null?' Persentase tidak dihitung karena nilai pembanding nol.':''}`:'Data perbandingan belum tersedia.';
          return (
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
            <span className={`dashboard-change change-${metric?.direction?.toLowerCase()||'unavailable'}`} title={comparison} aria-label={`${label}: ${metric?.direction==='UP'?'naik':metric?.direction==='DOWN'?'turun':'perubahan'} ${metric?percentageLabel(metric):'belum tersedia'}. ${comparison}`} data-testid={`dashboard-change-${key}`}>{metric&&<span aria-hidden="true">{metric.direction==='UP'?'▲':metric.direction==='DOWN'?'▼':'•'}</span>}{trendsLoading?'…':percentageLabel(metric)}</span>
            {metric&&Array.isArray(trends?.series)&&<TrendLine series={trends.series} metric={key} label={label}/>}
          </section>
        );})}
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
            <div><h2><Zap />Aktivitas Terbaru</h2><p>Riwayat aktivitas operasional terbaru dalam sistem.</p></div>
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
                  {activity.slice(0,5).map((a) => (
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
                <ReportsChart days={chart} />
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
