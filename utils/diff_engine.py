from __future__ import annotations

"""Text and visual diff engines for PDF pages."""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2  # type: ignore[import]
import numpy as np
from PIL import Image


logger = logging.getLogger(__name__)


def text_diff(texts1: List[str], texts2: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Compute per-page text differences between two lists of page texts.

    Each change entry is a dict containing:
        - type: 'replace' | 'insert' | 'delete'
        - original: excerpt from original text (may be empty)
        - revised: excerpt from revised text (may be empty)

    Args:
        texts1: Page texts from the original PDF.
        texts2: Page texts from the revised PDF.

    Returns:
        Mapping of page key (e.g. "page_0") to list of changes.
    """
    import difflib

    num_pages = max(len(texts1), len(texts2))
    changes: Dict[str, List[Dict[str, Any]]] = {}

    for page_index in range(num_pages):
        original = texts1[page_index] if page_index < len(texts1) else ""
        revised = texts2[page_index] if page_index < len(texts2) else ""

        matcher = difflib.SequenceMatcher(None, original, revised)
        page_changes: List[Dict[str, Any]] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            page_changes.append(
                {
                    "type": tag,
                    "original": original[i1:i2][:200],
                    "revised": revised[j1:j2][:200],
                }
            )

        if page_changes:
            key = f"page_{page_index}"
            changes[key] = page_changes

    # Optionally enrich with pdf-diff CLI if available
    try:
        pdf_diff_summary = _run_pdf_diff_if_available()
        if pdf_diff_summary is not None:
            changes.setdefault("pdf_diff_cli", []).append(pdf_diff_summary)
    except Exception:  # pragma: no cover - best-effort enrichment
        logger.exception("pdf-diff CLI integration failed; continuing without it.")

    logger.info("Computed text diff for %d pages", len(changes))
    return changes


def summarize_changes(
    per_page_changes: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Flatten per-page text diff into a simple list of change summaries.

    This is used to produce a top-level JSON `changes` array such as:

        [
          {"page": 1, "type": "insert", "text": "New bug fix"}
        ]
    """
    summary: List[Dict[str, Any]] = []
    for page_key, entries in per_page_changes.items():
        if not page_key.startswith("page_"):
            # Skip any non-page metadata, e.g. "pdf_diff_cli"
            continue
        try:
            page_index = int(page_key.split("_", 1)[1])
        except (IndexError, ValueError):
            page_index = 0
        for entry in entries:
            text_excerpt = entry.get("revised") or entry.get("original") or ""
            summary.append(
                {
                    "page": page_index + 1,  # 1-based for UI
                    "type": entry.get("type", "change"),
                    "text": text_excerpt[:200],
                }
            )
    return summary


def visual_diff(img1: Image.Image, img2: Image.Image) -> Tuple[Image.Image, float]:
    """Compute visual differences between two page images.

    Args:
        img1: Original page image.
        img2: Revised page image.

    Returns:
        Tuple of (highlighted overlay image, similarity score in [0, 1]).
    """
    # Convert to OpenCV BGR images.
    cv1 = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2BGR)
    cv2_img = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2BGR)

    # Resize second image to match first image dimensions.
    height, width = cv1.shape[:2]
    cv2_img = cv2.resize(cv2_img, (width, height))

    # Absolute difference between images.
    diff = cv2.absdiff(cv1, cv2_img)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    # Threshold to get changed pixels.
    _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)

    # Similarity: portion of unchanged pixels.
    changed_pixels = int(np.count_nonzero(thresh))
    total_pixels = height * width
    similarity = 1.0 - (changed_pixels / float(total_pixels)) if total_pixels else 0.0

    # Highlight changes with contours on top of original.
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    overlay = cv1.copy()
    cv2.drawContours(overlay, contours, -1, (0, 0, 255), 2)

    result_image = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))

    logger.info("Visual diff similarity: %.4f", similarity)
    return result_image, float(max(0.0, min(1.0, similarity)))


def _run_pdf_diff_if_available() -> Dict[str, Any] | None:
    """Optionally invoke `pdf-diff` CLI if available on PATH.

    This is a best-effort enrichment; errors are swallowed by the caller.
    """
    if shutil.which("pdf-diff") is None:
        return None

    # For a proper integration we would need actual file paths; in this POC we
    # simply report that the CLI is present to surface in the report/JSON.
    info: Dict[str, Any] = {"tool": "pdf-diff", "status": "available"}
    try:
        # `pdf-diff --help` as a cheap liveness check
        completed = subprocess.run(
            ["pdf-diff", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        info["returncode"] = completed.returncode
        info["output_snippet"] = completed.stdout[:500]
    except Exception as exc:  # pragma: no cover - best-effort
        logger.debug("pdf-diff CLI probing failed: %s", exc)
    logger.debug("pdf-diff CLI info: %s", json.dumps(info)[:300])
    return info

