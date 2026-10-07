import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { BrandingProvider } from "@/context/BrandingContext";
import ProtectedRoute from "@/components/ProtectedRoute";

import Login from "@/pages/Login";
import Verify from "@/pages/Verify";

import AdminLayout from "@/pages/admin/AdminLayout";
import Dashboard from "@/pages/admin/Dashboard";
import Klien from "@/pages/admin/Klien";
import SuratKuasa from "@/pages/admin/SuratKuasa";
import SuratKuasaDetail from "@/pages/admin/SuratKuasaDetail";
import AkunUnit from "@/pages/admin/AkunUnit";
import Penugasan from "@/pages/admin/Penugasan";
import SuratTugas from "@/pages/admin/SuratTugas";
import SuratTugasPrint from "@/pages/admin/SuratTugasPrint";
import SuratPenugasanDoc from "@/pages/admin/SuratPenugasanDoc";
import LaporanPetugas from "@/pages/admin/LaporanPetugas";
import LaporanDetail from "@/pages/admin/LaporanDetail";
import Petugas from "@/pages/admin/Petugas";
import Pengaturan from "@/pages/admin/Pengaturan";

import PetugasLayout from "@/pages/petugas/PetugasLayout";
import Beranda from "@/pages/petugas/Beranda";
import Tugas from "@/pages/petugas/Tugas";
import DetailTugas from "@/pages/petugas/DetailTugas";
import BuatLaporan from "@/pages/petugas/BuatLaporan";
import Riwayat from "@/pages/petugas/Riwayat";
import Profil from "@/pages/petugas/Profil";

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading || user === null) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "admin" ? "/admin" : "/app"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrandingProvider>
      <BrowserRouter>
        <Toaster position="top-center" richColors />
        <Routes>
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
        </Routes>
      </BrowserRouter>
      </BrandingProvider>
    </AuthProvider>
  );
}
