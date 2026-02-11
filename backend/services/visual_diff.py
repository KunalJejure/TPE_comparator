from __future__ import annotations

"""Professional visual diff engine using SSIM + bounding-box overlays.

Inspired by Adobe Acrobat-style comparison: changed regions are outlined
with coloured borders and a subtle semi-transparent highlight, keeping the
underlying text and images fully readable.
"""

import logging
from typing import Tuple

import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)

# ── Colours (BGR for OpenCV) ─────────────────────────────────────────
_RED_BORDER = (0, 0, 220)         # crisp red border
_RED_FILL = (200, 210, 255)       # very light red / pink fill
_GREEN_BORDER = (0, 180, 0)       # green border for additions
_GREEN_FILL = (210, 255, 210)     # very light green fill

# Overlay fill opacity (0.0 = invisible, 1.0 = opaque)
_FILL_ALPHA = 0.18
_BORDER_THICKNESS = 2
_PADDING = 6  # px around each changed region


def _ensure_same_size(img1: np.ndarray, img2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Resize img2 to match img1's dimensions if they differ."""
    if img1.shape[:2] != img2.shape[:2]:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]),
                          interpolation=cv2.INTER_LANCZOS4)
    return img1, img2


def _compute_diff_regions(gray1: np.ndarray, gray2: np.ndarray,
                          threshold: int = 25):
    """Use SSIM to find changed regions and return (score, contours).

    Steps:
        1. Compute SSIM with a full diff map.
        2. Threshold the diff map to isolate changed pixels.
        3. Use morphological ops to group nearby changed pixels into regions.
        4. Extract contours of those regions.
    """
    score, diff_map = ssim(gray1, gray2, full=True)

    # Invert so changed areas are bright (255)
    diff_uint8 = ((1.0 - diff_map) * 255).astype("uint8")

    # Threshold — only significant changes
    _, binary = cv2.threshold(diff_uint8, threshold, 255, cv2.THRESH_BINARY)

    # Morphological closing + dilation to group nearby change-pixels
    # into cohesive regions (avoids dozens of tiny scattered boxes).
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close,
                              iterations=2)

    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
    dilated = cv2.dilate(closed, kernel_dilate, iterations=3)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    return score, contours


def _draw_bounding_boxes(canvas: np.ndarray, contours,
                         border_colour, fill_colour,
                         alpha: float = _FILL_ALPHA,
                         padding: int = _PADDING,
                         border: int = _BORDER_THICKNESS):
    """Draw semi-transparent highlighted bounding boxes on *canvas*.

    The technique:
      1. Create a separate highlight layer with filled rectangles.
      2. Alpha-blend it onto the canvas (keeps text readable).
      3. Draw crisp borders on top after blending.
    """
    h, w = canvas.shape[:2]
    rects = []

    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        # Apply padding
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(w, x + bw + padding)
        y2 = min(h, y + bh + padding)
        rects.append((x1, y1, x2, y2))

    if not rects:
        return canvas

    # 1 – paint fills on a copy
    highlight = canvas.copy()
    for (x1, y1, x2, y2) in rects:
        cv2.rectangle(highlight, (x1, y1), (x2, y2), fill_colour, -1)

    # 2 – alpha blend
    cv2.addWeighted(highlight, alpha, canvas, 1.0 - alpha, 0, canvas)

    # 3 – crisp borders on top
    for (x1, y1, x2, y2) in rects:
        cv2.rectangle(canvas, (x1, y1), (x2, y2), border_colour, border)

    return canvas


# ── Public API ───────────────────────────────────────────────────────

def generate_diff_overlay(img1: Image.Image, img2: Image.Image):
    """Create a single, readable diff overlay image.

    The *revised* page is used as the base.  Changed regions get a subtle
    semi-transparent coloured highlight **and** a crisp coloured border so
    the text underneath stays perfectly legible.

    Args:
        img1: Original page (PIL).
        img2: Revised page (PIL).

    Returns:
        Tuple of (overlay_pil_image, similarity_0_to_1, region_count).
    """
    cv1 = cv2.cvtColor(np.array(img1.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2.convert("RGB")), cv2.COLOR_RGB2BGR)

    cv1, cv2_img = _ensure_same_size(cv1, cv2_img)

    gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

    score, contours = _compute_diff_regions(gray1, gray2)

    # Start from the revised image (user cares about the new version)
    overlay = cv2_img.copy()
    overlay = _draw_bounding_boxes(overlay, contours,
                                   border_colour=_RED_BORDER,
                                   fill_colour=_RED_FILL)

    similarity = float(max(0.0, min(1.0, score)))
    result = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))

    logger.info("Visual diff: similarity=%.4f  regions=%d",
                similarity, len(contours))
    return result, similarity, len(contours)


def compute_similarity(img1: Image.Image, img2: Image.Image) -> float:
    """Quick similarity score between two PIL images (0.0–1.0)."""
    cv1 = cv2.cvtColor(np.array(img1.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv1, cv2_img = _ensure_same_size(cv1, cv2_img)

    gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

    score = ssim(gray1, gray2)
    return float(max(0.0, min(1.0, score)))
