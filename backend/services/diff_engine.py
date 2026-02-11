from __future__ import annotations

"""Text diff engine for PDF page comparisons."""

import difflib
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def text_diff(texts1: List[str], texts2: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Compute per-page text differences between two lists of page texts.

    Returns:
        Mapping of page key (e.g. "page_0") to list of changes.
    """
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
            changes[f"page_{page_index}"] = page_changes

    logger.info("Computed text diff for %d pages", len(changes))
    return changes


def summarize_changes(
    per_page_changes: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Flatten per-page text diff into a simple list of change summaries."""
    summary: List[Dict[str, Any]] = []
    for page_key, entries in per_page_changes.items():
        if not page_key.startswith("page_"):
            continue
        try:
            page_index = int(page_key.split("_", 1)[1])
        except (IndexError, ValueError):
            page_index = 0
        for entry in entries:
            text_excerpt = entry.get("revised") or entry.get("original") or ""
            summary.append(
                {
                    "page": page_index + 1,
                    "type": entry.get("type", "change"),
                    "text": text_excerpt[:200],
                }
            )
    return summary
