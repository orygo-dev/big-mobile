"""Image stamps on private powers of attorney; originals remain immutable."""
import base64
import hashlib
import io
from datetime import datetime, timezone

from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from starlette.concurrency import run_in_threadpool

from pdf_validation import validate_pdf

MAX_IMAGE = 2 * 1024 * 1024
MAX_PDF = 16 * 1024 * 1024


class StampError(ValueError):
    pass


class Placement(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    page: int = Field(ge=1, le=200, strict=True)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode='after')
    def within_page(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError('Gambar harus berada di dalam halaman')
        return self


def normalize_image(content):
    if len(content) > MAX_IMAGE:
        raise ValueError('Ukuran gambar maksimal 2MB')
    with Image.open(io.BytesIO(content)) as source:
        if source.format not in {'PNG', 'JPEG', 'WEBP'} or source.width * source.height > 12_000_000:
            raise ValueError('Gunakan gambar PNG, JPEG, atau WebP maksimal 12 megapiksel')
        image = ImageOps.exif_transpose(source).convert('RGBA')
        if not image.getchannel('A').getbbox():
            raise ValueError('Gambar seluruhnya transparan')
        output = io.BytesIO()
        image.save(output, 'PNG')
        return output.getvalue()


def stamp_pdf(content, image, placement):
    if len(content) > MAX_PDF:
        raise StampError('PDF terlalu besar untuk diedit (maksimal 16MB)')
    validate_pdf(content)
    reader = PdfReader(io.BytesIO(content), strict=True)
    # Image stamping changes document bytes and must not invalidate a digital signature silently.
    fields = reader.get_fields() or {}
    if reader.trailer['/Root'].get('/Perms') or any(field.get('/FT') == '/Sig' for field in fields.values()):
        raise StampError('PDF memiliki bidang tanda tangan digital. Gunakan salinan PDF tanpa bidang tanda tangan digital.')
    if placement.page > len(reader.pages):
        raise StampError('Halaman yang dipilih tidak ditemukan')
    writer = PdfWriter(clone_from=reader)
    page = writer.pages[placement.page - 1]
    page.transfer_rotation_to_content()
    box = page.cropbox
    width, height = float(box.width), float(box.height)
    if not (1 <= width <= 14400 and 1 <= height <= 14400):
        raise StampError('Ukuran halaman PDF tidak didukung')
    overlay = io.BytesIO()
    canvas = Canvas(overlay, pagesize=(width, height))
    canvas.drawImage(ImageReader(io.BytesIO(image)), placement.x * width,
                     (1 - placement.y - placement.height) * height,
                     placement.width * width, placement.height * height,
                     mask='auto', preserveAspectRatio=True, anchor='c')
    canvas.save()
    page.merge_transformed_page(PdfReader(overlay).pages[0],
                                Transformation().translate(float(box.left), float(box.bottom)))
    output = io.BytesIO()
    writer.write(output)
    result = output.getvalue()
    if len(result) > MAX_PDF:
        raise StampError('Hasil PDF melebihi 16MB. Gunakan gambar dengan ukuran lebih kecil.')
    validate_pdf(result)
    return result


def register(router, runtime):
    async def get_sk(identity, user):
        result = await runtime.db.power_of_attorneys.find_one({'id': identity, 'company_id': user['company_id']})
        if not result:
            raise HTTPException(404, 'Surat Kuasa tidak ditemukan')
        return result

    @router.get('/surat-kuasa/{sk_id}/stamp-info')
    async def stamp_info(sk_id: str, user: dict = Depends(runtime.admin_required)):
        sk = await get_sk(sk_id, user)
        documents = await runtime.db.documents.find({'company_id': user['company_id'], 'kind': 'surat_kuasa', 'ref_id': sk_id}).sort('created_at', -1).to_list(None)
        company = await runtime.db.companies.find_one({'id': user['company_id']}) or {}
        return {'current_file_url': sk.get('file_url', ''),
                'signature': company.get('director_signature', ''),
                'versions': [{key: doc.get(key) for key in ('id', 'url', 'filename', 'created_at', 'stamped', 'source_document_id')} for doc in documents]}

    @router.post('/surat-kuasa/{sk_id}/stamp')
    async def save_stamp(sk_id: str, request: Request,
                         source_document_id: str = Form(..., max_length=100),
                         expected_file_url: str = Form(..., max_length=1000),
                         placement: str = Form(..., max_length=2000),
                         use_company_signature: bool = Form(False),
                         image: UploadFile | None = File(None),
                         user: dict = Depends(runtime.admin_required)):
        sk = await get_sk(sk_id, user)
        if sk.get('file_url', '') != expected_file_url:
            raise HTTPException(409, 'Dokumen telah berubah. Tutup editor dan buka kembali sebelum menyimpan.')
        scope = {'id': source_document_id, 'company_id': user['company_id'], 'kind': 'surat_kuasa', 'ref_id': sk_id}
        source = await runtime.db.documents.find_one(scope)
        if not source or not source.get('storage_path', '').startswith(f"{runtime.APP_NAME}/companies/{user['company_id']}/"):
            raise HTTPException(404, 'Dokumen sumber tidak ditemukan')
        try:
            position = Placement.model_validate_json(placement)
        except (ValidationError, ValueError):
            raise HTTPException(422, 'Posisi, ukuran gambar, atau halaman tidak valid')
        if use_company_signature == (image is not None):
            raise HTTPException(400, 'Pilih tepat satu sumber gambar tanda tangan/stempel')
        try:
            if use_company_signature:
                company = await runtime.db.companies.find_one({'id': user['company_id']}) or {}
                data_url = company.get('director_signature', '')
                prefix, encoded = data_url.split(',', 1)
                if prefix != 'data:image/png;base64' or len(encoded) > MAX_IMAGE * 2:
                    raise ValueError('Tanda tangan pengaturan tidak valid')
                image_bytes = base64.b64decode(encoded, validate=True)
            else:
                if image.content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
                    raise ValueError('Format gambar tidak didukung')
                image_bytes = await image.read(MAX_IMAGE + 1)
            normalized = await run_in_threadpool(normalize_image, image_bytes)
        except (ValueError, OSError, Image.DecompressionBombError):
            raise HTTPException(400, 'Gambar tidak valid. Gunakan PNG/JPEG/WebP maksimal 2MB dan 12 megapiksel, atau pilih tanda tangan yang tersedia di pengaturan.')
        try:
            source_bytes, _ = await run_in_threadpool(runtime.get_object, source['storage_path'])
        except FileNotFoundError:
            raise HTTPException(404, 'PDF sumber tidak ditemukan di penyimpanan')
        try:
            result = await run_in_threadpool(stamp_pdf, source_bytes, normalized, position)
        except Exception as error:
            if isinstance(error, StampError):
                raise HTTPException(400, str(error))
            runtime.logger.warning('Cannot stamp PDF: %s', type(error).__name__)
            raise HTTPException(400, 'PDF tidak dapat diedit. Gunakan PDF tanpa enkripsi, script, atau lampiran.')
        identity = runtime.new_id()
        path = f"{runtime.APP_NAME}/companies/{user['company_id']}/surat-kuasa/{sk_id}/{identity}.pdf"
        await runtime.db.upload_intents.insert_one({'id': path, 'storage_path': path, 'company_id': user['company_id'], 'created_at': datetime.now(timezone.utc)})
        stored = await run_in_threadpool(runtime.put_object, path, result, 'application/pdf')
        url = f"/api/files/{stored['path']}"

        async def persist():
            # Native repository reads inside transactions lock rows (FOR UPDATE).
            latest = await get_sk(sk_id, user)
            if latest.get('file_url', '') != expected_file_url or not await runtime.db.documents.find_one(scope):
                raise HTTPException(409, 'Dokumen telah berubah. Tutup editor dan buka kembali sebelum menyimpan.')
            await runtime.db.documents.insert_one({
                'id': identity, 'company_id': user['company_id'], 'kind': 'surat_kuasa', 'ref_id': sk_id,
                'storage_path': stored['path'], 'url': url, 'filename': 'surat-kuasa-stempel.pdf',
                'stamped': True, 'source_document_id': source_document_id,
                'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
                'sha256': hashlib.sha256(result).hexdigest(), 'placement': position.model_dump(),
                'created_by': user['id'], 'created_at': runtime.now_iso()})
            await runtime.db.power_of_attorneys.update_one({'id': sk_id, 'company_id': user['company_id']}, {'$set': {'file_url': url, 'updated_at': runtime.now_iso()}})
            await runtime.log_audit(user, f'Menambahkan tanda tangan/stempel pada Surat Kuasa (halaman {position.page})', 'surat_kuasa', sk_id, request)
            await runtime.db.upload_intents.delete_one({'id': path, 'company_id': user['company_id']})
        await runtime.transactions.run(runtime.client, persist)
        return {'id': identity, 'file_url': url}
