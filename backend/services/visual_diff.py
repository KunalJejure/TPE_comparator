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


def _ensure_same_size(img1: np.ndarray, img2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Resize img2 to match img1's dimensions if they differ."""
    if img1.shape[:2] != img2.shape[:2]:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]),
                          interpolation=cv2.INTER_LANCZOS4)
    return img1, img2


def _compute_diff_regions(gray1: np.ndarray, gray2: np.ndarray,
                          threshold: int = 25,
                          mask_header_footer: bool = True,
                          sensitivity: str = "medium",
                          special_bboxes: List[List[float]] = None):
    """Use SSIM to find changed regions and return (score, contours).

    Steps:
        1. Optionally mask header/footer regions (top/bottom 8%).
        2. Mask special regions (e.g. date/time stamps).
        3. Apply light Gaussian pre-blur to suppress anti-aliasing noise.
        4. Compute SSIM with a full diff map.
        5. Threshold the diff map to isolate changed pixels.
        6. Use morphological ops to group nearby changed pixels into regions.
        7. Extract contours of those regions.

    Args:
        sensitivity: "low" (draft, threshold=40), "medium" (default, 25),
                     "high" (pixel-perfect, 15).
        mask_header_footer: If True, mask top/bottom 8% of the page to
                            ignore page numbers and running headers.
    """
    # ── Adaptive threshold based on sensitivity ──
    # Low = 40 (standard), Medium = 8 (highly sensitive), High = 3 (extreme/pixel-level)
    _THRESHOLDS = {"low": 40, "medium": 8, "high": 3}
    threshold = _THRESHOLDS.get(sensitivity, threshold)

    h, w = gray1.shape[:2]

    # ── Header/footer masking (Step 1) ──
    # Mask top/bottom 8% of page to ignore page numbers, running
    # headers, date stamps, and other repeated boilerplate.
    header_footer_margin = 0
    if mask_header_footer:
        header_footer_margin = int(h * 0.08)

    # ── Gaussian pre-blur (Step 3) ──
    # Reduced blur to preserve tiny detail changes (0.1% changes)
    gray1_proc = gray1.copy()
    gray2_proc = gray2.copy()

    # Apply header/footer mask — set to a neutral 128 (gray) to ignore in SSIM
    if header_footer_margin > 0:
        gray1_proc[:header_footer_margin, :] = gray2_proc[:header_footer_margin, :] = 128
        gray1_proc[h - header_footer_margin:, :] = gray2_proc[h - header_footer_margin:, :] = 128

    # Mask special regions (date, time, etc.)
    if special_bboxes:
        for bbox in special_bboxes:
            # bbox is [x0, y0, x1, y1]
            # Use a larger buffer (6px) to catch text anti-aliasing artifacts
            x0 = max(0, int(bbox[0]) - 6)
            y0 = max(0, int(bbox[1]) - 6)
            x1 = min(w, int(bbox[2]) + 6)
            y1 = min(h, int(bbox[3]) + 6)
            if x1 > x0 and y1 > y0:
                gray1_proc[y0:y1, x0:x1] = gray2_proc[y0:y1, x0:x1] = 128

    gray1_proc = cv2.GaussianBlur(gray1_proc, (3, 3), 0.2)
    gray2_proc = cv2.GaussianBlur(gray2_proc, (3, 3), 0.2)

    score, diff_map = ssim(gray1_proc, gray2_proc, full=True)

    # Invert so changed areas are bright (255)
    diff_uint8 = ((1.0 - diff_map) * 255).astype("uint8")

    # Zero out header/footer in the diff map so no contours are detected there
    if header_footer_margin > 0:
        diff_uint8[:header_footer_margin, :] = 0
        diff_uint8[h - header_footer_margin:, :] = 0

    # Zero out special regions in the diff map too
    if special_bboxes:
        for bbox in special_bboxes:
            # bbox is [x0, y0, x1, y1]
            x0 = max(0, int(bbox[0]) - 6)
            y0 = max(0, int(bbox[1]) - 6)
            x1 = min(w, int(bbox[2]) + 6)
            y1 = min(h, int(bbox[3]) + 6)
            if x1 > x0 and y1 > y0:
                diff_uint8[y0:y1, x0:x1] = 0

    # Threshold — only significant changes
    _, binary = cv2.threshold(diff_uint8, threshold, 255, cv2.THRESH_BINARY)

    # Morphological closing + dilation to group nearby change-pixels.
    # Reduced kernel sizes to avoid merging tiny distinct changes.
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close,
                               iterations=1)

    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(closed, kernel_dilate, iterations=1)

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
    
    If an ROI intersects one of the *special_bboxes* (e.g. date/time), 
    it is IGNORED (not drawn) per user request to "ignore overlays".
    
    Returns:
        (canvas, drawn_count): Updated image and number of regions actually highlighted.
    """
    h, w = canvas.shape[:2]
    rects_to_draw = []
    drawn_count = 0

    for cnt in contours:
        rx, ry, bw, bh = cv2.boundingRect(cnt)
        # Apply padding
        x1 = max(0, rx - padding)
        y1 = max(0, ry - padding)
        x2 = min(w, rx + bw + padding)
        y2 = min(h, ry + bh + padding)
        
        # Check overlap with special_bboxes (e.g. date/time regions)
        is_special = False
        if special_bboxes:
            for s_bbox in special_bboxes:
                # s_bbox is [sx0, sy0, sx1, sy1]
                # Inflate s_bbox by 8px buffer for robust intersection
                sx0, sy0, sx1, sy1 = s_bbox[0] - 8, s_bbox[1] - 8, s_bbox[2] + 8, s_bbox[3] + 8
                # Check for any intersection between [x1, y1, x2, y2] and inflated s_bbox
                if not (x2 < sx0 or x1 > sx1 or y2 < sy0 or y1 > sy1):
                    is_special = True
                    break
        
        if is_special:
            # Skip drawing entirely for "ignored" regions
            continue
        
        drawn_count += 1
        rects_to_draw.append(((x1, y1, x2, y2), border_colour, fill_colour))

    if not rects_to_draw:
        return canvas, 0

    # 1 – paint fills on a separate layer
    highlight = canvas.copy()
    for (box, b_col, f_col) in rects_to_draw:
        cv2.rectangle(highlight, (box[0], box[1]), (box[2], box[3]), f_col, -1)

    # 2 – alpha blend the fills layer onto the canvas
    cv2.addWeighted(highlight, alpha, canvas, 1.0 - alpha, 0, canvas)

    # 3 – draw crisp borders on top
    for (box, b_col, f_col) in rects_to_draw:
        cv2.rectangle(canvas, (box[0], box[1]), (box[2], box[3]), b_col, border)

    return canvas, drawn_count


# ── Public API ───────────────────────────────────────────────────────

def generate_diff_overlay(img1_pil: Image.Image,
                          img2_pil: Image.Image,
                          sensitivity: str = "medium",
                          mask_header_footer: bool = False,
                          date_time_regions1: List[Tuple[float, float, float, float]] = [],
                          date_time_regions2: List[Tuple[float, float, float, float]] = []):
    """Create diff overlay images for comparison views.

    Generates:
      1. A combined overlay (revised base + highlights)
      2. Original page with highlights
      3. Revised page with highlights

    Regions identified as Date/Time are completely ignored in the visual output.
    """
    cv1 = cv2.cvtColor(np.array(img1_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2_pil.convert("RGB")), cv2.COLOR_RGB2BGR)

    cv1, cv2_img = _ensure_same_size(cv1, cv2_img)

    gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

    # 1. Prepare Ignored Regions (Union of both pages)
    # If a region is date/time in either page, we ignore changes there.
    all_ignored = date_time_regions1 + date_time_regions2

    # 2. Find Changed Regions
    score, contours = _compute_diff_regions(
        gray1, gray2, 
        sensitivity=sensitivity, 
        mask_header_footer=mask_header_footer,
        special_bboxes=all_ignored
    )

    # 3. Combined Overlay (Revised base + RED boxes)
    overlay = cv2_img.copy()
    overlay, drawn_count = _draw_bounding_boxes(
        overlay, contours, 
        special_bboxes=all_ignored,
        border_colour=_RED_BORDER,
        fill_colour=_RED_FILL
    )

    # 4. Original Highlight (Original base + RED boxes)
    orig_highlight = cv1.copy()
    orig_highlight, _ = _draw_bounding_boxes(
        orig_highlight, contours, 
        special_bboxes=all_ignored,
        border_colour=_RED_BORDER,
        fill_colour=_RED_FILL
    )

    # 5. Revised Highlight (Revised base + RED boxes)
    rev_highlight = cv2_img.copy()
    rev_highlight, _ = _draw_bounding_boxes(
        rev_highlight, contours, 
        special_bboxes=all_ignored,
        border_colour=_RED_BORDER,
        fill_colour=_RED_FILL
    )

    similarity = float(max(0.0, min(1.0, score)))
    result_overlay = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    result_orig_hl = Image.fromarray(cv2.cvtColor(orig_highlight, cv2.COLOR_BGR2RGB))
    result_rev_hl = Image.fromarray(cv2.cvtColor(rev_highlight, cv2.COLOR_BGR2RGB))

    logger.info("Visual diff: similarity=%.4f  content_regions=%d  total_raw_regions=%d",
                similarity, drawn_count, len(contours))
    
    return result_overlay, result_orig_hl, result_rev_hl, similarity, drawn_count


def compute_similarity(img1: Image.Image, img2: Image.Image) -> float:
    """Quick similarity score between two PIL images (0.0–1.0)."""
    cv1 = cv2.cvtColor(np.array(img1.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv1, cv2_img = _ensure_same_size(cv1, cv2_img)

    gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)

    score = ssim(gray1, gray2)
    return float(max(0.0, min(1.0, score)))
