# Chat penugasan

Admin membuka **Chat** dari sidebar/dashboard atau tombol **Chat petugas** pada penugasan dan menu Surat Tugas. Petugas membuka **Chat dengan admin** dari detail tugas, menu Chat, atau riwayat laporan.

## Penggunaan

- Percakapan mengikuti ID penugasan. Semua admin pada perusahaan terkait dan petugas yang ditugaskan dapat mengaksesnya; petugas lain dan perusahaan lain tidak dapat membaca pesan/lampiran.
- Kirim teks, maksimal empat foto/dokumen, lokasi GPS, atau kombinasi ketiganya. Lokasi tampil sebagai pratinjau sebelum dikirim dan dapat dihapus. Tautan lokasi membuka Google Maps; akurasi GPS ditampilkan bila tersedia.
- Tombol kamera meminta pengambilan foto pada browser/perangkat yang mendukungnya. Tombol File memilih gambar atau dokumen.
- Foto JPG/JPEG, PNG, WebP maksimal 8 MB. Foto dinormalisasi ke JPEG, dibatasi 2.560 piksel pada sisi terpanjang, dan metadata EXIF dilepas.
- Dokumen PDF, TXT/CSV UTF-8, DOCX, XLSX, PPTX maksimal 10 MB. PDF dengan konten aktif dan dokumen Office dengan macro/objek tertanam ditolak; aplikasi tidak menyediakan pemindaian antivirus. Dokumen diunduh sebagai attachment, gambar dapat dilihat langsung.
- Pesan gagal terkirim mempertahankan isi, lokasi dan file selama halaman masih terbuka. Tekan Kirim kembali untuk memakai ID pengiriman yang sama; pesan tidak digandakan ketika respons sebelumnya hilang. Mengubah isi setelah kegagalan membuat pengiriman baru. Draft tidak disimpan lintas reload.
- Pesan baru dimuat setiap lima detik saat halaman chat terlihat. Kotak masuk/jumlah belum dibaca diperbarui setiap 15 detik dan saat tanda baca berubah; notifikasi muncul dalam aplikasi. Belum ada push notification ketika aplikasi ditutup.
- Pesan ditandai dibaca setelah bagian akhir percakapan terlihat, bukan ketika tab tersembunyi. Pesan lama dapat dimuat bertahap. Saat tugas selesai/dibatalkan/kedaluwarsa, percakapan hanya baca; lampiran dan riwayat tetap tersedia.

## Integritas dan operasi

Metadata pesan, nomor urut, ringkasan percakapan dan audit ditulis dalam transaksi MongoDB. Penutupan tugas dan pengiriman menyentuh assignment yang sama sehingga konflik diperiksa ulang. Unique index `(company_id, assignment_id, sender_id, client_message_id)` melindungi retry; isi yang berubah dengan ID sama ditolak 409. Nomor urut per assignment melindungi pagination ketika beberapa pengguna mengirim bersamaan.

File ditulis di luar callback transaksi dengan upload journal. File tanpa metadata setelah kegagalan/retry bersamaan dibersihkan oleh worker setelah satu jam; file yang direferensikan `chat_messages.attachments.storage_path` dipertahankan. Lampiran disimpan pada storage privat yang dikonfigurasi, bukan direktori publik; URL tidak membawa token. Backup aplikasi mencakup koleksi chat serta file lokal. Untuk S3, backup versi object tetap mengikuti konfigurasi operator pada panduan deployment.

Startup membuat index chat otomatis; tidak menghapus atau mengubah data lama. Preflight memeriksa relasi chat terhadap assignment/pengguna pada tenant yang sama. Pengiriman baru dibatasi 30 pesan per pengguna per menit; retry pesan yang sudah tersimpan memakai hasil lama. Riwayat belum memiliki penghapusan/retensi otomatis; operator perlu menetapkan kebijakan retensi sebelum penggunaan produksi berskala besar.

## Verifikasi

`python -m pytest backend/tests/test_chat.py -q` memeriksa validasi lokasi/lampiran, akses, input, status tertutup dan read cursor. Suite `backend/tests/test_real_transactions.py` dengan `MONGO_TEST_URI` dan `RUN_BROWSER_TESTS=true` memeriksa transaksi, retry paralel, rollback audit, pagination, isolasi file, riwayat tugas tertutup, send vs close, dan UI HTTPS admin/petugas.

Pengujian browser memakai GPS simulasi dan file uji. Kamera/GPS/izin serta performa pada Android/iOS nyata dan aaPanel target tetap perlu diverifikasi.
