# FieldCollector — PRD & Progress

## Problem Statement
Aplikasi web responsive/PWA untuk perusahaan jasa collector/penanganan unit lapangan (PT Garda Koleksi Nusantara). Mengelola Surat Kuasa dari klien, data akun/unit, penugasan petugas, pembuatan Surat Tugas, dan laporan petugas lapangan (unit ditemukan/tidak) dengan foto bukti + GPS. MVP, tanpa AI/payment/chat/GPS realtime.

## Architecture
- **Backend**: FastAPI monolith (`/app/backend/server.py`) + MongoDB. Semua route prefix `/api`. Auth JWT Bearer (bcrypt). Object storage via Emergent (`/app/backend/storage.py`) untuk foto; DB hanya simpan URL/path. QR code via `qrcode` (PNG endpoint). Seed data di `seed.py`.
- **Frontend**: React (CRA + craco, alias `@`=src). Tailwind + shadcn/ui. Token di localStorage `fc_token`, axios interceptor Bearer. Leaflet via CDN (OpenStreetMap). Recharts untuk grafik. PWA manifest.
- **Roles**: admin (desktop dashboard + sidebar), petugas (mobile bottom-nav). Authorization di backend (admin_required / petugas_required), petugas tidak bisa akses data petugas lain.

## User Personas
- **Admin**: mengelola klien, surat kuasa, akun/unit, petugas, membuat penugasan & surat tugas, melihat/review laporan.
- **Petugas lapangan**: melihat tugasnya, membuka detail, membuat laporan kunjungan + foto + GPS.

## Core Requirements (static)
Auth & role; Klien CRUD (soft-deactivate); Surat Kuasa + akun terkait; Data Akun/Unit (search/filter/multiselect/pagination); Penugasan → Surat Tugas (nomor ST/FC/YYYY/MM/NNNN); Print A4 + QR; Verifikasi publik; Aplikasi petugas (Beranda/Tugas/Riwayat/Profil); Laporan 3-langkah (status+catatan+GPS → foto bukti+watermark → review → submit); Dashboard stats+grafik; Laporan admin + detail (foto, map); Audit log; Keamanan upload (tipe/ukuran, UUID filename).

## Implemented (2026-06)
- [x] JWT auth (admin & petugas), seed demo data, brute-force lockout
- [x] Dashboard: 7 stat cards + Aktivitas Terbaru + grafik 7 hari
- [x] Klien CRUD + nonaktifkan
- [x] Surat Kuasa list/detail + tambah akun/unit + edit SK
- [x] Data Akun/Unit: search, filter klien/status/wilayah, checkbox multiselect, pagination, Buat Penugasan
- [x] Penugasan → generate Surat Tugas otomatis, status akun → DITUGASKAN
- [x] Surat Tugas list + status + print A4 + QR code + halaman verifikasi publik
- [x] Petugas management CRUD
- [x] Aplikasi petugas mobile: Beranda, Tugas, Detail Tugas (Buka Maps), Riwayat (+filter), Profil
- [x] Laporan 3-langkah: kamera (capture=environment) + watermark client-side (canvas) + GPS auto/alasan manual + review + submit (object storage)
- [x] Laporan admin: tabel + filter + detail (foto gallery + Leaflet map + Google Maps link + review)
- [x] Audit log + Pengaturan (profil perusahaan)
- [x] Validasi: foto wajib jika UNIT_DITEMUKAN, catatan ≥10 char, lokasi wajib/alasan
- [x] Testing: 24/24 backend pytest PASS, frontend critical flows verified, authorization enforced

## Backlog
- P2: tombol Import Data akun (CSV) — belum (hanya tambah manual)
- P3: refactor server.py menjadi modul per-domain (maintainability)
- P3: serve_file re-check user aktif (bukan hanya signature token)

## Next Tasks
- Tidak ada blocker. Menunggu feedback user untuk prioritas berikutnya.

## Test Credentials
Admin: admin@demo.com / admin123 (juga trader.impian@gmail.com / admin123) · Petugas: petugas@demo.com / petugas123, siti@demo.com / petugas123
