# BIG Mobile / FieldCollector

Aplikasi administrasi penugasan dan laporan kunjungan petugas. Frontend menggunakan React; backend menggunakan FastAPI dan MongoDB.

## Konfigurasi lokal

Salin `backend/.env.example` menjadi `backend/.env` dan `frontend/.env.example` menjadi `frontend/.env`. Isi JWT secret acak dan konfigurasi storage. MongoDB harus berjalan. URL frontend/backend harus sesuai dengan `APP_BASE_URL`, `CORS_ORIGINS`, dan `REACT_APP_BACKEND_URL`.

Data demo tidak dibuat secara default. Untuk database development yang kosong, aktifkan `SEED_DEMO_DATA=true`; kembalikan ke `false` setelah bootstrap. Seed tidak lagi mereset password admin yang sudah ada. Jangan aktifkan data demo pada deployment produksi.

Backend: instal `backend/requirements.txt` di virtual environment, lalu jalankan `python -m uvicorn server:app --reload --port 8000` dari direktori `backend`.

Frontend: jalankan `npm ci --legacy-peer-deps`, lalu `npm start` dari direktori `frontend`. Lockfile dan overrides npm menyimpan versi dependensi yang diverifikasi. Tanpa `REACT_APP_BACKEND_URL`, frontend memakai `/api` pada origin yang sama; server hosting harus meneruskan `/api` ke backend.

### MongoDB lokal Windows

Pada komputer Windows 10/CPU Sandy Bridge yang diaudit, gunakan runtime MongoDB 7.0.43 resmi pada direktori baru `.local/db-compatible7`. Buat direktori tersebut serta `.local/logs`, lalu jalankan `mongod --config backend/mongod.local.example.yml`. Inisialisasi replica set `rs0` dengan host `127.0.0.1:27017` dan gunakan URI replica set di `.env`. Transaksi memerlukan primary replica set, bukan standalone.

Zlib tidak mengonversi database Snappy dan tidak mengatasi seluruh kompresi internal history store MongoDB 8 pada CPU ini. Direktori database lama/cadangan tetap dipertahankan; data lama belum tersedia pada database lokal baru sampai dipulihkan dan diimpor dengan runtime/hardware yang kompatibel. Jangan mencoba membuka data MongoDB 8 memakai MongoDB 7.

Backend memantau koneksi MongoDB dan mencoba kembali saat koneksi gagal. `GET /api/health` mengembalikan HTTP 200 saat database siap dan HTTP 503 saat belum siap. Permintaan aplikasi ditolak dengan pesan gangguan layanan selama database belum siap.

### Penyimpanan foto dan dokumen

Untuk menjalankan unggahan tanpa provider eksternal, isi `FILE_STORAGE_BACKEND=local` di `backend/.env`. File disimpan pada `.local/uploads` secara default; `LOCAL_STORAGE_DIR` dapat menentukan direktori lain. File tetap dilayani melalui endpoint dengan autentikasi dan pemeriksaan pemilik/perusahaan. Cadangkan direktori ini bersama database. Tidak ada perpindahan otomatis dari storage remote ke lokal; file lama di provider remote tidak ikut dipindahkan.

Untuk provider sebelumnya, gunakan `FILE_STORAGE_BACKEND=remote` beserta kredensial dan URL provider. Gangguan provider mengembalikan pesan layanan penyimpanan, bukan menyamarkannya sebagai laporan berhasil.

Penugasan harus berada dalam masa berlaku Surat Kuasa dan klien/petugas harus aktif. Jika tanggal akhir kosong, tanggal akhir Surat Kuasa digunakan. Tugas yang belum mulai tidak dapat dilaporkan. Status selesai, dibatalkan, dan kedaluwarsa tidak dapat diubah kembali; buat penugasan baru. Backend memeriksa kedaluwarsa setiap menit, memproses maksimal 200 surat per siklus. Unit tanpa penugasan aktif dapat dipilih kembali tanpa menghapus riwayat hasil kunjungannya.

## Verifikasi

Untuk suite lokal tanpa seluruh paket integrasi, instal `backend/requirements-test.txt`. Tes regresi lokal (API/database dimock; storage lokal memakai direktori sementara): `python -m pytest backend/tests/test_local_regressions.py backend/tests/test_workflow_audit.py -q`.

Frontend: `npm test` (Vitest), lalu `npm run build` (Vite). Node.js 22.20 atau lebih baru diperlukan. Server development meneruskan `/api` ke port 8000 ketika backend URL kosong.

Tes integrasi lama di `backend/tests/test_fieldcollector_api.py` dan `test_document_feature.py` mengarah ke server demo eksternal secara default dan mengubah data. Jalankan hanya terhadap instance pengujian yang dikonfigurasi melalui `REACT_APP_BACKEND_URL`.

Lihat `AUDIT.md` untuk temuan, perbaikan, dan batas verifikasi.

## Produksi dengan aaPanel

Ikuti [panduan deployment aaPanel](deploy/README.md) untuk Docker Compose, Nginx HTTPS, replica set MongoDB, bootstrap admin, preflight, backup terenkripsi, monitoring, dan rollback. Produksi memakai cookie HttpOnly/Secure, storage lokal atau S3 private, dan transaksi MongoDB wajib. Gunakan `backend/requirements-production.lock` dengan `pip install --require-hashes -r ...` untuk paket runtime yang dikunci.

Jalankan suite keamanan/ops tambahan: `python -m pytest backend/tests/test_production_security.py backend/tests/test_backup_ops.py -q`. Untuk integrasi transaksi nyata, set `MONGO_TEST_URI` ke replica set pengujian lalu jalankan `backend/tests/test_real_transactions.py`; pengujian membuat database terisolasi sendiri dan membersihkannya. CI di `.github/workflows/verify.yml` juga membangun kedua container. Deployment/HTTPS, pemulihan data asli dan perangkat fisik harus diverifikasi pada lingkungan target sebelum go-live.

## Chat penugasan

Chat admin–petugas mendukung foto, dokumen dan lokasi GPS, kotak masuk serta pesan belum dibaca. Percakapan terikat pada penugasan dan menjadi hanya baca setelah tugas ditutup. Lihat [panduan chat](CHAT.md) untuk format lampiran, keamanan, retry dan batas operasional.
