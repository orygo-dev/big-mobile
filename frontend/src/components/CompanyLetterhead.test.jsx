import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import CompanyLetterhead from './CompanyLetterhead';

describe('company letterhead', () => {
  const logo = 'data:image/png;base64,c2V0dGluZ3M=';
  it('prints the configured logo and all company contact details', () => {
    const html = renderToStaticMarkup(<CompanyLetterhead company={{name:'PT Reborn Partner',address:'Jl. Kantor 12',email:'office@rebornpartner.xyz',phone:'021-12345',logo}} title="SURAT PENUGASAN" number="001/RP" />);
    for (const text of [logo,'PT Reborn Partner','Jl. Kantor 12','office@rebornpartner.xyz','021-12345','SURAT PENUGASAN','001/RP']) expect(html).toContain(text);
    expect(html).not.toContain('Garda Koleksi');
    expect(html).not.toContain('>FC<');
  });
  it('accepts the company settings field names used by the legacy print page', () => {
    const html = renderToStaticMarkup(<CompanyLetterhead company={{nama:'PT Current',alamat:'Alamat Pengaturan',telepon:'081234',email:'current@example.com',logo}} />);
    for (const text of ['PT Current','Alamat Pengaturan','081234','current@example.com',logo]) expect(html).toContain(text);
  });
  it('does not invent a logo or contact details when settings are empty', () => {
    const html = renderToStaticMarkup(<CompanyLetterhead company={{name:'PT Current'}} />);
    expect(html).not.toContain('<img');
    expect(html).not.toContain('Email:');
    expect(html).not.toContain('Telp:');
  });
});
