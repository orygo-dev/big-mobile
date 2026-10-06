import os
import uuid
import bcrypt
from datetime import datetime, timezone, timedelta


def _id():
    return str(uuid.uuid4())


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def seed_all(db):
    company_id = "company-fieldcollector-001"
    existing = await db.companies.find_one({"id": company_id})
    if not existing:
        await db.companies.insert_one({
            "id": company_id, "nama": "PT Garda Koleksi Nusantara",
            "alamat": "Jl. Jenderal Sudirman No. 45, Jakarta Pusat",
            "telepon": "021-5550123", "email": "info@gardakoleksi.co.id",
            "created_at": now_iso(), "updated_at": now_iso(),
        })

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@demo.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin = await db.users.find_one({"email": admin_email})
    if not admin:
        await db.users.insert_one({
            "id": _id(), "company_id": company_id, "role": "admin",
            "name": "Administrator", "email": admin_email,
            "password_hash": _hash(admin_password), "status": "aktif",
            "created_at": now_iso(), "updated_at": now_iso(),
        })
    else:
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": _hash(admin_password), "company_id": company_id, "role": "admin"}})

    # demo admin (matches spec README credential)
    if not await db.users.find_one({"email": "admin@demo.com"}):
        await db.users.insert_one({
            "id": _id(), "company_id": company_id, "role": "admin",
            "name": "Admin Demo", "email": "admin@demo.com",
            "password_hash": _hash("admin123"), "status": "aktif",
            "created_at": now_iso(), "updated_at": now_iso(),
        })

    await ensure_document_config(db, company_id)

    # If already seeded accounts, stop (idempotent)
    if await db.accounts.count_documents({"company_id": company_id}) > 0:
        return

    # Petugas
    petugas_id = _id()
    await db.users.insert_one({
        "id": petugas_id, "company_id": company_id, "role": "petugas",
        "name": "Andi Pratama", "email": "petugas@demo.com",
        "password_hash": _hash("petugas123"), "telepon": "0812-3456-7890",
        "tim": "Tim Jakarta Selatan", "status": "aktif", "petugas_code": "PTG-00123",
        "nik": "6372050507790001", "jabatan": "PROFCOLL",
        "no_sertifikasi": "1105500694001125", "sertifikasi_valid_until": "2028-11-20",
        "avatar": "", "created_at": now_iso(), "updated_at": now_iso(),
    })
    await db.counters.update_one({"_id": f"petugas_{company_id}"}, {"$set": {"seq": 123}}, upsert=True)

    petugas2_id = _id()
    await db.users.insert_one({
        "id": petugas2_id, "company_id": company_id, "role": "petugas",
        "name": "Siti Rahma", "email": "siti@demo.com",
        "password_hash": _hash("petugas123"), "telepon": "0813-9876-5432",
        "tim": "Tim Jakarta Barat", "status": "aktif", "petugas_code": "PTG-00124",
        "avatar": "", "created_at": now_iso(), "updated_at": now_iso(),
    })

    # Client
    client_id = _id()
    await db.clients.insert_one({
        "id": client_id, "company_id": company_id, "nama_perusahaan": "PT Finance Nusantara",
        "alamat": "Jl. Gatot Subroto No. 10, Jakarta", "telepon": "021-5551234",
        "email": "ops@financenusantara.co.id", "nama_pic": "Rudi Hartono",
        "nomor_pic": "0821-1111-2222", "status": "aktif",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    client2_id = _id()
    await db.clients.insert_one({
        "id": client2_id, "company_id": company_id, "nama_perusahaan": "PT Multi Leasing Indonesia",
        "alamat": "Jl. MH Thamrin No. 22, Jakarta", "telepon": "021-5559999",
        "email": "collection@multileasing.co.id", "nama_pic": "Dewi Anggraini",
        "nomor_pic": "0822-3333-4444", "status": "aktif",
        "created_at": now_iso(), "updated_at": now_iso(),
    })

    # Surat Kuasa
    sk_id = _id()
    today = datetime.now(timezone.utc).date()
    await db.power_of_attorneys.insert_one({
        "id": sk_id, "company_id": company_id, "nomor": "SK/FIN/2026/0101",
        "client_id": client_id, "tanggal_surat": today.isoformat(),
        "tanggal_berlaku": today.isoformat(),
        "tanggal_berakhir": (today + timedelta(days=180)).isoformat(),
        "file_url": "", "keterangan": "Surat Kuasa penanganan unit kendaraan bermotor wilayah Jabodetabek.",
        "status": "aktif", "created_at": now_iso(), "updated_at": now_iso(),
    })
    sk2_id = _id()
    await db.power_of_attorneys.insert_one({
        "id": sk2_id, "company_id": company_id, "nomor": "SK/ML/2026/0045",
        "client_id": client2_id, "tanggal_surat": today.isoformat(),
        "tanggal_berlaku": today.isoformat(),
        "tanggal_berakhir": (today + timedelta(days=120)).isoformat(),
        "file_url": "", "keterangan": "Surat Kuasa penanganan unit motor.",
        "status": "aktif", "created_at": now_iso(), "updated_at": now_iso(),
    })

    accounts = [
        ("1234567890", "Budi Santoso", "DA 1234 AB", "Mobil", "Toyota", "Avanza 1.5 G", "2021", "Hitam",
         "Jl. Melati No. 10, Jakarta Selatan", "DKI Jakarta", "Jakarta Selatan", "Tebet", "Tebet Barat", -6.2297, 106.8544),
        ("1234567891", "Dewi Lestari", "B 5678 CD", "Mobil", "Honda", "Brio RS", "2022", "Merah",
         "Jl. Kenanga No. 5, Jakarta Barat", "DKI Jakarta", "Jakarta Barat", "Kebon Jeruk", "Kelapa Dua", -6.1983, 106.7721),
        ("1234567892", "Agus Setiawan", "B 9012 EF", "Motor", "Yamaha", "NMAX 155", "2023", "Biru",
         "Jl. Anggrek No. 22, Jakarta Timur", "DKI Jakarta", "Jakarta Timur", "Duren Sawit", "Pondok Bambu", -6.2340, 106.9120),
        ("1234567893", "Rina Marlina", "B 3456 GH", "Mobil", "Daihatsu", "Xenia 1.3 R", "2020", "Silver",
         "Jl. Mawar No. 8, Jakarta Utara", "DKI Jakarta", "Jakarta Utara", "Kelapa Gading", "Pegangsaan Dua", -6.1588, 106.9056),
        ("1234567894", "Hendra Wijaya", "B 7890 IJ", "Motor", "Honda", "PCX 160", "2023", "Putih",
         "Jl. Flamboyan No. 14, Jakarta Pusat", "DKI Jakarta", "Jakarta Pusat", "Menteng", "Gondangdia", -6.1934, 106.8324),
        ("1234567895", "Lina Kusuma", "B 2468 KL", "Mobil", "Suzuki", "Ertiga GX", "2019", "Abu-abu",
         "Jl. Cempaka No. 3, Depok", "Jawa Barat", "Depok", "Beji", "Kemiri Muka", -6.3833, 106.8167),
    ]
    for (kontrak, debitur, polisi, jenis, merk, model, tahun, warna, alamat, prov, kab, kec, kel, lat, lng) in accounts:
        await db.accounts.insert_one({
            "id": _id(), "company_id": company_id, "nomor_kontrak": kontrak,
            "nama_debitur": debitur, "nik": "", "telepon": "0812-0000-0000",
            "alamat": alamat, "provinsi": prov, "kabupaten": kab, "kecamatan": kec, "kelurahan": kel,
            "nomor_polisi": polisi, "jenis_kendaraan": jenis, "merk": merk, "model": model,
            "tahun": tahun, "warna": warna,
            "nomor_rangka": f"MH1{kontrak[-7:]}EK{kontrak[-3:]}", "nomor_mesin": f"JF{kontrak[-7:]}",
            "stnk_name": debitur,
            "client_id": client_id, "surat_kuasa_id": sk_id, "keterangan": "",
            "latitude": lat, "longitude": lng, "status": "BELUM_DITUGASKAN",
            "created_at": now_iso(), "updated_at": now_iso(),
        })


async def ensure_document_config(db, company_id):
    """Idempotent upgrade: extended company fields, document template, officer cert & vehicle fields."""
    comp = await db.companies.find_one({"id": company_id})
    if comp and "company_code" not in comp:
        await db.companies.update_one({"id": company_id}, {"$set": {
            "city": "Jakarta", "director_name": "Budi Hartono", "director_position": "DIREKTUR",
            "company_code": "GKN", "number_format": "{sequence}/{company_code}/{month_name}/{year}",
            "logo": "",
        }})

    if not await db.document_templates.find_one({"company_id": company_id, "version": "v1"}):
        await db.document_templates.insert_one(_default_template(company_id))

    # Upgrade existing demo officers (cert fields) if missing
    await db.users.update_one(
        {"email": "petugas@demo.com", "nik": {"$exists": False}},
        {"$set": {"nik": "6372050507790001", "jabatan": "PROFCOLL",
                  "no_sertifikasi": "1105500694001125", "sertifikasi_valid_until": "2028-11-20"}})
    await db.users.update_one(
        {"email": "siti@demo.com", "nik": {"$exists": False}},
        {"$set": {"nik": "3271010101900002", "jabatan": "PROFCOLL",
                  "no_sertifikasi": "1105500694002225", "sertifikasi_valid_until": "2027-06-15"}})

    # Upgrade existing accounts: stnk_name from debitur where missing
    try:
        await db.accounts.update_many(
            {"company_id": company_id, "stnk_name": {"$exists": False}},
            [{"$set": {"stnk_name": "$nama_debitur"}}])
    except Exception:
        pass
    # Fill sample chassis/engine for demo accounts that are empty
    async for a in db.accounts.find({"company_id": company_id, "$or": [{"nomor_rangka": ""}, {"nomor_rangka": {"$exists": False}}]}):
        k = a.get("nomor_kontrak", "0000000")
        await db.accounts.update_one({"id": a["id"]}, {"$set": {
            "nomor_rangka": f"MH1{k[-7:]}EK{k[-3:]}", "nomor_mesin": f"JF{k[-7:]}",
        }})


def _default_template(company_id):
    return {
        "id": _id(), "company_id": company_id, "version": "v1",
        "ruang_lingkup_intro": "Melakukan serah terima terhadap {unit_count} unit kendaraan beserta segala kelengkapannya, di manapun kendaraan tersebut berada, untuk kemudian diserahkan kembali kepada {finance_name} sesuai dengan perjanjian pembiayaan konsumen No. {contract_number} yang ditandatangani oleh:",
        "ruang_lingkup_closing": "Membuat dan menyerahkan Berita Acara Serah Terima Kendaraan (BASTK) kepada Debitur yang bersangkutan sebagaimana mestinya pada waktu penyerahan kendaraan dilakukan dan melakukan hal-hal lainnya sehubungan dengan hal di atas, segala sesuatu yang perlu dan berguna bagi kepentingan \"PERSEROAN\" dengan tetap memperhatikan peraturan perundang-undangan yang berlaku.",
        "larangan": [
            "Menggunakan kekerasan, ancaman, intimidasi, atau tekanan fisik maupun psikis.",
            "Memasuki rumah atau tempat tertutup tanpa izin pihak yang berhak.",
            "Mengambil objek jaminan secara paksa atau tanpa penyerahan sukarela.",
            "Membawa barang yang bukan objek penugasan.",
            "Menerima pembayaran tanpa kewenangan dan bukti resmi.",
            "Mengalihkan tugas tanpa persetujuan tertulis.",
            "Menggunakan identitas atau dokumen yang tidak sah.",
            "Menyebarkan data debitur kepada pihak yang tidak berkepentingan.",
            "Melakukan tindakan yang bertentangan dengan peraturan perundang-undangan.",
        ],
        "kewajiban": [
            "Membawa identitas, sertifikasi profesi, dan surat penugasan selama menjalankan tugas.",
            "Bersikap sopan, memperkenalkan diri, dan menjelaskan maksud kedatangan.",
            "Membuat BASTK serta dokumentasi untuk setiap serah terima.",
            "Menjaga keamanan objek sejak diterima sampai diserahkan.",
            "Melaporkan setiap kendala, penolakan, atau dugaan pelanggaran.",
        ],
        "batas_kewenangan": [
            "Penerima tugas hanya berwenang melakukan tindakan dalam ruang lingkup surat ini. Surat ini bukan perintah penyitaan dan tidak memberikan kewenangan kepolisian, pengadilan, atau kekuasaan publik lainnya.",
            "Pelanggaran menjadi tanggung jawab pribadi pelaksana dan dapat mengakibatkan pencabutan tugas, tindakan disiplin, serta proses hukum.",
        ],
        "masa_berlaku": "Surat tugas berlaku sejak {valid_from} sampai dengan {valid_until}. Surat berakhir otomatis ketika objek telah diserahterimakan dan tugas dinyatakan selesai, penugasan dibatalkan atau dicabut oleh PERSEROAN, atau terdapat keadaan lain yang menyebabkan penugasan tidak dapat dilanjutkan.",
        "verifikasi_note": "Pindai QR untuk memastikan penerbit, nomor, tanggal, dan status dokumen langsung dari sistem. Data debitur tidak ditampilkan secara publik.",
        "bastk_intro": "Pada hari ini, {day_name}, {date}, yang bertanda tangan di bawah ini:",
        "bastk_handover": "Dengan ini secara sukarela menyerahkan kendaraan bermotor kepada {finance_name} yang bekerja sama dengan {company_name} dalam keadaan dan kondisi sebagaimana tersebut secara rinci di bawah ini:",
        "bastk_ketentuan": "Apabila dalam waktu 7 (tujuh) hari sejak tanggal/waktu penyerahan tersebut di atas, pihak konsumen (Debitur) tidak ada konfirmasi/penyelesaian untuk pelunasan, maka pihak pembiayaan berhak menjual/melelang kendaraan tersebut sesuai dengan Perjanjian Pembiayaan Konsumen dan Pengakuan Hutang.",
        "checklist_items": [
            "STNK", "Lampu Stop (Belakang)", "Lampu Sein Depan R/L", "Lampu Sein Belakang R/L",
            "Cover Body", "Spakbor Depan", "Spakbor Belakang", "Tutup Shock Depan R/L",
            "Kunci Kontak", "Panel Starter/Lampu", "Besi Belakang Jok", "Pedal Versneling",
            "Accu", "Karburator", "Filter Udara", "Master Rem Cakram", "Kaliper/Jepitan Disk",
            "Disk Brake", "Speedometer", "Standar Tengah", "Standar Samping", "Kick Starter",
            "Tutup Rantai", "Knalpot", "Spion", "Pedal Rem", "Mesin Dapat Hidup",
        ],
        "distribution": [
            "Lembar Putih: Untuk Konsumen",
            "Lembar Merah: Untuk {company_name}",
            "Lembar Kuning: Untuk Pembiayaan/Leasing",
        ],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
