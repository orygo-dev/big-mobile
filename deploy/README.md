# Instalasi aaPanel: Apache + MySQL, tanpa Docker

Arsitektur: Apache melayani build React dan meneruskan `/api/` ke FastAPI pada `127.0.0.1:8000`. FastAPI berjalan sebagai layanan systemd pengguna `bigmobile`. Database menggunakan MySQL/InnoDB; file private berada di `/var/lib/big-mobile/uploads`.

## 1. Persiapan

Gunakan Linux dengan systemd, Python 3.12 beserta modul venv, Node.js 22.20 atau versi 22 yang kompatibel, Git, dan MySQL **8.4 LTS**. MySQL minimal 8.0.21; paket ini tidak mendukung MariaDB. Instal Apache dan MySQL melalui aaPanel. Aktifkan modul Apache `proxy`, `proxy_http`, `headers`, `rewrite`, `ssl`. Nama/path layanan Apache aaPanel berbeda dari paket distro; gunakan panel untuk mengaktifkan modul dan memuat ulang konfigurasi.

Buat DNS domain menuju server, tambahkan website di aaPanel, pasang sertifikat SSL dan aktifkan redirect HTTPS. Buka port publik 80/443. MySQL dan backend hanya mendengarkan loopback; port 3306/8000 tidak perlu dibuka ke internet.

## 2. Database dan konfigurasi

Buat database `big_mobile` dan pengguna khusus `bigmobile` di menu Database aaPanel. Berikan hak hanya pada `big_mobile.*`, termasuk CREATE/ALTER/INDEX karena backend menginisialisasi tabel dan indeks. Pilih charset utf8mb4. Password kuat harus URL-encoded pada MYSQL_URL; jangan memakai akun root untuk aplikasi.

Siapkan direktori dan pengguna layanan sebagai root:

```bash
useradd --system --home /var/lib/big-mobile --shell /usr/sbin/nologin bigmobile
install -d -m 755 /www/wwwroot/big-mobile /www/wwwroot/big-mobile/releases
install -d -m 700 /etc/big-mobile
install -d -o bigmobile -g bigmobile -m 700 /var/lib/big-mobile/uploads
git clone https://github.com/orygo-dev/big-mobile.git /www/wwwroot/big-mobile/source
cd /www/wwwroot/big-mobile/source
install -m 600 deploy/app.env.example /etc/big-mobile/app.env
```

Jika pengguna/direktori sudah ada, gunakan kembali. Edit `/etc/big-mobile/app.env`: MYSQL_URL, domain pada APP_BASE_URL/CORS_ORIGINS, JWT_SECRET dan MONITOR_TOKEN acak berbeda, APP_ENV=production, SEED_DEMO_DATA=false. Jangan letakkan env pada DocumentRoot. MySQL remote memerlukan `?ssl_ca=/path/to/ca.pem` dan sertifikat dengan hostname yang sesuai. Gunakan server database lokal jika tersedia.

## 3. Instalasi pertama

Bangun rilis pertama; ganti `initial` dengan nama rilis unik:

```bash
mkdir /www/wwwroot/big-mobile/releases/initial
git archive HEAD | tar -x -C /www/wwwroot/big-mobile/releases/initial
cd /www/wwwroot/big-mobile/releases/initial
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r backend/requirements-production.lock
cd frontend
npm ci --legacy-peer-deps
REACT_APP_BACKEND_URL='' npm run build
cd ..
.venv/bin/python backend/manage.py --env /etc/big-mobile/app.env bootstrap-admin --name 'Administrator' --email 'admin@domain-anda.id' --company 'Nama Perusahaan'
.venv/bin/python backend/manage.py --env /etc/big-mobile/app.env preflight
ln -s /www/wwwroot/big-mobile/releases/initial /www/wwwroot/big-mobile/current
install -m 644 deploy/big-mobile.service /etc/systemd/system/big-mobile.service
systemctl daemon-reload
systemctl enable --now big-mobile
curl --fail http://127.0.0.1:8000/api/health
```

Password admin diminta secara interaktif, minimal 12 karakter; tidak ada akun/password demo pada produksi. Untuk memindahkan data existing, lakukan langkah migrasi di bawah **sebelum bootstrap-admin**.

## 4. Website Apache

Set DocumentRoot website aaPanel menjadi `/www/wwwroot/big-mobile/current/frontend/build`. Izinkan Apache mengikuti symlink `current`; seluruh direktori induk harus bisa dilalui pengguna Apache. Jangan arahkan DocumentRoot ke source/backend/repository.

Salin isi `deploy/aapanel-apache.conf` ke dalam VirtualHost HTTPS website melalui aaPanel. Pertahankan konfigurasi sertifikat, redirect dan ACME challenge yang dibuat panel. Konfigurasi memerlukan modul yang disebut di atas. Jalankan pemeriksaan konfigurasi Apache menggunakan executable Apache aaPanel, kemudian reload melalui panel.

Buka `https://domain-anda.id/login`, login, refresh URL dashboard, dan uji penugasan/laporan/chat beserta lampiran. `/api/health` harus memberikan 200 dengan status ready; saat database tidak siap hasilnya 503. Pastikan cookie login Secure/HttpOnly. Uji unggahan dan izin lokasi melalui HTTPS pada perangkat target.

## 5. Migrasi data MongoDB lama

Hentikan penulisan aplikasi lama selama ekspor dan pemindahan file. Buat backup sumber terlebih dahulu. Ekspor ini memakai alat terpisah; aplikasi baru tidak menginstal driver MongoDB.

```bash
python3.12 -m venv /opt/big-mobile-migration
/opt/big-mobile-migration/bin/pip install -r tools/requirements-migration.txt
# Isi SOURCE_MONGO_URL dan SOURCE_MONGO_DATABASE lewat environment privat.
/opt/big-mobile-migration/bin/python tools/export_legacy_mongo.py /var/backups/big-mobile-legacy
.venv/bin/python backend/migrate_legacy.py /var/backups/big-mobile-legacy --env /etc/big-mobile/app.env
.venv/bin/python backend/manage.py --env /etc/big-mobile/app.env init-db
.venv/bin/python backend/manage.py --env /etc/big-mobile/app.env preflight
```

Target MySQL harus kosong. Import memeriksa checksum, jumlah record, collection yang dikenali, lalu menulis dalam satu transaksi. ID, hash password, riwayat dan path file dipertahankan. Salin storage lama ke direktori private baru dengan struktur path sama dan kepemilikan `bigmobile`; bandingkan hash file. Jangan hapus sumber sebelum login, relasi, seluruh hitungan dan file diverifikasi. Password demo/default harus diganti sebelum preflight produksi lulus. Dataset sangat besar perlu diuji pada staging untuk ukuran transaksi dan durasi maintenance.

## 6. Update dan rollback

```bash
cd /www/wwwroot/big-mobile/source
git pull --ff-only
bash deploy/release.sh release-20261010
# Jika perlu kembali ke rilis yang masih tersimpan:
bash deploy/rollback.sh initial
```

Script membangun rilis terpisah, memeriksa preflight dan mengalihkan symlink current. Jika readiness update gagal, rilis sebelumnya dikembalikan. Rilis baru harus dibuat dari commit yang telah direview. Rollback kode tidak memulihkan database; pertahankan kompatibilitas schema dan backup sebelum update.

## 7. Backup dan restore

Instal client native `mysqldump`/`mysql` versi yang kompatibel. Buat venv ops dan instal `deploy/requirements-ops.txt`. Simpan env ops berizin 0600 di luar webroot, berdasarkan ops.env.example. BACKUP_ENCRYPTION_KEY berisi 32 byte acak base64; simpan kunci terpisah dari arsip. MYSQL_URL/BACKUP_MYSQL_URL memakai akun database yang sesuai. Native credentials ditulis hanya pada config sementara berizin 0600, bukan argumen proses.

Hentikan layanan sementara untuk memastikan snapshot SQL dan file konsisten, lakukan backup, lalu hidupkan kembali walaupun backup gagal. Atur jadwal melalui cron aaPanel sesuai jendela maintenance:

```bash
systemctl stop big-mobile
python deploy/run-ops.py --env /etc/big-mobile/ops.env backup backup /var/backups/big-mobile/backup.enc --uploads /var/lib/big-mobile/uploads
systemctl start big-mobile
```

Backup menggunakan transaksi snapshot InnoDB, checksum dan enkripsi AES-256-GCM. Jangan mengubah schema selama backup. Salin arsip ke lokasi off-server. Restore membutuhkan database **terpisah, kosong**, direktori file kosong, dan RESTORE_MYSQL_URL khusus:

```bash
python deploy/run-ops.py --env /etc/big-mobile/ops.env backup restore /var/backups/big-mobile/backup.enc --uploads /var/lib/big-mobile-restore/uploads --isolated-target
```

Uji login, jumlah record, relasi dan hash file pada staging setelah restore. Kegagalan import SQL dapat meninggalkan target staging parsial; jangan alihkan trafik sebelum verifikasi. Backup lokal ini tidak mencadangkan object S3; untuk S3 gunakan versioning/replikasi provider dan lakukan drill pemulihan object bersama database.

## 8. Pemeriksaan operasional

Gunakan `systemctl status big-mobile` dan `journalctl -u big-mobile`. Pantau readiness, disk, MySQL, TLS, umur backup dan hasil restore. `/api/metrics` membutuhkan Bearer MONITOR_TOKEN. Hindari log Apache yang menyimpan query/body sensitif; gunakan `%m %U %>s` untuk request API jika menambahkan access log.

Jalankan pengujian aaPanel nyata, restore drill dan perangkat fisik sebelum go-live. Paket ini tidak mengonfigurasi server produksi tanpa akses/domain/env server yang sebenarnya.
