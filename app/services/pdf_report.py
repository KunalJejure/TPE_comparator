# app/services/pdf_report.py

"""Generate a PDF report with visual diff overlays for all pages."""

import io

import cv2
import numpy as np
from PIL import Image

from services.visual_diff import generate_visual_diff


def generate_diff_pdf(
    images1: list[Image.Image],
    images2: list[Image.Image],
) -> tuple[bytes, list[dict]]:
    """
    Process all page-pairs, create diff overlays, and assemble into a single PDF.

    Args:
        images1: List of PIL Images from the reference PDF.
        images2: List of PIL Images from the compared PDF.

    Returns:
        Tuple of (pdf_bytes, page_results) where:
          - pdf_bytes: The generated diff PDF as bytes.
          - page_results: List of dicts with per-page similarity info.
    """
    min_pages = min(len(images1), len(images2))
    diff_pil_images: list[Image.Image] = []
    page_results: list[dict] = []

    for idx in range(min_pages):
        # Convert PIL → BGR numpy (OpenCV format)
        img1_cv = cv2.cvtColor(np.array(images1[idx].convert("RGB")), cv2.COLOR_RGB2BGR)
        img2_cv = cv2.cvtColor(np.array(images2[idx].convert("RGB")), cv2.COLOR_RGB2BGR)

        # Ensure same dimensions
        if img1_cv.shape != img2_cv.shape:
            img2_cv = cv2.resize(img2_cv, (img1_cv.shape[1], img1_cv.shape[0]))

        # Generate visual diff
        diff_bgr, similarity = generate_visual_diff(img1_cv, img2_cv)

        # Convert BGR → RGB → PIL for PDF assembly
        diff_rgb = cv2.cvtColor(diff_bgr, cv2.COLOR_BGR2RGB)
        diff_pil = Image.fromarray(diff_rgb)
        diff_pil_images.append(diff_pil)

        page_results.append({
            "page": idx + 1,
            "similarity": similarity,
            "status": "PASS" if similarity >= 90 else "FAIL",
        })

    # Assemble all diff images into a single PDF
    pdf_buffer = io.BytesIO()
    if diff_pil_images:
        first = diff_pil_images[0].convert("RGB")
        rest = [img.convert("RGB") for img in diff_pil_images[1:]]
        first.save(pdf_buffer, format="PDF", save_all=True, append_images=rest, resolution=200)

    pdf_bytes = pdf_buffer.getvalue()
    return pdf_bytes, page_results
