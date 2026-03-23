import asyncio
import io
import json
from unittest.mock import Mock
from backend.api.scope_validator import validate_scope

async def test():
    # create dummy upload files
    class DummyFile:
        def __init__(self, name, content):
            self.filename = name
            self.content = content
        async def read(self):
            return self.content

    print("Running validate_scope...")
    try:
        # Word document placeholder
        import docx
        doc = docx.Document()
        doc.add_paragraph("Validation plan text")
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_bytes = doc_io.getvalue()
        
        doc_upload = DummyFile("val.docx", doc_bytes)
        scope_upload = DummyFile("test.png", b"fake png data")
        
        res = await validate_scope(
            document=doc_upload,
            scope_items="[]",
            scope_document=scope_upload
        )
        print("Success!", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
