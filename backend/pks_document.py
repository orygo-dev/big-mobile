"""Versioned PKS template based on the supplied two-page agreement.
Identity and banking values are always taken from a frozen, server-built snapshot.
"""
import base64
import io
import json
import re
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape
from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
from PIL import Image as PILImage

VERSION = 'big-pks-1'
CLAUSES = json.loads((Path(__file__).parent/'templates/pks_clauses.json').read_text(encoding='utf-8'))
MONTHS = ('Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember')
DAYS = ('Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu')
ROMAN = ('I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII')
COMPANY_FIELDS = ('nama','alamat','telepon','email','city','director_name','director_position','logo')
OFFICER_FIELDS = ('id','name','petugas_code','nik','alamat','telepon','email','bank_name','bank_branch','bank_account_number','bank_account_name')

def snapshot(company, officer, dates, duration, unit):
    required_company = {'nama':'nama perusahaan','alamat':'alamat perusahaan','telepon':'telepon perusahaan','city':'kota perusahaan','director_name':'nama direktur','director_position':'jabatan direktur'}
    required_officer = {'name':'nama petugas','nik':'NIK petugas','alamat':'alamat petugas','telepon':'telepon petugas','bank_name':'nama bank','bank_account_number':'nomor rekening','bank_account_name':'nama pemilik rekening'}
    missing = [label for key,label in required_company.items() if not str(company.get(key) or '').strip()]
    missing += [label for key,label in required_officer.items() if not str(officer.get(key) or '').strip()]
    if missing:
        raise HTTPException(400,'Lengkapi data di Pengaturan/Petugas sebelum membuat PKS: '+', '.join(missing)+'.')
    if not re.fullmatch(r'\d{16}',str(officer['nik']).strip()):
        raise HTTPException(400,'NIK petugas harus berisi 16 digit. Perbarui melalui menu Petugas.')
    if not re.fullmatch(r'\d{5,40}',str(officer['bank_account_number']).strip()):
        raise HTTPException(400,'Nomor rekening petugas harus 5-40 digit, termasuk angka nol di depan jika ada.')
    for values,fields in ((company,COMPANY_FIELDS),(officer,OFFICER_FIELDS)):
        for key in fields:
            if key=='logo':continue
            value=str(values.get(key) or '')
            limit=1200 if key=='alamat' else 320 if key=='email' else 256
            if len(value)>limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',value):
                raise HTTPException(400,'Data identitas terlalu panjang atau tidak valid. Periksa Pengaturan dan menu Petugas.')
    # Explicit whitelist excludes credentials, private configuration and signature images.
    def copy(values, fields):return {key:str(values.get(key) or '').strip() for key in fields}
    return {'template_version':VERSION,'company':copy(company,COMPANY_FIELDS),'officer':copy(officer,OFFICER_FIELDS),**dates,'duration':duration,'duration_unit':unit}

def date_words(value):
    d=date.fromisoformat(value)
    return f'{d.day} {MONTHS[d.month-1]} {d.year}'

def terbilang(n):
    ones=('nol','satu','dua','tiga','empat','lima','enam','tujuh','delapan','sembilan','sepuluh','sebelas')
    if n<12:return ones[n]
    if n<20:return ones[n-10]+' belas'
    if n<100:return ones[n//10]+' puluh'+(' '+terbilang(n%10) if n%10 else '')
    if n<200:return 'seratus'+(' '+terbilang(n-100) if n>100 else '')
    if n<1000:return ones[n//100]+' ratus'+(' '+terbilang(n%100) if n%100 else '')
    if n<2000:return 'seribu'+(' '+terbilang(n-1000) if n>1000 else '')
    return terbilang(n//1000)+' ribu'+(' '+terbilang(n%1000) if n%1000 else '')

class NumberedCanvas:
    """Canvas factory with total-page footer, including overflow on long identities."""
    @staticmethod
    def create(*args,**kwargs):
        from reportlab.pdfgen.canvas import Canvas
        class Counted(Canvas):
            def __init__(self,*a,**k):super().__init__(*a,**k);self.saved=[]
            def showPage(self):self.saved.append(dict(self.__dict__));self._startPage()
            def save(self):
                total=len(self.saved)
                for state in self.saved:
                    self.__dict__.update(state);self.setFont('Times-Roman',7);self.drawRightString(A4[0]-28,19,f'Halaman {self._pageNumber}/{total}');super().showPage()
                super().save()
        return Counted(*args,**kwargs)

def render(data, number='DRAFT/BIG-PKSM', draft=True):
    company=data['company'];officer=data['officer'];start=date.fromisoformat(data['start_date'])
    out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=28,rightMargin=28,topMargin=27,bottomMargin=33,title='Perjanjian Kerjasama Mitra Penagihan '+number,author=company['nama'])
    body=ParagraphStyle('PKSBody',fontName='Times-Roman',fontSize=7.4,leading=8.5,alignment=TA_JUSTIFY,spaceAfter=1.2,splitLongWords=True)
    title=ParagraphStyle('PKSTitle',parent=body,fontName='Times-Bold',fontSize=9,leading=10.5,alignment=TA_CENTER,spaceAfter=4)
    heading=ParagraphStyle('PKSHeading',parent=body,fontName='Times-Bold',alignment=TA_CENTER,spaceBefore=4,spaceAfter=2,keepWithNext=True)
    numbered=ParagraphStyle('PKSNumbered',parent=body,leftIndent=10,firstLineIndent=-10)
    def p(text,style=body):
        if style is body and re.match(r'^(\d+\.|[a-d]\.)\s',str(text)):style=numbered
        return Paragraph(escape(str(text)).replace('\n','<br/>'),style)
    story=[]
    logo=company.get('logo','')
    if logo.startswith('data:image/') and ';base64,' in logo:
        try:
            raw=base64.b64decode(logo.split(';base64,',1)[1],validate=True)
            if len(raw)>2_500_000:raise ValueError('Logo too large')
            with PILImage.open(io.BytesIO(raw)) as picture:
                if picture.width*picture.height>12_000_000:raise ValueError('Logo too large')
                ratio=picture.width/picture.height
            image=Image(io.BytesIO(raw),width=min(85,50*ratio),height=min(50,85/ratio));image.hAlign='LEFT';story.extend([image,Spacer(1,7)])
        except Exception:
            # No remote image URLs are fetched; keep company identity if a legacy logo is unusable.
            story.append(p(company['nama'],title))
    else:story.append(p(company['nama'],title))
    story.extend([p('PERJANJIAN KERJASAMA MITRA PENAGIHAN',title),p('Nomor: '+number,title)])
    if draft:story.append(p('DRAFT - BELUM DITANDATANGANI',ParagraphStyle('Draft',parent=title,textColor=colors.HexColor('#b45309'),fontSize=7.2)))
    story.append(p(f'Pada hari ini {DAYS[start.weekday()]}, tanggal {terbilang(start.day)}, bulan {MONTHS[start.month-1]}, {terbilang(start.year)} ({start.strftime("%d-%m-%Y")}), telah dibuat dan ditandatangani Perjanjian Kerjasama Mitra Penagihan oleh dan antara:'))
    story.append(p(f'1. {company["nama"]}, perseroan terbatas yang didirikan berdasarkan hukum Negara Republik Indonesia, berkedudukan dan berkantor di {company["alamat"]}, dalam perbuatan hukum ini diwakili oleh {company["director_name"]}, bertindak dalam kedudukannya selaku {company["director_position"]}, dengan demikian sah bertindak untuk dan atas nama {company["nama"]} (selanjutnya disebut "PIHAK PERTAMA").'))
    story.append(p(f'2. {officer["name"]}, pemegang Kartu Tanda Penduduk (KTP) nomor {officer["nik"]}, beralamat {officer["alamat"]}, dalam hal ini bertindak untuk dan atas nama diri sendiri (selanjutnya disebut "Mitra").'))
    story.append(p('PIHAK PERTAMA dan Mitra secara bersama-sama disebut "Para Pihak" dan masing-masing disebut "Pihak", terlebih dahulu menerangkan hal-hal sebagai berikut:'))
    for line in ['a. Bahwa PIHAK PERTAMA adalah perseroan terbatas yang menjalankan usaha di bidang jasa konsultasi manajemen sumber daya manusia, termasuk untuk melakukan penagihan utang;', 'b. Bahwa Mitra adalah perseorangan yang mempunyai persyaratan dan kemampuan untuk melakukan penagihan;', 'c. Bahwa PIHAK PERTAMA bermaksud membuka kesempatan menjadi mitra bagi pihak-pihak yang bersedia untuk melakukan penagihan;', 'd. Bahwa Mitra dengan ini menyatakan kesediaannya untuk menjadi Mitra PIHAK PERTAMA dalam melakukan penagihan.']:
        story.append(p(line))
    story.append(p('Para Pihak telah setuju dan sepakat untuk membuat, menetapkan, melaksanakan dan mematuhi Perjanjian Kerjasama Mitra Penagihan ini (selanjutnya disebut "Perjanjian") dengan syarat dan ketentuan sebagai berikut:'))
    def information(rows):
        table=Table([[p(label),p(': '+str(value or '-'))] for label,value in rows],colWidths=[88,doc.width-88],hAlign='LEFT')
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]));return table
    for n in range(1,13):
        section_start=len(story)
        section=CLAUSES[str(n)]
        if n==7:story.append(Spacer(1,3))
        story.append(p(f'PASAL {n}\n{section["title"]}',heading))
        if n==6:
            unit='tahun' if data['duration_unit']=='TAHUN' else 'bulan'
            story.append(p(f'1. Perjanjian ini berlaku selama {data["duration"]} ({terbilang(data["duration"])}) {unit}, mulai tanggal {date_words(data["start_date"])} sampai dengan tanggal {date_words(data["end_date"])}.'))
        if n==10:
            story.append(p('1. Untuk keperluan komunikasi, surat menyurat dan pemberitahuan antara Para Pihak, disepakati alamat pemberitahuan dan wakil Para Pihak sebagai berikut:'))
            story.append(p(company['nama']))
            story.append(information([('Alamat',company['alamat']),('Telepon',company['telepon']),('Email',company['email']),('Up',company['director_name'])]))
            story.append(p('MITRA - '+officer['name']))
            story.append(information([('Alamat',officer['alamat']),('Telepon',officer['telepon']),('Email',officer['email']),('Up',officer['name'])]))
        for paragraph in section['paragraphs']:story.append(p(paragraph))
        if n==6:story[section_start:]=[KeepTogether(story[section_start:])]
        if n==5:
            story.append(information([('Nama Bank',officer['bank_name']),('Cabang Bank',officer['bank_branch']),('No. Rekening',officer['bank_account_number']),('Atas Nama',officer['bank_account_name'])]))
            story.append(p('Nama yang tercatat pada rekening adalah nama pihak yang menandatangani Perjanjian ini.'))
    story.append(p('Demikian Perjanjian ini dibuat dalam rangkap 2 (dua), masing-masing bermaterai cukup dan mempunyai kekuatan hukum yang sama.'))
    signature=Table([[p(company['city']+', '+date_words(data['start_date'])),p('')],[p(company['nama']),p('MITRA')],[Spacer(1,48),Spacer(1,48)],[p(company['director_name']),p(officer['name'])],[p(company['director_position']),p('')]],colWidths=[doc.width/2]*2)
    signature.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1)]))
    story.append(KeepTogether([Spacer(1,7),signature]));doc.build(story,canvasmaker=NumberedCanvas.create)
    return out.getvalue()
