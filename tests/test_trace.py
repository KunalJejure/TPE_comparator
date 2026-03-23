import requests
import io
import docx

def create_dummy_docx():
    doc = docx.Document()
    doc.add_paragraph('Test Validation Plan content.')
    doc_io = io.BytesIO()
    doc.save(doc_io)
    return doc_io.getvalue()

files = {
    'document': ('Validation_Plan.docx', create_dummy_docx(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    'scope_document': ('Poka.png', b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff\xff\x7f\x06\x04\x00\x06\x1a\x01\xa8\xeb\x10\xe2\xd5\x00\x00\x00\x00IEND\xaeB`\x82', 'image/png')
}
data = {
    'scope_items': '[]'
}

print("Starting custom server to capture trace...")
import sys
import subprocess
import time

server_proc = subprocess.Popen(["python", "main.py"])
time.sleep(5)

print("Sending request to grab 500 trace...")
r = requests.post('http://127.0.0.1:8000/api/scope-validator/validate', files=files, data=data)
print(r.status_code)
print(r.text)
server_proc.terminate()
