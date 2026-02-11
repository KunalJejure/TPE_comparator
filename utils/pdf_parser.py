from __future__ import annotations

"""PDF parsing utilities for text and page images."""

import logging
from pathlib import Path
from typing import List
import io

import fitz  # PyMuPDF
from PIL import Image


logger = logging.getLogger(__name__)


def extract_text(pdf_path: str) -> List[str]:
    """Extract text from a PDF file, page by page.

    Args:
        pdf_path: Path to the PDF file on disk.

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

    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to extract text from %s", pdf_path)
        raise exc

    finally:
        if doc is not None:
            doc.close()

    return texts


def page_to_image(pdf_path: str, page_num: int) -> Image.Image:
    """Render a single PDF page to a PIL image using PyMuPDF.

    Args:
        pdf_path: Path to the PDF file on disk.
        page_num: Zero-based page index.

    Returns:
        Rendered page as a PIL Image.
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
            raise IndexError("Page number out of range")

        page = doc.load_page(page_num)

        # Render page to image
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")

        image = Image.open(io.BytesIO(img_bytes))

        logger.info("Rendered page %d of %s to image", page_num + 1, pdf_path)
        return image

    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to render page %d of %s", page_num, pdf_path)
        raise exc

    finally:
        if doc is not None:
            doc.close()
