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
                          threshold: int = 25,
                          mask_header_footer: bool = True,
                          sensitivity: str = "medium"):
    """Use SSIM to find changed regions and return (score, contours).

    Steps:
        1. Optionally mask header/footer regions (top/bottom 8%).
        2. Apply light Gaussian pre-blur to suppress anti-aliasing noise.
        3. Compute SSIM with a full diff map.
        4. Threshold the diff map to isolate changed pixels.
        5. Use morphological ops to group nearby changed pixels into regions.
        6. Extract contours of those regions.

    Args:
        sensitivity: "low" (draft, threshold=40), "medium" (default, 25),
                     "high" (pixel-perfect, 15).
        mask_header_footer: If True, mask top/bottom 8% of the page to
                            ignore page numbers and running headers.
    """
    # ── Adaptive threshold based on sensitivity ──
    _THRESHOLDS = {"low": 40, "medium": 25, "high": 15}
    threshold = _THRESHOLDS.get(sensitivity, threshold)

    h, w = gray1.shape[:2]

    # ── Header/footer masking (Step 2) ──
    # Mask top/bottom 8% of page to ignore page numbers, running
    # headers, date stamps, and other repeated boilerplate.
    header_footer_margin = 0
    if mask_header_footer:
        header_footer_margin = int(h * 0.08)

    # ── Gaussian pre-blur (Step 5) ──
    # Suppress sub-pixel anti-aliasing and font rendering differences
    # that produce false-positive diff regions.
    gray1_proc = cv2.GaussianBlur(gray1, (3, 3), 0.5)
    gray2_proc = cv2.GaussianBlur(gray2, (3, 3), 0.5)

    # Apply header/footer mask — zero out margins so SSIM ignores them
    if header_footer_margin > 0:
        gray1_proc[:header_footer_margin, :] = gray2_proc[:header_footer_margin, :] = 128
        gray1_proc[h - header_footer_margin:, :] = gray2_proc[h - header_footer_margin:, :] = 128

    score, diff_map = ssim(gray1_proc, gray2_proc, full=True)

    # Invert so changed areas are bright (255)
    diff_uint8 = ((1.0 - diff_map) * 255).astype("uint8")

    # Zero out header/footer in the diff map so no contours are detected there
    if header_footer_margin > 0:
        diff_uint8[:header_footer_margin, :] = 0
        diff_uint8[h - header_footer_margin:, :] = 0

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
    """Create diff overlay images for comparison views.

    Generates:
      1. A combined overlay (revised base + red highlights)
      2. Original page with red highlights
      3. Revised page with yellow highlights

    Args:
        img1: Original page (PIL).
        img2: Revised page (PIL).

    Returns:
        Tuple of (overlay_pil, orig_highlight_pil, rev_highlight_pil, similarity, region_count).
    """
    cv1 = cv2.cvtColor(np.array(img1.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2.convert("RGB")), cv2.COLOR_RGB2BGR)

    cv1, cv2_img = _ensure_same_size(cv1, cv2_img)

    gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

    score, contours = _compute_diff_regions(gray1, gray2)

    # 1. Combined Overlay (Revised base + RED boxes)
    overlay = cv2_img.copy()
    overlay = _draw_bounding_boxes(overlay, contours,
                                   border_colour=_RED_BORDER,
                                   fill_colour=_RED_FILL)

    # 2. Original Highlight (Original base + RED boxes)
    orig_highlight = cv1.copy()
    orig_highlight = _draw_bounding_boxes(orig_highlight, contours,
                                          border_colour=_RED_BORDER,
                                          fill_colour=_RED_FILL)

    # 3. Revised Highlight (Revised base + YELLOW boxes)
    # OpenCV uses BGR. Yellow is (0, 255, 255). We'll use a slightly softer yellow.
    YELLOW_BORDER = (0, 200, 255)
    YELLOW_FILL = (180, 240, 255)
    rev_highlight = cv2_img.copy()
    rev_highlight = _draw_bounding_boxes(rev_highlight, contours,
                                         border_colour=YELLOW_BORDER,
                                         fill_colour=YELLOW_FILL)

    similarity = float(max(0.0, min(1.0, score)))
    result_overlay = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    result_orig_hl = Image.fromarray(cv2.cvtColor(orig_highlight, cv2.COLOR_BGR2RGB))
    result_rev_hl = Image.fromarray(cv2.cvtColor(rev_highlight, cv2.COLOR_BGR2RGB))

    logger.info("Visual diff: similarity=%.4f  regions=%d",
                similarity, len(contours))
    return result_overlay, result_orig_hl, result_rev_hl, similarity, len(contours)


def compute_similarity(img1: Image.Image, img2: Image.Image) -> float:
    """Quick similarity score between two PIL images (0.0–1.0)."""
    cv1 = cv2.cvtColor(np.array(img1.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv1, cv2_img = _ensure_same_size(cv1, cv2_img)

    gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

    score = ssim(gray1, gray2)
    return float(max(0.0, min(1.0, score)))
