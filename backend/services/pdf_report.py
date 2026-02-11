from __future__ import annotations

"""Generate a PDF report with visual diff overlays for all pages."""

import io
import logging

import cv2
import numpy as np
from PIL import Image

from backend.services.visual_diff import generate_visual_diff

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
        img1_cv = cv2.cvtColor(np.array(images1[idx].convert("RGB")), cv2.COLOR_RGB2BGR)
        img2_cv = cv2.cvtColor(np.array(images2[idx].convert("RGB")), cv2.COLOR_RGB2BGR)

        if img1_cv.shape != img2_cv.shape:
            img2_cv = cv2.resize(img2_cv, (img1_cv.shape[1], img1_cv.shape[0]))

        diff_bgr, similarity = generate_visual_diff(img1_cv, img2_cv)

        diff_rgb = cv2.cvtColor(diff_bgr, cv2.COLOR_BGR2RGB)
        diff_pil = Image.fromarray(diff_rgb)
        diff_pil_images.append(diff_pil)

        page_results.append({
            "page": idx + 1,
            "similarity": similarity,
            "status": "PASS" if similarity >= 90 else "FAIL",
        })

    pdf_buffer = io.BytesIO()
    if diff_pil_images:
        first = diff_pil_images[0].convert("RGB")
        rest = [img.convert("RGB") for img in diff_pil_images[1:]]
        first.save(pdf_buffer, format="PDF", save_all=True, append_images=rest, resolution=200)

    return pdf_buffer.getvalue(), page_results
