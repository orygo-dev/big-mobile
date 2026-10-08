import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { BrandingProvider } from "@/context/BrandingContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppErrorBoundary from "@/components/AppErrorBoundary";

const Login = lazy(() => import("@/pages/Login"));
const Verify = lazy(() => import("@/pages/Verify"));

const AdminLayout = lazy(() => import("@/pages/admin/AdminLayout"));
const Dashboard = lazy(() => import("@/pages/admin/Dashboard"));
const Klien = lazy(() => import("@/pages/admin/Klien"));
const SuratKuasa = lazy(() => import("@/pages/admin/SuratKuasa"));
const SuratKuasaDetail = lazy(() => import("@/pages/admin/SuratKuasaDetail"));
const AkunUnit = lazy(() => import("@/pages/admin/AkunUnit"));
const Penugasan = lazy(() => import("@/pages/admin/Penugasan"));
const SuratTugas = lazy(() => import("@/pages/admin/SuratTugas"));
const SuratTugasPrint = lazy(() => import("@/pages/admin/SuratTugasPrint"));
const SuratPenugasanDoc = lazy(() => import("@/pages/admin/SuratPenugasanDoc"));
const LaporanPetugas = lazy(() => import("@/pages/admin/LaporanPetugas"));
const LaporanDetail = lazy(() => import("@/pages/admin/LaporanDetail"));
const Petugas = lazy(() => import("@/pages/admin/Petugas"));
const Pengaturan = lazy(() => import("@/pages/admin/Pengaturan"));

const PetugasLayout = lazy(() => import("@/pages/petugas/PetugasLayout"));
const Beranda = lazy(() => import("@/pages/petugas/Beranda"));
const Tugas = lazy(() => import("@/pages/petugas/Tugas"));
const DetailTugas = lazy(() => import("@/pages/petugas/DetailTugas"));
const BuatLaporan = lazy(() => import("@/pages/petugas/BuatLaporan"));
const Riwayat = lazy(() => import("@/pages/petugas/Riwayat"));
const Profil = lazy(() => import("@/pages/petugas/Profil"));

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading || user === null) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "admin" ? "/admin" : "/app"} replace />;
}

export default function App() {
  return (
    <AppErrorBoundary><AuthProvider>
      <BrandingProvider>
      <BrowserRouter>
        <Toaster position="top-center" richColors />
        <Suspense fallback={<div role="status" className="p-8 text-center text-blue-600">Memuat halaman…</div>}><Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<Login />} />
          <Route path="/verifikasi/:id" element={<Verify />} />
          <Route path="/verify/surat-tugas/:code" element={<Verify />} />

          {/* Print (standalone, no sidebar) */}
          <Route path="/admin/surat-tugas/:id/print" element={
            <ProtectedRoute role="admin"><SuratTugasPrint /></ProtectedRoute>
          } />
          <Route path="/admin/surat-tugas/:id/dokumen" element={
            <ProtectedRoute role="admin"><SuratPenugasanDoc /></ProtectedRoute>
          } />

          {/* Admin */}
          <Route path="/admin" element={<ProtectedRoute role="admin"><AdminLayout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="klien" element={<Klien />} />
            <Route path="surat-kuasa" element={<SuratKuasa />} />
            <Route path="surat-kuasa/:id" element={<SuratKuasaDetail />} />
            <Route path="akun" element={<AkunUnit />} />
            <Route path="penugasan" element={<Penugasan />} />
            <Route path="surat-tugas" element={<SuratTugas />} />
            <Route path="laporan" element={<LaporanPetugas />} />
            <Route path="laporan/:id" element={<LaporanDetail />} />
            <Route path="petugas" element={<Petugas />} />
            <Route path="pengaturan" element={<Pengaturan />} />
          </Route>

          {/* Petugas */}
          <Route path="/app" element={<ProtectedRoute role="petugas"><PetugasLayout /></ProtectedRoute>}>
            <Route index element={<Beranda />} />
            <Route path="tugas" element={<Tugas />} />
            <Route path="tugas/:accountId" element={<DetailTugas />} />
            <Route path="tugas/:accountId/laporan" element={<BuatLaporan />} />
            <Route path="riwayat" element={<Riwayat />} />
            <Route path="profil" element={<Profil />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes></Suspense>
      </BrowserRouter>
      </BrandingProvider>
    </AuthProvider></AppErrorBoundary>
  );
}
