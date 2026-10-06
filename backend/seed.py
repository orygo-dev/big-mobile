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
            "tahun": tahun, "warna": warna, "nomor_rangka": "", "nomor_mesin": "",
            "client_id": client_id, "surat_kuasa_id": sk_id, "keterangan": "",
            "latitude": lat, "longitude": lng, "status": "BELUM_DITUGASKAN",
            "created_at": now_iso(), "updated_at": now_iso(),
        })
