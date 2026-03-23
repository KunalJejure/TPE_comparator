import io
import os
import base64
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import HTTPException

# Optional dependencies
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger(__name__)

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract text from a support document (PDF, DOCX, TXT, or Image)."""
    fname_lower = filename.lower()

    # 1. Plain Text
    if fname_lower.endswith(".txt"):
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="replace")

    # 2. DOCX
    elif fname_lower.endswith(".docx"):
        if not Document:
            raise HTTPException(status_code=500, detail="python-docx not installed")
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())

    # 3. PDF
    elif fname_lower.endswith(".pdf"):
        if not fitz:
            raise HTTPException(status_code=500, detail="PyMuPDF (fitz) not installed")
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        texts = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(texts)

    # 4. Images (OCR or Vision API)
    elif fname_lower.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif")):
        # --- Priority 1: Groq Vision API ---
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
                
                # Preprocess image
                if Image:
                    img = Image.open(io.BytesIO(file_bytes))
                    if img.mode != "RGB": img = img.convert("RGB")
                    img.thumbnail((1200, 1200))
                    out_io = io.BytesIO()
                    img.save(out_io, format="JPEG")
                    processed_bytes = out_io.getvalue()
                    mime_type = "image/jpeg"
                else:
                    processed_bytes = file_bytes
                    mime_type = "image/png"

                b64_image = base64.b64encode(processed_bytes).decode("utf-8")
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract all text from this document image. Return only the raw text."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}}
                        ]
                    }],
                    temperature=0
                )
                vision_text = response.choices[0].message.content.strip()
                if vision_text: return vision_text
            except Exception as e:
                logger.warning("Groq Vision failed: %s", e)

        # --- Priority 2: PyMuPDF OCR (if supported) ---
        if fitz:
            try:
                doc = fitz.open(stream=file_bytes, filetype="png")
                res = "\n".join(page.get_text() for page in doc).strip()
                doc.close()
                if res: return res
            except: pass

        # --- Priority 3: Pytesseract OCR ---
        try:
            import pytesseract
            if not Image: raise ImportError()
            img = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(img).strip()
        except: pass

        raise HTTPException(status_code=400, detail="Could not extract text from image. Check GROQ_API_KEY or install pytesseract.")

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {filename}")
