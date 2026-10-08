import io
from pypdf import PdfReader
from pypdf.generic import DictionaryObject, ArrayObject, IndirectObject


def validate_pdf(content):
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 200:
        raise ValueError("PDF must have 1–200 unencrypted pages")
    visited = set()
    count = 0
    forbidden = {"/JavaScript", "/JS", "/OpenAction", "/AA", "/Launch", "/EmbeddedFiles"}
    def inspect(value, depth=0):
        nonlocal count
        count += 1
        if count > 20000 or depth > 50:
            raise ValueError("PDF structure too complex")
        if isinstance(value, IndirectObject):
            key = (value.idnum, value.generation)
            if key in visited:
                return
            visited.add(key)
            inspect(value.get_object(), depth+1)
        elif isinstance(value, DictionaryObject):
            if any(key in forbidden for key in value):
                raise ValueError("PDF active content is not allowed")
            for item in value.values():
                inspect(item, depth+1)
        elif isinstance(value, ArrayObject):
            for item in value:
                inspect(item, depth+1)
    inspect(reader.trailer)
