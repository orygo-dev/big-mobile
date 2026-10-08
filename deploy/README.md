# Deployment BIG Mobile di aaPanel

Paket ini menjalankan React/Nginx dan FastAPI dalam Docker Compose, di belakang HTTPS Nginx aaPanel. Database harus replica set yang diautentikasi dan menggunakan TLS. MongoDB yang dipasang aaPanel sebagai standalone belum memenuhi kebutuhan transaksi. Pilihan praktis: managed replica set, atau tiga anggota replica set pada server terpisah dengan backup teruji. Tiga proses pada satu VPS tidak memberi ketahanan terhadap kegagalan VPS.

## Persiapan server

1. Gunakan Linux yang didukung Docker Engine/Compose v2 dan MongoDB pilihan Anda. Siapkan domain dan DNS ke server; instal sertifikat HTTPS melalui aaPanel dan aktifkan pengalihan HTTP ke HTTPS. Pastikan waktu/NTP benar.
2. Firewall publik hanya membuka port situs yang diperlukan. Port aplikasi 8080 hanya bind ke localhost; port backend/database tidak boleh dibuka publik. Batasi akses panel dan SSH.
3. Clone repository ke `/www/wwwroot/big-mobile`, simpan tag/commit rilis. Docker tidak tersedia pada komputer pengembangan saat audit, sehingga build container dan pemeriksaan sertifikat wajib dijalankan pada staging server sebelum rilis.
4. Salin `deploy/app.env.example` ke `deploy/app.env`, izin `0600`. Isi domain sebenarnya, `APP_BASE_URL`, `CORS_ORIGINS`, URI MongoDB authenticated replica set/TLS, database khusus aplikasi, JWT secret acak, dan MONITOR_TOKEN yang berbeda. URI password harus URL encoded. Jangan commit `.env` atau menuliskan secret di chat. Matikan seed demo.
5. Storage lokal menggunakan volume Docker `big-mobile_uploads`; pastikan kapasitas, izin UID 10001, dan backup off-server. Alternatif S3 memakai bucket private, HTTPS, encryption, versioning, lifecycle, IAM minimal, dan replikasi/backup. Endpoint file aplikasi memeriksa tenant/pemilik; bucket tidak boleh public.

## Rilis pertama

```bash
cd /www/wwwroot/big-mobile
export RELEASE_TAG=2026-10-08-1
docker compose -f deploy/compose.yml config --quiet
docker compose -f deploy/compose.yml build --pull
docker compose -f deploy/compose.yml run --rm --no-deps backend python manage.py bootstrap-admin --name 'Administrator' --email 'admin@domain-anda.id' --company 'Nama Perusahaan'
bash deploy/release.sh "$RELEASE_TAG"
```

Bootstrap hanya menerima database aplikasi kosong dan meminta password secara interaktif. Untuk database hasil migrasi, gunakan akun existing dan ganti semua password demo sebelum preflight. `manage.py preflight` memeriksa konfigurasi, transaksi nyata dengan write/abort, duplicate, referensi tenant, admin aktif, dan password bawaan. Pemeriksaan ini tidak menjamin integritas semua data legacy; tetap cocokkan jumlah, hubungan, dan dokumen terhadap sumber migrasi.

Di aaPanel, buat situs domain Anda, aktifkan SSL, lalu masukkan isi `aapanel-location.conf` di dalam blok **server HTTPS**. Hindari location `/` ganda yang dibuat panel. Target proxy adalah `127.0.0.1:8080`; batas upload 45 MB dan timeout 130 detik. Nginx aaPanel mengganti header forwarded IP/scheme agar header dari klien tidak dipercaya. [Dokumentasi reverse proxy aaPanel](https://www.aapanel.com/docs/Function/proxy.html).

Periksa `https://DOMAIN/api/health` menghasilkan HTTP 200 dan `status=ready`. Uji login/logout, perubahan password, file foto/PDF, refresh halaman langsung, geolokasi/kamera dan cetak pada HTTPS. Cookie produksi wajib Secure/HttpOnly; token tidak disimpan di localStorage dan URL file tidak berisi token. Frontend dan API harus berada pada origin yang sama.

## Update dan rollback

Jalankan CI dan staging terlebih dahulu. Buat backup terenkripsi sebelum update. Pakai tag rilis baru yang unik, jangan menimpa tag lama. `bash deploy/release.sh TAG` membangun image, menjalankan preflight, dan menunggu readiness. Simpan image rilis sebelumnya dan catat commit/image digest, tanggal backup, hasil pengujian, operator serta konfigurasi non-secret.

Jika readiness/flow gagal, `bash deploy/rollback.sh TAG_SEBELUMNYA` memakai image yang sudah tersedia tanpa rebuild. Jangan otomatis mengembalikan database di atas data aktif. Perubahan database rilis ini menambahkan index/backfill; data legacy yang melanggar uniqueness menghentikan readiness dan harus diperbaiki di staging berdasarkan sumber data. Untuk rilis mendatang yang menghapus/mengubah field, siapkan strategi migrasi mundur sebelum deploy.

## Backup dan drill pemulihan

Instal MongoDB Database Tools resmi dan Python ops virtualenv di host:

```bash
python3 -m venv /opt/big-mobile-ops
/opt/big-mobile-ops/bin/pip install -r deploy/requirements-ops.txt
```

Salin `ops.env.example` menjadi `ops.env` berizin 0600, isi kunci AES 256 bit base64 dan URI akun backup yang memiliki privilege backup. Simpan kunci di tempat terpisah dari backup. Temukan mount volume upload dengan `docker volume inspect big-mobile_uploads`, gunakan path yang dikembalikan pada `--uploads`. Backup mencakup full replica set melalui `mongodump --oplog`, bukan hanya satu database; dedikasikan cluster atau batasi kebijakan akses backup sesuai data yang disimpan.

```bash
/opt/big-mobile-ops/bin/python deploy/run-ops.py --env deploy/app.env --env deploy/ops.env backup backup /BACKUP/big-mobile-DATE.bmb.enc --uploads /PATH/UPLOAD_VOLUME
```

Hentikan sementara perubahan data/unggahan saat membuat backup aplikasi untuk mendapatkan pasangan database/file yang konsisten, terutama penghapusan/reconciliation. Simpan backup terenkripsi off-server. Contoh target awal: harian dengan retensi 30 hari, backup tambahan sebelum rilis; RPO/RTO final harus disepakati berdasarkan kebutuhan operasional dan hasil drill. Backup di disk VPS yang sama tidak melindungi kegagalan VPS.

Restore hanya ke replica set **terpisah dan kosong**, dengan `RESTORE_MONGO_URL` berbeda. Direktori upload target harus kosong. Flag isolated-target menegaskan target yang diperiksa; script menolak database aplikasi existing, memverifikasi authentication tag/checksum dan menolak path traversal/symlink.

```bash
/opt/big-mobile-ops/bin/python deploy/run-ops.py --env deploy/app.env --env deploy/ops.env backup restore /BACKUP/big-mobile-DATE.bmb.enc --uploads /RESTORE/UPLOADS --isolated-target
```

Bandingkan jumlah semua koleksi, hash file, relasi, login, tugas aktif dan riwayat; jalankan preflight serta smoke test staging. Catat waktu pemulihan. Ubah trafik hanya setelah verifikasi; pertahankan backup sumber. Mode script ini untuk local storage. S3 memerlukan drill pemulihan versi object/replikasi provider dan referensi MongoDB; belum diuji terhadap provider nyata.

Data Windows lama yang gagal dibaca tidak boleh dihapus. Pulihkan salinan menggunakan runtime resmi pada hardware yang kompatibel, export BSON, import ke staging replica set, cocokkan jumlah/dokumen dan preflight sebelum cutover. Jangan menyalin file WiredTiger langsung ke database aktif produksi.

## Monitoring aaPanel

Tambahkan cron setiap menit: `/opt/big-mobile-ops/bin/python /www/wwwroot/big-mobile/deploy/run-ops.py --env /www/wwwroot/big-mobile/deploy/app.env monitor`. Exit nonzero menandakan HTTP/health gagal; aktifkan notifikasi kegagalan cron di aaPanel. Notifikasi belum dihubungkan ke akun penerima selama audit.

Endpoint `/api/metrics` memerlukan Bearer MONITOR_TOKEN dan memuat readiness, transaksi, jumlah request/error/durasi sejak proses hidup. Counter per proses; gunakan satu worker sesuai paket awal. Pantau disk/upload, memori, latency p95, rasio 5xx, status replica set/lag, kedaluwarsa TLS, umur backup dan keberhasilan restore. Log API JSON mencatat request ID/route template/status/durasi tanpa body/password/URI credential; log Docker dirotasi. Log proxy `/api` dimatikan untuk menghindari query sensitif.

## Syarat go-live yang masih memerlukan server/perangkat

- Docker build, hasil scan image OS/base image, HTTPS/CSP/proxy, preflight dan CI berhasil pada staging aaPanel.
- Migrasi data asli selesai jika diperlukan; akun demo/password default tidak tersedia di produksi.
- Restore off-server, monitoring/notifikasi dan kapasitas diuji; bukti dan target RPO/RTO dicatat.
- Kamera, GPS izin ditolak/diterima, foto, koneksi lambat/putus, cetak A4 dan login ulang diuji pada Android/iOS nyata.
- S3 private/encryption/version restore diuji jika dipilih. Tes mock S3 tidak menggantikan pemeriksaan provider.

Jangan nyatakan aplikasi sudah live atau kapasitas produksi terbukti sebelum pemeriksaan tersebut selesai.
