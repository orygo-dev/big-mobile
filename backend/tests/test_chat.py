import io
import uuid
import zipfile
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_local_regressions import local_api, ADMIN, OFFICER, bearer, server
from chat import Location, safe_filename, validate_attachment
from PIL import Image


@pytest.mark.parametrize('point', [{'latitude': 91, 'longitude': 0}, {'latitude': 0, 'longitude': -181}, {'latitude': float('nan'), 'longitude': 0}, {'latitude': 0, 'longitude': 0, 'accuracy': -1}])
def test_chat_rejects_invalid_location(point):
    with pytest.raises(ValidationError): Location(**point)


def test_chat_attachment_checks_content_and_strips_image_metadata():
    output = io.BytesIO(); Image.new('RGB', (20, 20), 'blue').save(output, 'PNG')
    content, mime, extension, kind = validate_attachment(output.getvalue(), 'photo.png', server)
    assert mime == 'image/jpeg' and extension == '.jpg' and kind == 'image'
    with Image.open(io.BytesIO(content)) as image: assert image.format == 'JPEG' and not image.getexif()
    for content, name in [(b'fake', 'photo.png'), (b'fake', 'document.pdf'), (b'fake', 'document.docx'), (b'fake', 'app.exe'), (b'\x00', 'document.txt')]:
        with pytest.raises(HTTPException): validate_attachment(content, name, server)


def test_chat_rejects_macro_and_embedded_office_document():
    for bad in ['word/vbaProject.bin', 'word/embeddings/file.bin', '../outside']:
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types/>'); archive.writestr('word/document.xml', '<document/>'); archive.writestr(bad, 'unsafe')
        with pytest.raises(HTTPException): validate_attachment(output.getvalue(), 'document.docx', server)


def test_chat_filename_has_no_path_or_header_controls():
    assert safe_filename('C:\\folder\\photo\r\n.png') == 'photo.png'


def test_chat_denies_foreign_or_unassigned_thread(local_api):
    api, db = local_api; db.users.find_one.return_value = OFFICER
    for path in ['/api/chat/other-task', '/api/chat/other-task/attachments/photo']:
        assert api.get(path, headers=bearer(OFFICER)).status_code == 404
        query = db.assignments.find_one.call_args.args[0]
        assert query['company_id'] == OFFICER['company_id'] and query['officer_id'] == OFFICER['id']
    server.get_object.assert_not_called()


def test_chat_closed_thread_rejects_send_before_storage(local_api):
    api, db = local_api; db.users.find_one.return_value = ADMIN
    db.assignments.find_one.return_value = {'id': 'task', 'status': 'SELESAI', 'officer_id': OFFICER['id']}
    response = api.post('/api/chat/task/messages', data={'client_message_id': str(uuid.uuid4()), 'text': 'Message'}, headers=bearer())
    assert response.status_code == 409
    db.chat_messages.insert_one.assert_not_called()
    db.upload_intents.insert_one.assert_not_called()


@pytest.mark.parametrize('data', [{'client_message_id': 'bad', 'text': 'Message'}, {'client_message_id': str(uuid.uuid4()), 'text': ''}, {'client_message_id': str(uuid.uuid4()), 'location': '{"latitude":999,"longitude":0}'}])
def test_chat_invalid_message_has_no_writes(local_api, data):
    api, db = local_api; db.users.find_one.return_value = ADMIN
    db.assignments.find_one.return_value = {'id': 'task', 'status': 'AKTIF', 'officer_id': OFFICER['id']}
    assert api.post('/api/chat/task/messages', data=data, headers=bearer()).status_code == 400
    db.chat_messages.insert_one.assert_not_called()


def test_chat_read_cursor_is_clamped_and_monotonic(local_api):
    api, db = local_api; db.users.find_one.return_value = ADMIN
    db.assignments.find_one.return_value = {'id': 'task', 'status': 'AKTIF', 'chat_sequence': 7}
    response = api.post('/api/chat/task/read', json={'sequence': 900}, headers=bearer())
    assert response.status_code == 200 and response.json()['sequence'] == 7
    query, update = db.chat_reads.update_one.call_args.args
    assert query == {'company_id': ADMIN['company_id'], 'assignment_id': 'task', 'user_id': ADMIN['id']}
    assert update == {'$max': {'sequence': 7}}
