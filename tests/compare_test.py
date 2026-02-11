from __future__ import annotations

"""Basic tests for the PDF Comparator POC."""

from pathlib import Path
import tempfile

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from utils.pdf_parser import extract_text, page_to_image
from utils.diff_engine import text_diff, visual_diff


def _create_sample_pdfs(tmpdir: Path) -> tuple[Path, Path]:
    """Create two simple one-page PDFs for testing."""
    pdf1 = tmpdir / "original.pdf"
    pdf2 = tmpdir / "revised.pdf"

    # Original PDF
    c1 = canvas.Canvas(str(pdf1), pagesize=letter)
    c1.drawString(72, 750, "Original Document")
    c1.drawString(72, 730, "Page 1 Content")
    c1.showPage()
    c1.save()

    # Revised PDF with slightly different text
    c2 = canvas.Canvas(str(pdf2), pagesize=letter)
    c2.drawString(72, 750, "Revised Document")
    c2.drawString(72, 730, "Page 1 Content - Modified")
    c2.showPage()
    c2.save()

    return pdf1, pdf2


def test_extract_text_and_page_to_image() -> None:
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


def test_text_and_visual_diff() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        pdf1, pdf2 = _create_sample_pdfs(tmpdir)

        texts1 = extract_text(str(pdf1))
        texts2 = extract_text(str(pdf2))
        diffs = text_diff(texts1, texts2)

        assert isinstance(diffs, dict)
        # Expect at least one page with changes
        assert any(v for v in diffs.values())

        img1 = page_to_image(str(pdf1), 0)
        img2 = page_to_image(str(pdf2), 0)
        diff_img, similarity = visual_diff(img1, img2)

        assert diff_img is not None
        assert 0.0 <= similarity <= 1.0

