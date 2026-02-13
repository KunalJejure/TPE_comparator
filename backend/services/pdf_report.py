from __future__ import annotations

"""Generate a PDF report with visual diff overlays for all pages."""

import io
import logging

from PIL import Image

from backend.services.visual_diff import generate_diff_overlay

logger = logging.getLogger(__name__)


def generate_diff_pdf(
    images1: list,
    images2: list,
):
    """Process all page-pairs, create diff overlays, assemble into a single PDF.

    Returns:
        Tuple of (pdf_bytes, page_results).
    """
    min_pages = min(len(images1), len(images2))
    diff_pil_images = []
    page_results = []

    for idx in range(min_pages):
        diff_pil, similarity, _region_count = generate_diff_overlay(
            images1[idx], images2[idx]
        )
        diff_pil_images.append(diff_pil)

        page_results.append({
            "page": idx + 1,
            "similarity": similarity,
            "status": "PASS" if similarity >= 0.90 else "FAIL",
        })

    pdf_buffer = io.BytesIO()
    if diff_pil_images:
        first = diff_pil_images[0].convert("RGB")
        rest = [img.convert("RGB") for img in diff_pil_images[1:]]
        first.save(pdf_buffer, format="PDF", save_all=True, append_images=rest, resolution=200)

    return pdf_buffer.getvalue(), page_results
