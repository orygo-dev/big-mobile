/** Current tenant settings, shared by assignment letters and their attachments. */
export default function CompanyLetterhead({ company = {}, title, number }) {
  const name = company.name ?? company.nama ?? "";
  const address = company.address ?? company.alamat ?? "";
  const phone = company.phone ?? company.telepon ?? "";
  return (
    <header data-testid="company-letterhead" style={{ marginBottom: 14, breakInside: "avoid" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, borderBottom: "3px solid #111", paddingBottom: 10 }}>
        {company.logo && <img src={company.logo} alt={`Logo ${name}`} style={{ width: 76, height: 64, flexShrink: 0, objectFit: "contain" }} />}
        <div style={{ flex: 1, textAlign: "center", overflowWrap: "anywhere" }}>
          <div style={{ fontSize: 17, fontWeight: 800, lineHeight: 1.3 }}>{name}</div>
          {address && <div style={{ fontSize: 10, lineHeight: 1.4, marginTop: 3, whiteSpace: "pre-line" }}>{address}</div>}
          {(company.email || phone) && <div style={{ fontSize: 10, lineHeight: 1.4, marginTop: 2 }}>
            {[company.email && `Email: ${company.email}`, phone && `Telp: ${phone}`].filter(Boolean).join(" · ")}
          </div>}
        </div>
        {company.logo && <div aria-hidden="true" style={{ width: 76, flexShrink: 0 }} />}
      </div>
      {title && <div style={{ textAlign: "center", marginTop: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 800 }}>{title}</div>
        {number && <div style={{ fontSize: 11, marginTop: 2 }}>Nomor: {number}</div>}
      </div>}
    </header>
  );
}
