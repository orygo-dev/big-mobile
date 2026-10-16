import CompanyLetterhead from "./CompanyLetterhead";

const date = (value) => {
  if (!value) return "-";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
};

/** Operational assignment; company, officer and vehicle details come from the document payload. */
export default function FieldAssignmentLetter({ doc, qrSrc }) {
  const d = doc.data;
  const company = d.company;
  const signature = doc.director_signature ?? company.director_signature;
  const finance = d.finance.name || "pemberi kuasa";
  const row = (label, value) => <tr key={label}><td>{label}</td><td>: {value || "-"}</td></tr>;
  return <div className="doc-page field-letter" data-testid="doc-page-1">
    <style>{`
      .doc-page.field-letter { padding: 10mm 14mm; font-size: 11px; line-height: 1.25; overflow-wrap: anywhere; }
      .field-letter p { margin: 5px 0; text-align: justify; }
      .field-letter table { border-collapse: collapse; font-size: inherit; line-height: inherit; }
      .field-letter .field-details td { padding: 0 8px 0 0; vertical-align: top; }
      .field-letter .field-details td:first-child { width: 120px; }
      .field-letter .field-officer { width: 100%; margin: 5px 0; text-align: left; }
      .field-letter .field-officer th, .field-letter .field-officer td { padding: 2px 5px; vertical-align: top; }
      .field-letter .field-officer thead { border-block: 1px solid #999; }
      .field-letter .field-special { display: flex; align-items: center; gap: 8px; margin: 5px 0; font-weight: 700; }
      .field-letter .field-special:before, .field-letter .field-special:after { content: ''; flex: 1; border-top: 1px dashed #444; }
      .field-letter .field-clauses { padding-left: 20px; margin: 4px 0; }
      .field-letter .field-clauses > li { padding-left: 3px; margin-bottom: 3px; text-align: justify; }
      .field-letter .field-unit { margin: 4px 0; break-inside: avoid; }
      .field-letter .field-signers { display: grid; grid-template-columns: 1fr 1fr; gap: 0 8%; text-align: center; break-inside: avoid; margin-top: 8px; }
      .field-letter .field-closing { break-inside: avoid; }
      .field-letter .field-signature { height: 22mm; display: flex; justify-content: center; align-items: center; }
      .field-letter .field-signature img { width: 50mm; height: 22mm; object-fit: contain; }
      .field-letter .field-verification { display: flex; gap: 8px; align-items: center; margin-top: 8px; font-size: 8px; break-inside: avoid; }
      .field-letter .field-footer { border-top: 2px solid #111; margin-top: 8px; padding-top: 4px; font-size: 8px; text-align: center; }
    `}</style>
    <CompanyLetterhead company={doc.letterhead || company} title="SURAT TUGAS" number={d.letter.document_number || doc.st_nomor || "(akan dibuat saat finalisasi)"} />
    <p>Yang bertanda tangan di bawah ini:</p>
    <table className="field-details"><tbody>
      {row("Nama", company.director_name)}
      {row("Jabatan", `${company.director_position || "Direktur"} ${company.name || ""}`)}
      {row("Alamat", company.address)}
    </tbody></table>
    <p>Dengan ini bertindak untuk dan atas nama <b>{company.name}</b> yang berkedudukan di {company.city || "-"}, selanjutnya disebut <b>PEMBERI TUGAS</b>, dalam pelaksanaan penugasan dari <b>{finance}</b>, menunjuk dan memberikan tugas kepada:</p>
    <table className="field-officer"><thead><tr><th>No.</th><th>Nama</th><th>NIK</th><th>No. SPPI / Sertifikasi</th><th>Jabatan</th></tr></thead>
      <tbody><tr><td>1</td><td><b>{d.officer.name}</b></td><td>{d.officer.nik || "-"}</td><td>{d.officer.certification_number || "-"}</td><td>{d.officer.position || "Petugas"}</td></tr></tbody>
    </table>
    <p>Petugas tersebut di atas selanjutnya disebut <b>PENERIMA TUGAS</b>.</p>
    <div className="field-special">KHUSUS</div>
    <p>PEMBERI TUGAS memberikan wewenang kepada PENERIMA TUGAS untuk melaksanakan hal-hal sebagai berikut:</p>
    <ol className="field-clauses">
      <li>Melakukan serah terima terhadap <b>{d.accounts.length} unit kendaraan</b> beserta kelengkapannya dari Debitur/Pihak Ketiga yang menguasai kendaraan, untuk diserahkan kepada <b>{finance}</b> selaku kreditur, sesuai perjanjian pembiayaan dengan data sebagai berikut:
        {d.accounts.map((a, index) => <div className="field-unit" key={index}>
          {d.accounts.length > 1 && <b>Unit {index + 1}</b>}
          <table className="field-details"><tbody>
            {row("No. Kontrak", a.contract_number)}{row("Nama Debitur", a.debtor_name)}{row("Alamat", a.debtor_address)}
            {row("Merk / Tipe / Tahun", `${a.brand || "-"} / ${a.year || "-"}`)}{row("Warna", a.color)}
            {row("No. Polisi", a.license_plate)}{row("No. Mesin", a.engine_number)}{row("No. Rangka", a.chassis_number)}
          </tbody></table>
        </div>)}
      </li>
      <li>Membuat dan menandatangani Berita Acara Penyerahan/Serah Terima Kendaraan (BAPK/BASTK) bersama Debitur/Pihak Ketiga serta menyerahkan salinannya kepada pihak yang menyerahkan kendaraan.</li>
      <li>Melaksanakan tugas sesuai ruang lingkup surat ini, membawa identitas, sertifikasi profesi dan surat tugas, serta memperkenalkan diri dan menjelaskan maksud kedatangan secara sopan.</li>
      <li>PENERIMA TUGAS <b>dilarang menerima pembayaran, uang, hadiah atau imbalan dalam bentuk apa pun</b>. Pembayaran dilakukan langsung melalui kantor atau kanal pembayaran resmi {finance}.</li>
      <li>Menjaga kendaraan beserta seluruh kelengkapannya sesuai kondisi pada saat diterima dan menyerahkannya ke lokasi penyimpanan yang ditunjuk PEMBERI TUGAS selambat-lambatnya <b>1 x 24 jam</b> setelah serah terima, disertai dokumentasi dan laporan.</li>
      <li>Berkoordinasi dengan PEMBERI TUGAS dan pihak yang berwenang apabila terdapat kendala. Surat ini tidak memberikan kewenangan penyitaan, kewenangan kepolisian atau kewenangan publik lainnya.</li>
      <li>Menghubungi Debitur/Pihak Ketiga dan melakukan serah terima secara sukarela. Apabila terjadi penolakan atau sengketa, hentikan pengambilan kendaraan dan laporkan kepada PEMBERI TUGAS untuk tindak lanjut sesuai ketentuan yang berlaku.</li>
      <li>PENERIMA TUGAS <b>dilarang melakukan kekerasan, ancaman, intimidasi, pengambilan paksa, memasuki tempat tertutup tanpa izin, menggelapkan kendaraan atau kelengkapannya, serta menyebarkan data debitur kepada pihak yang tidak berkepentingan</b>.</li>
      <li>PENERIMA TUGAS wajib mempertanggungjawabkan pelaksanaan tugas, melaporkan setiap kejadian dan tidak mengalihkan penugasan tanpa persetujuan tertulis. Pelanggaran dapat mengakibatkan pencabutan tugas dan tindak lanjut sesuai ketentuan yang berlaku.</li>
      <li>Surat tugas berlaku sejak <b>{date(d.letter.valid_from)}</b> sampai dengan <b>{date(d.letter.valid_until)}</b>, dan berakhir apabila tugas selesai atau penugasan dibatalkan/dicabut oleh PEMBERI TUGAS.</li>
    </ol>
    <div className="field-closing">
    <div style={{ textAlign: "right", marginTop: 8 }}>{company.city || "-"}, {date(d.letter.issue_date)}</div>
    <div className="field-signers">
      <div>PEMBERI TUGAS<br /><b>{company.name}</b></div><div>PENERIMA TUGAS<br />{d.officer.position || "Petugas"}</div>
      <div className="field-signature">{signature && <img src={signature} alt="Tanda tangan direktur" data-testid="director-signature" />}</div><div className="field-signature" />
      <div><b><u>{company.director_name || "-"}</u></b></div><div><b><u>{d.officer.name || "-"}</u></b></div>
      <div>{company.director_position || "Direktur"}</div><div>{d.officer.position || "Petugas"}</div>
    </div>
    <div className="field-verification">
      {doc.is_finalized && <img src={qrSrc} alt="QR verifikasi surat tugas" data-testid="doc-qr" style={{ width: 50, height: 50 }} />}
      <div><b>{doc.is_finalized ? "VERIFIKASI SURAT TUGAS" : "DRAFT - BELUM DIFINALISASI"}</b><br />Kode: {d.letter.generate_code || "-"}<br />Pindai QR untuk memeriksa nomor dan status surat pada aplikasi.</div>
      <div style={{ marginLeft: "auto" }}>Tembusan:<br />1. {finance}<br />2. Administrasi {company.name}<br />3. Arsip</div>
    </div>
    <div className="field-footer">{[company.address, company.email && `Email: ${company.email}`, company.phone && `Telp: ${company.phone}`].filter(Boolean).join(" · ")}</div>
    </div>
  </div>;
}
