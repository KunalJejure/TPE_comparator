from __future__ import annotations

"""SSIM-based visual diff with highlighted overlay."""

import logging

import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)


def generate_visual_diff(img1_bgr, img2_bgr):
    """Generate a visual diff overlay between two BGR numpy images.

    Returns:
        Tuple of (overlay_bgr, similarity_percent).
    """
    if img1_bgr.shape != img2_bgr.shape:
        img2_bgr = cv2.resize(img2_bgr, (img1_bgr.shape[1], img1_bgr.shape[0]))

    gray1 = cv2.cvtColor(img1_bgr, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2_bgr, cv2.COLOR_BGR2GRAY)

    score, diff = ssim(gray1, gray2, full=True)
    diff = (1 - diff) * 255
    diff = diff.astype("uint8")

    thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)[1]

    red = np.zeros_like(img1_bgr)
    green = np.zeros_like(img1_bgr)
    red[:, :, 2] = thresh
    green[:, :, 1] = thresh

    overlay = cv2.addWeighted(img2_bgr, 0.7, red, 0.5, 0)
    overlay = cv2.addWeighted(overlay, 1, green, 0.5, 0)

    similarity = round(score * 100, 2)
    return overlay, similarity


def visual_diff(img1: Image.Image, img2: Image.Image):
    """High-level visual diff accepting PIL Images.

    Returns:
        Tuple of (result_pil_image, similarity_0_to_1).
    """
    cv1 = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2BGR)

    height, width = cv1.shape[:2]
    cv2_img = cv2.resize(cv2_img, (width, height))

    diff = cv2.absdiff(cv1, cv2_img)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)

    changed_pixels = int(np.count_nonzero(thresh))
    total_pixels = height * width
    similarity = 1.0 - (changed_pixels / float(total_pixels)) if total_pixels else 0.0

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    overlay = cv1.copy()
    cv2.drawContours(overlay, contours, -1, (0, 0, 255), 2)

    result_image = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    logger.info("Visual diff similarity: %.4f", similarity)
    return result_image, float(max(0.0, min(1.0, similarity)))
