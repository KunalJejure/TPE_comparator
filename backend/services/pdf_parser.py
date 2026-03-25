from __future__ import annotations

"""PDF parsing utilities — text extraction and page-to-image rendering.

Uses PyMuPDF (fitz) which renders pages at pixel-perfect quality,
preserving all embedded images, screenshots, charts, and layout exactly
as they appear in the PDF.

Step 4 accuracy improvement: added structured text extraction
(``get_text("dict", sort=True)``) and table extraction
(``page.find_tables()``) to preserve document structure for comparison.
"""

import io
import logging
import os
import base64
import re
from pathlib import Path
from typing import Any, Dict, List

import fitz  # PyMuPDF
from PIL import Image

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

# Render DPI — 200 gives excellent quality for text and embedded images
# while keeping file sizes reasonable for large (30+ page) PDFs.
RENDER_DPI = 200


def extract_text(pdf_path: str) -> List[str]:
    """Extract text from a PDF file, page by page.

    Uses ``sort=True`` so text follows the natural reading order
    (top-left to bottom-right), which is critical for multi-column
    layouts and prevents columns from interleaving.

    Returns:
        List of text strings, one per page, in order.
    """
    path = Path(pdf_path)
    if not path.is_file():
        msg = f"PDF not found at: {pdf_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    texts: List[str] = []
    doc = None

    try:
        doc = fitz.open(pdf_path)
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            # sort=True reorders text to natural reading order
            text = page.get_text(sort=True)
            if len(text.strip()) < 10:
                logger.info(f"Page {page_index + 1} appears to be a scanned image. Running OCR fallback.")
                text = _extract_text_via_vision(page)
            texts.append(text)
        logger.info("Extracted text from %d pages in %s", len(texts), pdf_path)
    except Exception as exc:
        logger.exception("Failed to extract text from %s", pdf_path)
        raise exc
    finally:
        if doc is not None:
            doc.close()

    return texts


def extract_structured_text(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract text with structure metadata per page.

    Uses ``get_text("dict", sort=True)`` to return block-level data
    with font info, bounding boxes, and logical section inference.

    Returns:
        List of dicts (one per page), each containing:
          - ``lines``: list of {text, font_size, is_bold, is_heading, bbox}
          - ``tables``: list of extracted table grids (if any)
          - ``raw_text``: plain text for backward compatibility
    """
    path = Path(pdf_path)
    if not path.is_file():
        msg = f"PDF not found at: {pdf_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    pages: List[Dict[str, Any]] = []
    doc = None

    try:
        doc = fitz.open(pdf_path)
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            page_dict = page.get_text("dict", sort=True)

            structured_lines: List[Dict[str, Any]] = []
            raw_parts: List[str] = []

            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:  # type 0 = text block
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue

                    text = " ".join(s["text"] for s in spans).strip()
                    if not text:
                        continue

                    font_size = max(s.get("size", 12) for s in spans)
                    is_bold = any(s.get("flags", 0) & (1 << 4) for s in spans)
                    # Heuristic: headings are bold text with font_size > 13
                    is_heading = is_bold and font_size > 13

                    structured_lines.append({
                        "text": text,
                        "font_size": round(font_size, 1),
                        "is_bold": is_bold,
                        "is_heading": is_heading,
                        "bbox": block.get("bbox", []),
                    })
                    raw_parts.append(text)

            # OCR Fallback for scanned pages
            raw_text_combined = "\n".join(raw_parts).strip()
            if len(raw_text_combined) < 10:
                logger.info(f"Page {page_index + 1} appears to be a scanned image. Running OCR fallback.")
                ocr_text = _extract_text_via_vision(page)
                if ocr_text:
                    structured_lines = [{
                        "text": ocr_text,
                        "font_size": 12.0,
                        "is_bold": False,
                        "is_heading": False,
                        "bbox": [],
                    }]
                    raw_parts = [ocr_text]

            # Extract tables using PyMuPDF's find_tables (v1.23+)
            tables = _extract_page_tables(page)

            pages.append({
                "lines": structured_lines,
                "tables": tables,
                "raw_text": "\n".join(raw_parts),
            })

        logger.info(
            "Extracted structured text from %d pages in %s",
            len(pages), pdf_path,
        )
    except Exception as exc:
        logger.exception("Failed to extract structured text from %s", pdf_path)
        raise exc
    finally:
        if doc is not None:
            doc.close()

    return pages


def is_date_time_string(text: str) -> bool:
    """Check if a string looks like a date or time.

    Matches patterns like:
      - 03/16/2026
      - 2026-03-25
      - 07:31:55
      - 07:31:55:087
      - 25-Mar-2026
    """
    if not text:
        return False
    
    # Common date/time patterns
    patterns = [
        # Combined: MM/DD/YYYY HH:MM:SS (with optional milliseconds)
        r"\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}:\d{2}([:.]\d+)?",
        # MM/DD/YYYY or DD/MM/YYYY
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        # YYYY-MM-DD or DD-MM-YYYY
        r"\b\d{2,4}-\d{1,2}-\d{1,2}\b",
        # HH:MM:SS (with optional milliseconds or extra digits)
        r"\b\d{1,2}:\d{2}:\d{2}([:.]\d+)?\b",
        # DD-Mon-YYYY (e.g., 25-Mar-2026)
        r"\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b",
    ]
    
    combined = "|".join(f"({p})" for p in patterns)
    match = re.search(combined, text)
    if match:
        logger.debug("Date/time match found in text: '%s' (pattern: %s)", text, match.group())
    return bool(match)


def get_date_time_bboxes(structured_page: Dict[str, Any], scale: float = 1.0) -> List[List[float]]:
    """Extract bboxes of lines that contain date/time strings.
    
    Args:
        structured_page: Page dict from extract_structured_text.
        scale: Scaling factor (e.g., RENDER_DPI / 72).
    """
    bboxes = []
    for line in structured_page.get("lines", []):
        text = line.get("text", "")
        if is_date_time_string(text):
            bbox = line.get("bbox", [])
            if bbox:
                # Scale from points to pixels
                scaled_bbox = [c * scale for c in bbox]
                bboxes.append(scaled_bbox)
                logger.debug("Found date/time bbox: %s for text: '%s'", scaled_bbox, text)
    if bboxes:
        logger.info("Total date/time bboxes extracted: %d", len(bboxes))
    return bboxes


def _extract_page_tables(page) -> List[Dict[str, Any]]:
    """Extract tables from a single page using PyMuPDF's find_tables.

    Returns a list of table dicts, each with:
      - ``header``: list of column header strings
      - ``rows``: list of rows, each a list of cell strings
      - ``bbox``: bounding box of the table on the page
    """
    tables: List[Dict[str, Any]] = []
    try:
        tab_finder = page.find_tables()
        for table in tab_finder.tables:
            extracted = table.extract()
            if not extracted or len(extracted) < 1:
                continue
            # First row is typically headers
            header = [str(c) if c else "" for c in extracted[0]]
            rows = [
                [str(c) if c else "" for c in row]
                for row in extracted[1:]
            ]
            tables.append({
                "header": header,
                "rows": rows,
                "bbox": list(table.bbox) if hasattr(table, "bbox") else [],
            })
    except Exception as exc:
        # find_tables() may not be available in older PyMuPDF versions
        logger.debug("Table extraction skipped for page: %s", exc)

    return tables


def _extract_text_via_vision(page, dpi: int = 150) -> str:
    """Use Groq Vision API to extract text from a scanned page."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set; skipping OCR for scanned page")
        return ""
    if OpenAI is None:
        logger.warning("openai package not installed; skipping OCR")
        return ""

    try:
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img_bytes = pix.tobytes("png")
        b64_image = base64.b64encode(img_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{b64_image}"

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all the text from this image exactly as it appears. Do not include any explanations, introductory text, or markdown formatting, just the raw text."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                }
            ],
            temperature=0,
            max_tokens=4000
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Vision OCR failed: %s", exc)
        return ""


def get_page_count(pdf_path: str) -> int:
    """Return the number of pages in a PDF without loading them."""
    doc = None
    try:
        doc = fitz.open(pdf_path)
        return len(doc)
    finally:
        if doc is not None:
            doc.close()


def page_to_image(pdf_path: str, page_num: int,
                  dpi: int = RENDER_DPI) -> Image.Image:
    """Render a single PDF page to a PIL image using PyMuPDF.

    Renders at *dpi* resolution which faithfully preserves:
      - All embedded images (screenshots, photos, charts)
      - Text at crisp quality
      - Vector graphics and diagrams

    Args:
        pdf_path: Path to the PDF file on disk.
        page_num: Zero-based page index.
        dpi: Render resolution (default 200).

    Returns:
        Rendered page as a PIL Image (RGB).
    """
    if page_num < 0:
        raise ValueError("page_num must be >= 0")

    path = Path(pdf_path)
    if not path.is_file():
        msg = f"PDF not found at: {pdf_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    doc = None

    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            raise IndexError(
                f"Page {page_num} out of range (PDF has {len(doc)} pages)"
            )

        page = doc.load_page(page_num)

        # alpha=False prevents transparent background — gives us a clean
        # white page, which is what users expect for document comparison.
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        logger.debug("Rendered page %d of %s (%dx%d @ %d DPI)",
                     page_num + 1, pdf_path,
                     image.width, image.height, dpi)
        return image
    except Exception as exc:
        logger.exception("Failed to render page %d of %s", page_num, pdf_path)
        raise exc
    finally:
        if doc is not None:
            doc.close()
