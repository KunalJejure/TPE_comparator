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
_YELLOW_BORDER = (0, 200, 255)    # amber/yellow border
_YELLOW_FILL = (180, 240, 255)    # light yellow fill

# Overlay fill opacity (0.0 = invisible, 1.0 = opaque)
_FILL_ALPHA = 0.18
_BORDER_THICKNESS = 2
_PADDING = 6  # px around each changed region


def _ensure_same_size(img1: np.ndarray, img2: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """Resize img2 to match img1's dimensions if they differ.
    Returns (img1, img2, scale_x, scale_y) where scale factors are for img2.
    """
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]

    if (h1, w1) != (h2, w2):
        logger.warning("Image size mismatch: img1=%s, img2=%s. Resizing img2 to match img1.", (h1, w1), (h2, w2))
        img2 = cv2.resize(img2, (w1, h1), interpolation=cv2.INTER_LANCZOS4)
        return img1, img2, w1 / float(w2), h1 / float(h2)

    return img1, img2, 1.0, 1.0


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
                         border: int = _BORDER_THICKNESS,
                         special_bboxes: List[List[float]] = None) -> Tuple[np.ndarray, int]:
    """Draw semi-transparent highlighted bounding boxes on *canvas*.

    If *special_bboxes* is provided, any ROI that intersects one of them
    is drawn in YELLOW instead of the default *border_colour*.
    
    Returns:
        (canvas, non_special_count)
    """
    h, w = canvas.shape[:2]
    rects_with_colors = []
    special_count = 0

    for cnt in contours:
        rx, ry, bw, bh = cv2.boundingRect(cnt)
        # Apply padding
        x1 = max(0, rx - padding)
        y1 = max(0, ry - padding)
        x2 = min(w, rx + bw + padding)
        y2 = min(h, ry + bh + padding)
        
        # Check overlap with special_bboxes (e.g. date/time regions)
        # We add a slight epsilon (2px) to the bboxes to make the intersection check robust
        is_special = False
        if special_bboxes:
            eps = 5.0 # Increased epsilon for more robust matching
            for s_bbox in special_bboxes:
                # sx0, sy0, sx1, sy1 = s_bbox
                # Standard AABB intersection
                if not (x2 + eps < s_bbox[0] or x1 - eps > s_bbox[2] or 
                        y2 + eps < s_bbox[1] or y1 - eps > s_bbox[3]):
                    is_special = True
                    logger.debug("Contour [%d,%d,%d,%d] MATCHED special bbox %s (eps=%.1f)", 
                                 x1, y1, x2, y2, s_bbox, eps)
                    break
            if not is_special:
                logger.debug("Contour [%d,%d,%d,%d] did NOT match any of %d special bboxes", 
                             x1, y1, x2, y2, len(special_bboxes))
        
        if is_special:
            special_count += 1
            b_col = _YELLOW_BORDER
            f_col = _YELLOW_FILL
        else:
            b_col = border_colour
            f_col = fill_colour
            
        rects_with_colors.append(((x1, y1, x2, y2), b_col, f_col))

    if not rects_with_colors:
        return canvas, 0

    # 1 – paint fills on a separate layer
    highlight = canvas.copy()
    for (box, b_col, f_col) in rects_with_colors:
        cv2.rectangle(highlight, (box[0], box[1]), (box[2], box[3]), f_col, -1)

    # 2 – alpha blend the fills layer onto the canvas
    cv2.addWeighted(highlight, alpha, canvas, 1.0 - alpha, 0, canvas)

    # 3 – draw crisp borders on top
    for (box, b_col, f_col) in rects_with_colors:
        cv2.rectangle(canvas, (box[0], box[1]), (box[2], box[3]), b_col, border)

    return canvas, len(contours) - special_count


# ── Public API ───────────────────────────────────────────────────────

def generate_diff_overlay(img1: Image.Image, img2: Image.Image,
                          date_time_regions1: List[List[float]] = None,
                          date_time_regions2: List[List[float]] = None):
    """Create diff overlay images for comparison views.

    Generates:
      1. A combined overlay (revised base + mixed red/yellow highlights)
      2. Original page with mixed red/yellow highlights
      3. Revised page with mixed red/yellow highlights

    Args:
        img1: Original page (PIL).
        img2: Revised page (PIL).
        date_time_regions1: Date/time bboxes for original page (pixels).
        date_time_regions2: Date/time bboxes for revised page (pixels).

    Returns:
        Tuple of (overlay_pil, orig_highlight_pil, rev_highlight_pil, similarity, region_count).
    """
    cv1 = cv2.cvtColor(np.array(img1.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2.convert("RGB")), cv2.COLOR_RGB2BGR)

    cv1, cv2_img, sx2, sy2 = _ensure_same_size(cv1, cv2_img)

    # Adjust date_time_regions2 if img2 was resized
    if (sx2 != 1.0 or sy2 != 1.0) and date_time_regions2:
        logger.info("Scaling date_time_regions2 by (%.3f, %.3f) due to image resize", sx2, sy2)
        date_time_regions2 = [
            [b[0] * sx2, b[1] * sy2, b[2] * sx2, b[3] * sy2]
            for b in date_time_regions2
        ]

    gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

    score, contours = _compute_diff_regions(gray1, gray2)

    # 1. Combined Overlay (Revised base + mixed RED/YELLOW boxes)
    overlay = cv2_img.copy()
    overlay, non_special_count = _draw_bounding_boxes(overlay, contours,
                                                      border_colour=_RED_BORDER,
                                                      fill_colour=_RED_FILL,
                                                      special_bboxes=date_time_regions2)

    # 2. Original Highlight (Original base + mixed RED/YELLOW boxes)
    orig_highlight = cv1.copy()
    orig_highlight, _ = _draw_bounding_boxes(orig_highlight, contours,
                                             border_colour=_RED_BORDER,
                                             fill_colour=_RED_FILL,
                                             special_bboxes=date_time_regions1)

    # 3. Revised Highlight (Revised base + mixed RED/YELLOW boxes)
    rev_highlight = cv2_img.copy()
    rev_highlight, _ = _draw_bounding_boxes(rev_highlight, contours,
                                            border_colour=_RED_BORDER,
                                            fill_colour=_RED_FILL,
                                            special_bboxes=date_time_regions2)

    similarity = float(max(0.0, min(1.0, score)))
    result_overlay = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    result_orig_hl = Image.fromarray(cv2.cvtColor(orig_highlight, cv2.COLOR_BGR2RGB))
    result_rev_hl = Image.fromarray(cv2.cvtColor(rev_highlight, cv2.COLOR_BGR2RGB))

    logger.info("Visual diff: similarity=%.4f  regions=%d (neglected=%d)",
                similarity, len(contours), len(contours) - non_special_count)
    return result_overlay, result_orig_hl, result_rev_hl, similarity, non_special_count


def compute_similarity(img1: Image.Image, img2: Image.Image) -> float:
    """Quick similarity score between two PIL images (0.0–1.0)."""
    cv1 = cv2.cvtColor(np.array(img1.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv1, cv2_img = _ensure_same_size(cv1, cv2_img)

    gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

    score = ssim(gray1, gray2)
    return float(max(0.0, min(1.0, score)))
