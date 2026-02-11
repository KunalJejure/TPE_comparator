# app/services/visual_diff.py

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

def generate_visual_diff(img1, img2):
    # Ensure both images have the same dimensions (required by SSIM)
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    score, diff = ssim(gray1, gray2, full=True)
    diff = (1 - diff) * 255
    diff = diff.astype("uint8")

    thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)[1]

    red = np.zeros_like(img1)
    green = np.zeros_like(img1)

    red[:, :, 2] = thresh       # Red highlights
    green[:, :, 1] = thresh    # Green highlights

    overlay = cv2.addWeighted(img2, 0.7, red, 0.5, 0)
    overlay = cv2.addWeighted(overlay, 1, green, 0.5, 0)

    similarity = round(score * 100, 2)

    return overlay, similarity
