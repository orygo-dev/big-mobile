# Audit BIG Mobile — 10 Oktober 2026

## Status

Perbaikan aplikasi dan paket deployment aaPanel selesai disiapkan untuk staging. Pengujian otomatis dan drill lokal membuktikan alur yang dijelaskan di bawah. Go-live masih memerlukan server/domain, deployment Apache/HTTPS, database produksi, monitoring penerima, serta pengujian perangkat nyata. Tidak ada klaim bahwa seluruh kemungkinan bug atau kerentanan sudah dihilangkan.

## Perbaikan utama

| Area | Hasil |
| --- | --- |
| Integritas penugasan | Assignment, surat, reservasi unit, counter, snapshot dan audit memakai satu transaksi MySQL/InnoDB; kegagalan di tengah operasi dibatalkan |
| Konkurensi | Parent references disentuh dalam transaksi; unique active/submission keys mencegah tugas/laporan ganda; cancel vs report memeriksa ulang pemilik/status |
| Retry | Idempotency-Key untuk mutasi JSON disimpan dengan fingerprint dan hasil dalam transaksi; form penugasan memakai key yang sama saat retry |
| Laporan/foto | Validasi semua gambar sebelum upload; metadata laporan/foto/status/audit atomic; upload journal merekonsiliasi orphan; konfirmasi yang hilang dipulihkan dari riwayat assignment |
| Riwayat dan renewal | Kuasa unit boleh diperbarui setelah tugas aktif ditutup. Snapshot laporan baru dan backfill sebelum edit master menjaga nama/alamat/relasi historis; snapshot surat akhir dipertahankan |
| Siklus tugas | Masa SK/klien/petugas aktif, batas tanggal, tugas masa depan, status akhir, kedaluwarsa otomatis, release unit dan penugasan ulang diperiksa |
| CRUD master | Klien, SK, unit dan petugas memiliki otorisasi tenant, validasi referensi/field/status, audit, serta penolakan penghapusan data yang sudah digunakan |
| Daftar data | Endpoint array mendukung page/limit dan metadata halaman; frontend membaca halaman berikutnya sehingga data setelah 500 record tetap dapat diakses. Pencarian laporan memakai snapshot historis sebelum paging |
| Dokumen | PDF diparse dan menolak active content/attachment; MIME/extension gambar mengikuti isi; logo harus PNG nyata. Petugas hanya dapat membaca PDF SK terkait assignment aktif miliknya; admin/tenant lain tetap diperiksa |
| Sesi | Cookie HttpOnly/Secure/SameSite, JWT issuer/audience/expiry/jti/version, revocation logout, invalidasi setelah perubahan password, dan redirect saat 401; token produksi tidak disimpan pada localStorage atau URL file |
| Login/config | Rate limit IP dan akun, hash password pada threadpool, Origin checks. Produksi menolak secret placeholder, HTTP, seed demo, MySQL tanpa autentikasi, akun root, remote tanpa verified TLS, storage lama dan transaksi dimatikan |
| Pengaturan | Perubahan password tersedia untuk admin/petugas. Logo dan background login disimpan atomic bersama audit; background/branding setelah login mengikuti perusahaan pengguna |
| Kegagalan jaringan | Dashboard/tugas/beranda/pengaturan menampilkan gagal/retry, bukan angka nol atau daftar kosong seolah berhasil. Form/foto dipertahankan ketika kirim gagal; error boundary memberi jalur pemulihan |
| Runtime/dependency | CRA/CRACO dilepas dari jalur build; Vite/Vitest, Leaflet lokal, lazy route chunks; paket Python production dipisah dan dikunci dengan SHA256 |
| Operasi | MySQL native, Python/systemd, Apache aaPanel/HTTPS, bootstrap admin, preflight data/transaction/storage, encrypted backup/isolated restore, monitor, release dan rollback |
| Chat penugasan | Admin/petugas, foto/dokumen/lokasi, inbox/unread/notifikasi aplikasi, pagination, retry tanpa duplikat, historical read-only, transaksi dan akses lampiran privat; lihat CHAT.md |
| Observabilitas | Readiness DB/storage, metrics terlindungi, request ID dan log JSON aman, log rotation; cron aaPanel disiapkan untuk notifikasi operator |

## Bukti verifikasi lokal

- Backend lokal: **150 tes** pada regresi API, alur, keamanan produksi dan backup. Database dimock pada suite ini; storage/validasi file memakai data sementara.
- MySQL nyata: **14 pengujian API/integritas + 1 pengujian browser HTTPS**. Database pengujian dibuat dengan nama unik dan dihapus setelah selesai. Meliputi rollback antar tabel, concurrency tugas/laporan/cancel, idempotensi, isolasi tenant/pemilik foto/PDF, perubahan kuasa/riwayat, logout, pagination/pencarian dan rollback logo ketika audit gagal.
- Browser HTTPS: login admin/petugas, cookie Secure/HttpOnly, refresh tanpa JWT localStorage, penugasan dari UI, GPS simulasi, foto/watermark, file SK petugas, chat foto/PDF/lokasi/izin GPS ditolak/retry respons hilang/read gagal/riwayat tertutup, review/feedback, PDF A4, retry ketika read gagal, respons kirim yang hilang setelah commit dan logout. Menggunakan sertifikat lokal pengujian dan mengabaikan certificate error hanya dalam browser QA; sertifikat publik aaPanel belum diuji.
- Browser tambahan: close/reassign/cancel, blokir tugas masa depan, duplikat, status akhir dan kedaluwarsa otomatis pada MySQL nyata.
- Frontend: **13 tes** API/error/file/pagination/session/peta; build produksi Vite berhasil. Entry JS sekitar 432 kB sebelum gzip (~134 kB gzip), halaman dashboard terpisah.
- Migrasi menggunakan manifest checksum/count dan transaksi MySQL; ID serta hash password sumber dipertahankan. Data MongoDB lokal yang tersedia sudah diimpor; login/sesi/chat berhasil melalui frontend menggunakan MySQL.
- Backup native menggunakan mysqldump dan restore mysql, arsip AES-256-GCM, pemeriksaan target kosong dan checksum. Pengujian tambahan berada pada test_mysql_ops.py; hasil CI menjadi bukti untuk rilis akhir.
- Python runtime lock dikunci dengan SHA256. Pipeline CI kini memakai layanan MySQL native, menjalankan alur browser HTTPS, backup/migrasi, audit dependency dan pemeriksaan konfigurasi Apache. Bukti CI container sebelum migrasi bukan bukti untuk runtime baru.
- Build frontend produksi berhasil. Vitest lokal Windows mengalami timeout saat startup worker; alur browser HTTPS pada MySQL tetap lulus. Suite frontend di CI harus lulus sebelum rilis.

## Dependensi

Audit 39 paket Python runtime: **0 advisori yang diketahui**. `npm audit --omit=dev`: **0 kerentanan yang diketahui**. Audit keseluruhan npm masih mencatat **6 entri high pada rantai build/test Tailwind/braces**, bersumber pada advisori rekursi braces yang belum memiliki patch. Tidak disembunyikan oleh `audit fix --force`; lihat `frontend/dependency-audit.json` dan [advisori resmi](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). Input pola build harus berasal dari repository yang ditinjau. DocumentRoot produksi hanya berisi build statis; paket tooling berada di direktori source privat. Patch OS, Apache dan MySQL perlu dikelola pada server.

Masih ada deprecation warning library test/startup FastAPI. Warning ini tidak menyebabkan kegagalan suite, tetapi perlu ditangani sebelum pembaruan mayor terkait.

## Runtime dan data lokal

Aplikasi lokal sekarang memakai MySQL **8.4.11 native** pada loopback port 3307, database big_mobile_mysql. Sumber MongoDB 7 pada .local/db-compatible7 diekspor sebelum dipindahkan dan dihentikan secara graceful setelah ekspor. Data admin/company/audit yang tersedia berhasil dipindahkan, dengan hash password tetap sama.

Direktori MongoDB 8 asli dan seluruh cadangan recovery tetap dipertahankan. Dataset historis tersebut belum dipulihkan melalui runtime/hardware yang kompatibel; migrasi data lokal yang tersedia tidak berarti seluruh data historis sudah kembali. Default password admin lokal hanya untuk development dan ditolak preflight produksi.

## Syarat go-live

Ikuti `deploy/README.md`. Server aaPanel/domain/kredensial belum diberikan, sehingga belum ada deployment nyata. Lengkapi:

1. MySQL/InnoDB dengan pengguna khusus, loopback atau verified TLS remote, unique indexes, preflight dan migrasi data asli jika diperlukan; tidak ada password demo/default.
2. Build frontend, Python/systemd dan Apache/HTTPS/CSP, smoke seluruh peran dan restore di staging aaPanel. Pertahankan direktori rilis untuk rollback.
3. Backup terenkripsi off-server dengan kunci terpisah, drill skala data produksi, RPO/RTO dan retensi; notifikasi monitoring benar-benar diterima operator.
4. Kamera/GPS, izin ditolak, jaringan lambat/putus, hasil cetak dan UI pada Android/iOS nyata. GPS/Edge mobile viewport bukan perangkat fisik.
5. Jika memilih S3: private bucket, HTTPS/encryption/IAM, versioning/replication dan restore versi object nyata. S3 saat audit hanya dimock.
6. Load dan kapasitas resource pada VPS target; kapasitas/failover MySQL produksi belum diuji.

Transaksi MySQL mengulang operasi setelah deadlock, dengan rollback sebelum retry. Upload/file I/O tetap berada di luar callback transaksi. Backup harus menghentikan penulisan agar snapshot SQL dan file berpasangan konsisten. Panduan deployment native berada pada deploy/README.md.

## Tambahan chat

Fitur dan batas operasional chat dijelaskan pada `CHAT.md`. Pengujian mencakup send vs close, retry paralel, nomor urut, unread/read cursor, rollback audit, dan akses foto/dokumen perusahaan lain/petugas lain. Chat memakai polling saat aplikasi terbuka; push notification saat aplikasi ditutup belum tersedia. Temuan dependensi tooling sebelumnya tetap berlaku.
