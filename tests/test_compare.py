from __future__ import annotations

"""Basic tests for the PDF Comparator."""

import tempfile
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.services.pdf_parser import extract_text, page_to_image
from backend.services.diff_engine import text_diff
from backend.services.visual_diff import generate_diff_overlay


def _create_sample_pdfs(tmpdir: Path):
    """Create two simple one-page PDFs for testing."""
    pdf1 = tmpdir / "original.pdf"
    pdf2 = tmpdir / "revised.pdf"

    c1 = canvas.Canvas(str(pdf1), pagesize=letter)
    c1.drawString(72, 750, "Original Document")
    c1.drawString(72, 730, "Page 1 Content")
    c1.showPage()
    c1.save()

    c2 = canvas.Canvas(str(pdf2), pagesize=letter)
    c2.drawString(72, 750, "Revised Document")
    c2.drawString(72, 730, "Page 1 Content - Modified")
    c2.showPage()
    c2.save()

    return pdf1, pdf2


def test_extract_text_and_page_to_image():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        pdf1, _ = _create_sample_pdfs(tmpdir)

        texts = extract_text(str(pdf1))
        assert texts, "Expected at least one page of text"
        assert isinstance(texts[0], str)
        assert "Original Document" in texts[0]

        image = page_to_image(str(pdf1), 0)
        assert image is not None
        width, height = image.size
        assert width > 0 and height > 0


def test_text_and_visual_diff():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        pdf1, pdf2 = _create_sample_pdfs(tmpdir)

        texts1 = extract_text(str(pdf1))
        texts2 = extract_text(str(pdf2))
        diffs = text_diff(texts1, texts2)

        assert isinstance(diffs, dict)
        assert any(v for v in diffs.values())

        img1 = page_to_image(str(pdf1), 0)
        img2 = page_to_image(str(pdf2), 0)
        diff_img, similarity, region_count = generate_diff_overlay(img1, img2)

        assert diff_img is not None
        assert 0.0 <= similarity <= 1.0
