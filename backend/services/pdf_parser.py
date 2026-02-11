from __future__ import annotations

"""PDF parsing utilities — text extraction and page-to-image rendering.

Uses PyMuPDF (fitz) which renders pages at pixel-perfect quality,
preserving all embedded images, screenshots, charts, and layout exactly
as they appear in the PDF.
"""

import io
import logging
from pathlib import Path
from typing import List

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

# Render DPI — 200 gives excellent quality for text and embedded images
# while keeping file sizes reasonable for large (30+ page) PDFs.
RENDER_DPI = 200


def extract_text(pdf_path: str) -> List[str]:
    """Extract text from a PDF file, page by page.

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
            texts.append(page.get_text())
        logger.info("Extracted text from %d pages in %s", len(texts), pdf_path)
    except Exception as exc:
        logger.exception("Failed to extract text from %s", pdf_path)
        raise exc
    finally:
        if doc is not None:
            doc.close()

    return texts


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
      • All embedded images (screenshots, photos, charts)
      • Text at crisp quality
      • Vector graphics and diagrams

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
