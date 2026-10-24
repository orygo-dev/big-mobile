import base64
import io
import json
from unittest.mock import Mock

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, RectangleObject, TextStringObject

from test_local_regressions import local_api, server, ADMIN, OFFICER, bearer
from pdf_stamp import Placement, StampError, normalize_image, stamp_pdf


def pdf_bytes(rotation=0, crop=False):
    writer = PdfWriter()
    page = writer.add_blank_page(600, 800)
    if crop:
        page.cropbox = RectangleObject((50, 100, 550, 700))
    if rotation:
        page.rotate(rotation)
    writer.add_blank_page(400, 400)
    out = io.BytesIO(); writer.write(out)
    return out.getvalue()


def image_bytes():
    out = io.BytesIO(); Image.new('RGBA', (200, 100), (0, 100, 200, 180)).save(out, 'PNG')
    return out.getvalue()


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
@pytest.mark.parametrize('crop', [False, True])
def test_stamp_preserves_page_count_and_uses_visible_top_left_coordinates(rotation, crop):
    original = pdf_bytes(rotation, crop)
    position = Placement(page=1, x=.2, y=.3, width=.3, height=.2)
    result = stamp_pdf(original, image_bytes(), position)
    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 2
    assert len(reader.pages[0].images) == 1
    assert len(reader.pages[1].images) == 0
    assert PdfReader(io.BytesIO(original)).pages[0].rotation == rotation
    page = reader.pages[0]
    assert page.rotation == rotation
    width, height = float(page.cropbox.width), float(page.cropbox.height)
    # Original page boxes/rotation are preserved, including annotation coordinates.
    assert list(page.cropbox) == list(PdfReader(io.BytesIO(original)).pages[0].cropbox)
    operations = page.get_contents().operations
    matrices = [list(map(float, values)) for values, operator in operations if operator == b'cm']
    assert matrices
    assert width > 0 and height > 0


def test_rotated_page_preserves_existing_link_rectangle_and_page_boxes():
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf_bytes(90, True))))
    from pypdf.annotations import Link
    writer.add_annotation(0, Link(rect=(100, 200, 200, 250), url='https://example.com'))
    out = io.BytesIO(); writer.write(out)
    result = stamp_pdf(out.getvalue(), image_bytes(), Placement(page=1, x=.2, y=.3, width=.3, height=.2))
    page = PdfReader(io.BytesIO(result)).pages[0]
    assert list(page['/Annots'][0].get_object()['/Rect']) == [100, 200, 200, 250]
    assert page.rotation == 90
    assert list(page.cropbox) == [50, 100, 550, 700]


@pytest.mark.parametrize('invalid', [
    {'x': -1}, {'y': .99}, {'width': 0}, {'width': 2}, {'page': 0}, {'page': 1.5}, {'x': float('nan')}, {'height': float('inf')}, {'surprise': 1}
])
def test_invalid_placement_rejected(invalid):
    with pytest.raises(ValueError):
        Placement(**({'page': 1, 'x': .2, 'y': .3, 'width': .3, 'height': .2} | invalid))


def test_invalid_page_and_signed_pdf_rejected():
    with pytest.raises(StampError, match='Halaman'):
        stamp_pdf(pdf_bytes(), image_bytes(), Placement(page=3, x=0, y=0, width=.2, height=.2))
    writer = PdfWriter()
    writer.add_blank_page(600, 800)
    field = DictionaryObject({NameObject('/FT'): NameObject('/Sig'), NameObject('/T'): TextStringObject('Signed')})
    writer._root_object[NameObject('/AcroForm')] = DictionaryObject({NameObject('/Fields'): ArrayObject([writer._add_object(field)])})
    out = io.BytesIO(); writer.write(out)
    with pytest.raises(StampError, match='tanda tangan digital'):
        stamp_pdf(out.getvalue(), image_bytes(), Placement(page=1, x=0, y=0, width=.2, height=.2))


def setup_document(local_api, monkeypatch):
    api, db = local_api
    source = {'id': 'original', 'company_id': ADMIN['company_id'], 'kind': 'surat_kuasa', 'ref_id': 'sk',
              'storage_path': f"{server.APP_NAME}/companies/{ADMIN['company_id']}/surat-kuasa/sk/source.pdf", 'url': '/api/files/source.pdf', 'filename': 'original.pdf'}
    db.power_of_attorneys.find_one.return_value = {'id': 'sk', 'company_id': ADMIN['company_id'], 'file_url': source['url']}
    db.documents.find_one.return_value = source
    db.documents.find.return_value.to_list.return_value = [source]
    db.companies.find_one.return_value = {'director_signature': 'data:image/png;base64,' + base64.b64encode(image_bytes()).decode()}
    monkeypatch.setattr(server, 'get_object', Mock(return_value=(pdf_bytes(), 'application/pdf')))
    monkeypatch.setattr(server, 'put_object', Mock(side_effect=lambda path, *_: {'path': path}))
    return api, db, source


def payload(**updates):
    return {'source_document_id': 'original', 'expected_file_url': '/api/files/source.pdf', 'use_company_signature': 'true',
            'placement': json.dumps({'page': 2, 'x': .2, 'y': .3, 'width': .3, 'height': .15})} | updates


def test_stamp_info_only_exposes_scoped_versions(local_api, monkeypatch):
    api, db, source = setup_document(local_api, monkeypatch)
    result = api.get('/api/surat-kuasa/sk/stamp-info')
    assert result.status_code == 200 and result.json()['versions'][0]['id'] == 'original'
    assert 'storage_path' not in result.text
    assert db.documents.find.call_args.args[0] == {'company_id': ADMIN['company_id'], 'kind': 'surat_kuasa', 'ref_id': 'sk'}


@pytest.mark.parametrize('company_image', [True, False])
def test_save_preserves_original_adds_version_and_audit(local_api, monkeypatch, company_image):
    api, db, source = setup_document(local_api, monkeypatch)
    kwargs = {'data': payload(use_company_signature=str(company_image).lower())}
    if not company_image:
        kwargs['files'] = {'image': ('stamp.png', image_bytes(), 'image/png')}
    response = api.post('/api/surat-kuasa/sk/stamp', **kwargs)
    assert response.status_code == 200, response.text
    created = db.documents.insert_one.call_args.args[0]
    assert created['stamped'] and created['source_document_id'] == 'original'
    assert created['source_sha256'] and created['sha256']
    db.documents.update_one.assert_not_called(); db.documents.delete_one.assert_not_called()
    saved = server.put_object.call_args.args[1]
    assert len(PdfReader(io.BytesIO(saved)).pages[1].images) == 1
    assert db.power_of_attorneys.update_one.call_args.args[1]['$set']['file_url'] == response.json()['file_url']
    assert 'halaman 2' in db.audit_logs.insert_one.call_args.args[0]['activity']
    db.upload_intents.delete_one.assert_called_once()


def test_stale_source_does_not_overwrite_new_upload(local_api, monkeypatch):
    api, db, source = setup_document(local_api, monkeypatch)
    db.power_of_attorneys.find_one.side_effect = [{'id': 'sk', 'file_url': source['url']}, {'id': 'sk', 'file_url': '/api/files/replaced.pdf'}]
    response = api.post('/api/surat-kuasa/sk/stamp', data=payload())
    assert response.status_code == 409
    db.documents.insert_one.assert_not_called(); db.power_of_attorneys.update_one.assert_not_called()
    # Orphan upload remains journaled for the existing reconciliation worker.
    db.upload_intents.insert_one.assert_called_once(); db.upload_intents.delete_one.assert_not_called()


@pytest.mark.parametrize('case,expected', [('missing_sk',404),('missing_source',404),('foreign_path',404),('stale',409),('bad_position',422),('bad_image',400),('missing_company_image',400),('missing_file',404)])
def test_failures_never_update_document(local_api, monkeypatch, case, expected):
    api, db, source = setup_document(local_api, monkeypatch)
    data = payload(); files = {}
    if case == 'missing_sk': db.power_of_attorneys.find_one.return_value = None
    if case == 'missing_source': db.documents.find_one.return_value = None
    if case == 'foreign_path': db.documents.find_one.return_value = {**source, 'storage_path': 'other-company/private.pdf'}
    if case == 'stale': data['expected_file_url'] = '/api/files/older.pdf'
    if case == 'bad_position': data['placement'] = '{"page":1,"x":0.9,"y":0,"width":0.5,"height":0.1}'
    if case == 'bad_image':
        data['use_company_signature'] = 'false'; files = {'image': ('x.png', b'broken', 'image/png')}
    if case == 'missing_company_image': db.companies.find_one.return_value = {}
    if case == 'missing_file': server.get_object.side_effect = FileNotFoundError()
    assert api.post('/api/surat-kuasa/sk/stamp', data=data, files=files).status_code == expected
    db.documents.insert_one.assert_not_called(); db.power_of_attorneys.update_one.assert_not_called()
    server.put_object.assert_not_called()


@pytest.mark.parametrize('path,method', [('stamp-info','get'),('stamp','post')])
def test_officer_cannot_access_editor(local_api, path, method):
    api, db = local_api
    server.app.dependency_overrides.pop(server.admin_required)
    db.users.find_one.return_value = OFFICER
    response = getattr(api, method)('/api/surat-kuasa/sk/' + path, headers=bearer(OFFICER), **({'data': payload()} if method == 'post' else {}))
    assert response.status_code == 403
    db.documents.insert_one.assert_not_called()
