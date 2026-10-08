# Audit BIG Mobile — 8 Oktober 2026

## Status

Perbaikan aplikasi dan paket deployment aaPanel selesai disiapkan untuk staging. Pengujian otomatis dan drill lokal membuktikan alur yang dijelaskan di bawah. Go-live masih memerlukan server/domain, deployment container/HTTPS, database produksi, monitoring penerima, serta pengujian perangkat nyata. Tidak ada klaim bahwa seluruh kemungkinan bug atau kerentanan sudah dihilangkan.

## Perbaikan utama

| Area | Hasil |
| --- | --- |
| Integritas penugasan | Assignment, surat, reservasi unit, counter, snapshot dan audit memakai satu transaksi snapshot/majority; kegagalan di tengah operasi dibatalkan |
| Konkurensi | Parent references disentuh dalam transaksi; unique active/submission keys mencegah tugas/laporan ganda; cancel vs report memeriksa ulang pemilik/status |
| Retry | Idempotency-Key untuk mutasi JSON disimpan dengan fingerprint dan hasil dalam transaksi; form penugasan memakai key yang sama saat retry |
| Laporan/foto | Validasi semua gambar sebelum upload; metadata laporan/foto/status/audit atomic; upload journal merekonsiliasi orphan; konfirmasi yang hilang dipulihkan dari riwayat assignment |
| Riwayat dan renewal | Kuasa unit boleh diperbarui setelah tugas aktif ditutup. Snapshot laporan baru dan backfill sebelum edit master menjaga nama/alamat/relasi historis; snapshot surat akhir dipertahankan |
| Siklus tugas | Masa SK/klien/petugas aktif, batas tanggal, tugas masa depan, status akhir, kedaluwarsa otomatis, release unit dan penugasan ulang diperiksa |
| CRUD master | Klien, SK, unit dan petugas memiliki otorisasi tenant, validasi referensi/field/status, audit, serta penolakan penghapusan data yang sudah digunakan |
| Daftar data | Endpoint array mendukung page/limit dan metadata halaman; frontend membaca halaman berikutnya sehingga data setelah 500 record tetap dapat diakses. Pencarian laporan memakai snapshot historis sebelum paging |
| Dokumen | PDF diparse dan menolak active content/attachment; MIME/extension gambar mengikuti isi; logo harus PNG nyata. Petugas hanya dapat membaca PDF SK terkait assignment aktif miliknya; admin/tenant lain tetap diperiksa |
| Sesi | Cookie HttpOnly/Secure/SameSite, JWT issuer/audience/expiry/jti/version, revocation logout, invalidasi setelah perubahan password, dan redirect saat 401; token produksi tidak disimpan pada localStorage atau URL file |
| Login/config | Rate limit IP dan akun, hash password pada threadpool, Origin checks. Produksi menolak secret placeholder, HTTP, seed demo, Mongo unauthenticated/non-TLS/certificate bypass, storage lama dan transaksi dimatikan |
| Pengaturan | Perubahan password tersedia untuk admin/petugas. Logo dan background login disimpan atomic bersama audit; background/branding setelah login mengikuti perusahaan pengguna |
| Kegagalan jaringan | Dashboard/tugas/beranda/pengaturan menampilkan gagal/retry, bukan angka nol atau daftar kosong seolah berhasil. Form/foto dipertahankan ketika kirim gagal; error boundary memberi jalur pemulihan |
| Runtime/dependency | CRA/CRACO dilepas dari jalur build; Vite/Vitest, Leaflet lokal, lazy route chunks; paket Python production dipisah dan dikunci dengan SHA256 |
| Operasi | Compose API/web, Nginx aaPanel/HTTPS, bootstrap admin, preflight data/transaction/storage, encrypted backup/isolated restore, monitor, release dan rollback |
| Chat penugasan | Admin/petugas, foto/dokumen/lokasi, inbox/unread/notifikasi aplikasi, pagination, retry tanpa duplikat, historical read-only, transaksi dan akses lampiran privat; lihat CHAT.md |
| Observabilitas | Readiness DB/storage, metrics terlindungi, request ID dan log JSON aman, log rotation; cron aaPanel disiapkan untuk notifikasi operator |

## Bukti verifikasi lokal

- Backend lokal: **150 tes** pada regresi API, alur, keamanan produksi dan backup. Database dimock pada suite ini; storage/validasi file memakai data sementara.
- Replica set MongoDB nyata: **14 pengujian API/integritas + 1 pengujian browser HTTPS**. Database pengujian dibuat dengan nama unik dan dihapus setelah selesai. Meliputi rollback multi-koleksi, concurrency tugas/laporan/cancel, idempotensi, isolasi tenant/pemilik foto/PDF, perubahan kuasa/riwayat, logout, pagination/pencarian dan rollback logo ketika audit gagal.
- Browser HTTPS: login admin/petugas, cookie Secure/HttpOnly, refresh tanpa JWT localStorage, penugasan dari UI, GPS simulasi, foto/watermark, file SK petugas, chat foto/PDF/lokasi/izin GPS ditolak/retry respons hilang/read gagal/riwayat tertutup, review/feedback, PDF A4, retry ketika read gagal, respons kirim yang hilang setelah commit dan logout. Menggunakan sertifikat lokal pengujian dan mengabaikan certificate error hanya dalam browser QA; sertifikat publik aaPanel belum diuji.
- Browser tambahan: close/reassign/cancel, blokir tugas masa depan, duplikat, status akhir dan kedaluwarsa otomatis pada MongoDB nyata.
- Frontend: **13 tes** API/error/file/pagination/session/peta; build produksi Vite berhasil. Entry JS sekitar 432 kB sebelum gzip (~134 kB gzip), halaman dashboard terpisah.
- Backup AES-256-GCM dan restore nyata ke replica set kosong: **17 koleksi, 56 dokumen, 1 foto** cocok; password hash dua pengguna cocok. Aplikasi hasil restore berhasil startup, login, membaca riwayat dan foto terautentikasi. Backup ~5,44 detik dan restore ~103,55 detik pada dataset QA kecil; bukan RTO produksi.
- Restart MongoDB lokal secara graceful: jumlah dokumen seluruh koleksi tetap sama; readiness, login dan sesi melalui frontend proxy berhasil setelah restart.
- Uji baseline dashboard: 100 request, concurrency 4, **0 error**, p50 85,1 ms, p95 483,4 ms pada CPU lokal. Belum mengukur kapasitas VPS atau load unggahan besar.
- Python compile, YAML Compose/CI/config Mongo, shell syntax release/rollback, dan diff whitespace diperiksa. Docker tidak tersedia pada host lokal. [CI Linux untuk commit 87b03f7](https://github.com/orygo-dev/big-mobile/actions/runs/37751855804) lulus: 137 tes backend, 12 tes frontend, 10 tes transaksi/browser HTTPS, audit runtime Python/npm, build kedua container, Nginx syntax serta Trivy High/Critical kedua image (termasuk temuan tanpa patch). Runtime API memakai Python 3.12 Alpine dengan paket OS diperbarui; image Debian awal gagal scan dan diganti. Ini membuktikan build/scan di CI, belum deployment pada aaPanel target.

## Dependensi

Audit 36 paket Python runtime: **0 advisori yang diketahui**. `npm audit --omit=dev`: **0 kerentanan yang diketahui**. Audit keseluruhan npm masih mencatat **6 entri high pada rantai build/test Tailwind/braces**, bersumber pada advisori rekursi braces yang belum memiliki patch. Tidak disembunyikan oleh `audit fix --force`; lihat `frontend/dependency-audit.json` dan [advisori resmi](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). Input pola build harus berasal dari repository yang ditinjau. Paket tooling tidak disertakan dalam image web akhir; scan OS/container tetap wajib.

Masih ada deprecation warning library test/startup FastAPI. Warning ini tidak menyebabkan kegagalan suite, tetapi perlu ditangani sebelum pembaruan mayor terkait.

## Runtime dan data lokal

MongoDB Windows 8.0.20/8.2 yang dicoba mengalami illegal instruction pada CPU Sandy Bridge ketika memproses kompresi internal. Zlib koleksi/journal tidak menyelesaikan history store. [Konfigurasi resmi Snappy MongoDB 8.0](https://github.com/mongodb/mongo/blob/r8.0.32/src/third_party/snappy/platform/build_windows/config.h) mengaktifkan BMI2. Runtime Linux 8 pada WSL1 juga tidak dapat berjalan karena allocator/memory mapping. Percobaan dilakukan pada salinan data.

Aplikasi lokal kini menggunakan MongoDB **7.0.43 resmi**, replica set rs0, direktori baru `.local/db-compatible7`. Direktori `.local/db`, cadangan startup/runtime, `.local/db-compatible`, cold backup sebelum transaksi dan salinan recovery dipertahankan. **Data lama belum dipulihkan/import ke database lokal baru.** Default admin lokal hanya untuk development dan akan ditolak oleh preflight produksi. Tidak ada downgrade data file MongoDB 8 ke MongoDB 7.

## Syarat go-live

Ikuti `deploy/README.md`. Server aaPanel/domain/kredensial belum diberikan, sehingga belum ada deployment nyata. Lengkapi:

1. Database authenticated replica set/TLS, unique indexes, preflight dan migrasi data asli jika diperlukan; tidak ada password demo/default.
2. Build/scan container, Nginx/HTTPS/CSP, smoke seluruh peran dan restore di staging aaPanel. Pertahankan image rilis untuk rollback.
3. Backup terenkripsi off-server dengan kunci terpisah, drill skala data produksi, RPO/RTO dan retensi; notifikasi monitoring benar-benar diterima operator.
4. Kamera/GPS, izin ditolak, jaringan lambat/putus, hasil cetak dan UI pada Android/iOS nyata. GPS/Edge mobile viewport bukan perangkat fisik.
5. Jika memilih S3: private bucket, HTTPS/encryption/IAM, versioning/replication dan restore versi object nyata. S3 saat audit hanya dimock.
6. Load dan kapasitas resource pada VPS target; replica failover belum diuji dengan tiga anggota pada host terpisah.

[Transaksi MongoDB](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/transactions/) dapat mengulang callback; upload/file I/O sudah ditempatkan di luar callback. [mongodump](https://www.mongodb.com/docs/database-tools/mongodump/) memakai oplog untuk backup replica set. Deployment di aaPanel mengikuti [reverse proxy/SSL resmi](https://www.aapanel.com/docs/Function/proxy.html).


## Tambahan chat

Fitur dan batas operasional chat dijelaskan pada `CHAT.md`. Pengujian mencakup send vs close, retry paralel, nomor urut, unread/read cursor, rollback audit, dan akses foto/dokumen perusahaan lain/petugas lain. Chat memakai polling saat aplikasi terbuka; push notification saat aplikasi ditutup belum tersedia. Temuan dependensi tooling sebelumnya tetap berlaku.
