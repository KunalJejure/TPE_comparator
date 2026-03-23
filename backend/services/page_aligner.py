from __future__ import annotations

"""Smart page alignment using text-similarity-based dynamic programming.

Solves the problem where a page is inserted/removed in the revised PDF,
causing all subsequent pages to be misaligned.  For example:

    Original:  [P1, P2, P3_EnvDetail, P4, ...]
    Revised:   [P1, P2, P3_TOC(new!), P4_EnvDetail, P5, ...]

    Alignment:
      Orig P1  ↔  Rev P1   (matched)
      Orig P2  ↔  Rev P2   (matched)
        ---    ↔  Rev P3   (INSERTED — new Table of Contents)
      Orig P3  ↔  Rev P4   (matched — Environmental Detail)

Uses Needleman-Wunsch global alignment (dynamic programming) with
text similarity scores as the substitution matrix.
"""

import difflib
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Type alias for an alignment pair.
# (orig_page_idx, rev_page_idx) — either side can be None.
AlignmentPair = Tuple[Optional[int], Optional[int]]


def _text_similarity(text_a: str, text_b: str) -> float:
    """Compute text similarity between two strings (0.0–1.0).

    Uses difflib.SequenceMatcher.ratio() which is fast and gives a
    good approximation of how similar two texts are.
    """
    if not text_a and not text_b:
        return 1.0
    if not text_a or not text_b:
        return 0.0
    return difflib.SequenceMatcher(None, text_a, text_b).ratio()


def compute_similarity_matrix(
    texts_a: List[str], texts_b: List[str],
) -> List[List[float]]:
    """Compute NxM similarity matrix between all page pairs.

    Returns:
        matrix[i][j] = similarity between texts_a[i] and texts_b[j]
    """
    n, m = len(texts_a), len(texts_b)
    matrix = [[0.0] * m for _ in range(n)]

    for i in range(n):
        for j in range(m):
            matrix[i][j] = _text_similarity(texts_a[i], texts_b[j])

    return matrix


def align_pages(
    texts_a: List[str],
    texts_b: List[str],
    match_threshold: float = 0.3,
    gap_penalty: float = -0.1,
) -> List[AlignmentPair]:
    """Align pages from two PDFs using Needleman-Wunsch dynamic programming.

    Finds the optimal alignment between original pages and revised pages
    based on text similarity. Handles inserted, removed, and reordered pages.

    Args:
        texts_a: List of page texts from original PDF.
        texts_b: List of page texts from revised PDF.
        match_threshold: Minimum similarity to consider two pages a match.
            Below this, pages are treated as unrelated (gap preferred).
        gap_penalty: Cost of leaving a page unmatched (insertion/deletion).

    Returns:
        List of (orig_idx, rev_idx) pairs:
          - (i, j)    → Original page i matches Revised page j
          - (None, j)  → Revised page j is INSERTED (no match in original)
          - (i, None)  → Original page i is REMOVED (no match in revised)

        Indices are 0-based.
    """
    n = len(texts_a)
    m = len(texts_b)

    # Handle edge cases
    if n == 0 and m == 0:
        return []
    if n == 0:
        return [(None, j) for j in range(m)]
    if m == 0:
        return [(i, None) for i in range(n)]

    # ── Step 1: Compute similarity matrix ──
    sim = compute_similarity_matrix(texts_a, texts_b)

    # ── Step 2: Needleman-Wunsch DP ──
    # Score matrix: (n+1) x (m+1)
    # dp[i][j] = best alignment score for texts_a[:i] and texts_b[:j]
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]

    # Initialize: gap penalties for unmatched pages
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + gap_penalty
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + gap_penalty

    # Fill DP table
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            similarity = sim[i - 1][j - 1]

            # Match score: use similarity if above threshold, else penalize
            if similarity >= match_threshold:
                match_score = similarity
            else:
                match_score = similarity - 0.5  # penalize poor matches

            diagonal = dp[i - 1][j - 1] + match_score   # match/substitute
            up = dp[i - 1][j] + gap_penalty              # delete (orig only)
            left = dp[i][j - 1] + gap_penalty            # insert (rev only)

            dp[i][j] = max(diagonal, up, left)

    # ── Step 3: Traceback ──
    alignment: List[AlignmentPair] = []
    i, j = n, m

    while i > 0 or j > 0:
        if i > 0 and j > 0:
            similarity = sim[i - 1][j - 1]
            if similarity >= match_threshold:
                match_score = similarity
            else:
                match_score = similarity - 0.5

            if dp[i][j] == dp[i - 1][j - 1] + match_score:
                # Diagonal — pages are aligned
                if similarity >= match_threshold:
                    alignment.append((i - 1, j - 1))
                else:
                    # Below threshold: treat as separate insert + delete
                    alignment.append((None, j - 1))
                    alignment.append((i - 1, None))
                i -= 1
                j -= 1
                continue

        if i > 0 and dp[i][j] == dp[i - 1][j] + gap_penalty:
            # Up — original page has no match (removed)
            alignment.append((i - 1, None))
            i -= 1
        elif j > 0:
            # Left — revised page has no match (inserted)
            alignment.append((None, j - 1))
            j -= 1
        else:
            break  # safety

    alignment.reverse()

    # ── Logging ──
    matched = sum(1 for a, b in alignment if a is not None and b is not None)
    inserted = sum(1 for a, b in alignment if a is None)
    removed = sum(1 for a, b in alignment if b is None)
    logger.info(
        "Page alignment: %d matched, %d inserted, %d removed (orig=%d, rev=%d)",
        matched, inserted, removed, n, m,
    )

    for orig_idx, rev_idx in alignment:
        if orig_idx is not None and rev_idx is not None:
            logger.debug(
                "  Orig P%d ↔ Rev P%d  (sim=%.2f)",
                orig_idx + 1, rev_idx + 1, sim[orig_idx][rev_idx],
            )
        elif orig_idx is not None:
            logger.debug("  Orig P%d ↔ ---  (REMOVED)", orig_idx + 1)
        else:
            logger.debug("  --- ↔ Rev P%d  (INSERTED)", rev_idx + 1)

    return alignment
