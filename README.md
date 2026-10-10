# BIG Mobile / FieldCollector

Aplikasi administrasi penugasan dan laporan kunjungan petugas. Frontend menggunakan React; backend menggunakan FastAPI dan MySQL/InnoDB.

## Konfigurasi lokal

Salin `backend/.env.example` menjadi `backend/.env` dan `frontend/.env.example` menjadi `frontend/.env`. Isi JWT secret acak dan konfigurasi storage. MySQL harus berjalan; isi MYSQL_URL dengan pengguna database khusus. URL frontend/backend harus sesuai dengan `APP_BASE_URL`, `CORS_ORIGINS`, dan `REACT_APP_BACKEND_URL`.

Data demo tidak dibuat secara default. Untuk database development yang kosong, aktifkan `SEED_DEMO_DATA=true`; kembalikan ke `false` setelah bootstrap. Seed tidak lagi mereset password admin yang sudah ada. Jangan aktifkan data demo pada deployment produksi.

Backend: instal `backend/requirements.txt` di virtual environment, lalu jalankan `python -m uvicorn server:app --reload --port 8000` dari direktori `backend`.

Frontend: jalankan `npm ci --legacy-peer-deps`, lalu `npm start` dari direktori `frontend`. Lockfile dan overrides npm menyimpan versi dependensi yang diverifikasi. Tanpa `REACT_APP_BACKEND_URL`, frontend memakai `/api` pada origin yang sama; server hosting harus meneruskan `/api` ke backend.

### MySQL native lokal

Gunakan MySQL 8.4 LTS (minimal 8.0.21), bukan MariaDB. Buat database utf8mb4 dan pengguna aplikasi dengan hak pada database tersebut saja. MYSQL_URL memakai format `mysql://user:URL_ENCODED_PASSWORD@127.0.0.1:3306/big_mobile`. Tabel InnoDB dan indeks dibuat saat startup; transaksi tidak memerlukan replica set atau container.

Backend memantau koneksi dan mencoba kembali saat layanan database gagal. `/api/health` memberikan 200 ketika siap dan 503 ketika belum siap. Data MongoDB lama dapat dipindahkan melalui ekspor/import terpisah sesuai panduan deployment; sumber lama tetap dipertahankan.

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

Ikuti [panduan deployment aaPanel](deploy/README.md) untuk Apache HTTPS, MySQL native, systemd, bootstrap admin, migrasi data lama, preflight, backup terenkripsi dan rollback. Aplikasi tidak menggunakan Docker. Produksi memakai cookie HttpOnly/Secure dan storage private. Instal runtime melalui `pip install --require-hashes -r backend/requirements-production.lock`.

Jalankan suite keamanan/ops dengan `python -m pytest backend/tests/test_production_security.py backend/tests/test_backup_ops.py -q`. Untuk integrasi nyata, set MYSQL_TEST_URL ke akun MySQL pengujian yang diizinkan membuat/menghapus database berawalan audit_mysql_; jalankan backend/tests/test_real_transactions.py. RUN_BROWSER_TESTS=true mengaktifkan alur HTTPS/browser. CI menjalankan MySQL native dan pemeriksaan konfigurasi Apache. Deployment aaPanel nyata, pemulihan data asli dan perangkat fisik tetap perlu diverifikasi di lingkungan target.

## Chat penugasan

Chat admin–petugas mendukung foto, dokumen dan lokasi GPS, kotak masuk serta pesan belum dibaca. Percakapan terikat pada penugasan dan menjadi hanya baca setelah tugas ditutup. Lihat [panduan chat](CHAT.md) untuk format lampiran, keamanan, retry dan batas operasional.
