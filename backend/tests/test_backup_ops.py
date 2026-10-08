import importlib.util
import io
import os
import tarfile
from pathlib import Path
import pytest
from cryptography.exceptions import InvalidTag

spec=importlib.util.spec_from_file_location('backup_ops',Path(__file__).resolve().parents[2]/'deploy/backup.py')
ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)


def test_encrypted_backup_roundtrip_and_tampering(tmp_path):
    source=tmp_path/'plain';source.write_bytes(os.urandom(1024*1024+127))
    encrypted=tmp_path/'encrypted';restored=tmp_path/'restored';key=os.urandom(32)
    ops.crypt(source,encrypted,key)
    assert encrypted.read_bytes()[:len(ops.MAGIC)]==ops.MAGIC
    ops.crypt(encrypted,restored,key,decrypt=True)
    assert restored.read_bytes()==source.read_bytes()
    with pytest.raises(InvalidTag):ops.crypt(encrypted,restored,os.urandom(32),decrypt=True)
    content=bytearray(encrypted.read_bytes());content[100]^=1;encrypted.write_bytes(content)
    with pytest.raises(InvalidTag):ops.crypt(encrypted,restored,key,decrypt=True)


@pytest.mark.parametrize('name,kind',[('../outside','file'),('/outside','file'),('link','symlink'),('link','hardlink')])
def test_restore_rejects_traversal_and_links(tmp_path,name,kind):
    archive=tmp_path/'backup.tar'
    with tarfile.open(archive,'w') as package:
        member=tarfile.TarInfo(name)
        if kind!='file':member.type=tarfile.SYMTYPE if kind=='symlink' else tarfile.LNKTYPE;member.linkname='../outside'
        else:member.size=1
        package.addfile(member,io.BytesIO(b'x'))
    with pytest.raises(ValueError):ops.safe_extract(archive,tmp_path/'output')


def test_restore_requires_isolated_target_before_io(tmp_path):
    with pytest.raises(ValueError,match='isolated-target'):
        ops.restore(tmp_path/'missing','mongodb://unused',tmp_path/'uploads',os.urandom(32))
