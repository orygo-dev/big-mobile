import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import FieldAssignmentLetter from "./FieldAssignmentLetter";

const fixture = {
  is_finalized: false,
  data: {
    company: {name: "PT. BERKAT INTIM GENERASI", director_name: "Direktur Contoh", city: "Palangka Raya", address: "Alamat perusahaan"},
    finance: {name: "Leasing Contoh"},
    officer: {name: "Petugas Contoh", nik: "1234567890123456", certification_number: "SPPI-123"},
    letter: {document_number: "018/BIG-SKS/X/2026", issue_date: "2026-10-10", valid_from: "2026-10-10", valid_until: "2026-10-24"},
    accounts: [{contract_number: "KONTRAK-1", debtor_name: "Debitur Satu"}, {contract_number: "KONTRAK-2", debtor_name: "Debitur Dua"}],
  },
};

describe("field assignment letter", () => {
  it("renders the substitution title underlined and the stored official number unchanged", () => {
    const html=renderToStaticMarkup(<FieldAssignmentLetter doc={fixture}/>);
    expect(html).toContain('text-decoration:underline');
    expect(html).toContain('SURAT KUASA SUBSTITUSI');
    expect(html).toContain('Nomor: 018/BIG-SKS/X/2026');
  });
  it("lists every assigned officer in both the identity table and signature area", () => {
    const officers = [{id: 'first', name: 'Petugas Pertama', nik: 'NIK-SATU'}, {id: 'second', name: 'Petugas Kedua', nik: 'NIK-DUA'}];
    const html = renderToStaticMarkup(<FieldAssignmentLetter doc={{...fixture, data: {...fixture.data, officers}}} />);
    expect(html.match(/Petugas Pertama/g)).toHaveLength(2);
    expect(html.match(/Petugas Kedua/g)).toHaveLength(2);
    expect(html).toContain('NIK-SATU'); expect(html).toContain('NIK-DUA');
    expect(html.match(/data-testid="assignment-recipient"/g)).toHaveLength(2);
  });
  it("shows every contract and the configured validity instead of assuming seven days", () => {
    const html = renderToStaticMarkup(<FieldAssignmentLetter doc={fixture} />);
    for (const value of ["KONTRAK-1", "KONTRAK-2", "Debitur Satu", "Debitur Dua", "24 Oktober 2026", "SPPI-123", "KHUSUS", "Tembusan:"]) expect(html).toContain(value);
    expect(html).not.toContain("selama 7 hari");
    expect(html).toContain("pengambilan paksa");
    expect(html).toContain("dilarang menerima pembayaran");
    expect(html).not.toContain("data-testid=\"doc-qr\"");
  });
  it("uses the supplied signature and shows a verification QR only for finalized letters", () => {
    const html = renderToStaticMarkup(<FieldAssignmentLetter doc={{...fixture, is_finalized: true, director_signature: "data:image/png;base64,signature"}} qrSrc="/api/surat-tugas/letter/qr" />);
    expect(html).toContain("data:image/png;base64,signature");
    expect(html).toContain("/api/surat-tugas/letter/qr");
    expect(html).toContain("data-testid=\"doc-qr\"");
  });
});
