from __future__ import annotations

"""AI-powered semantic PDF comparison via Groq (OpenAI-compatible).

Step 3 accuracy improvement: processes *changed pages only* with
pre-computed text diffs so the LLM focuses on validating and classifying
real changes instead of rediscovering them from raw text.

Provides detailed text and image change analysis using Groq LLM.
"""

import json
import logging
import os
from typing import Any, Dict, List

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Prompts ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a deterministic PDF comparison engine specialised in detecting
differences between two document revisions.

Rules:
- Ignore logos, watermarks, headers, footers, branding images, page numbers
- Compare ONLY:
  1. Text content (paragraphs, headings, bullets, tables)
  2. Meaningful images (charts, tables, diagrams, UI screenshots)
  3. Layout changes that affect readability
- Each change MUST include the page number it occurs on
- For text changes: provide the EXACT original and revised text snippets
- For image changes: describe what changed visually in detail (e.g.
  "Button colour changed from blue to green", "Chart axis scale updated",
  "New image added showing dashboard layout")
- Assign text change significance:
  LOW  = whitespace, punctuation, minor wording tweak
  MEDIUM = sentence rewritten, number/value changed
  HIGH = paragraph added/removed, meaning altered
- Assign image change impact based on visual significance:
  LOW  = minor cosmetic (colour shade, alignment tweak)
  MEDIUM = noticeable UI change (new element, removed section)
  HIGH = major layout or data change (redesigned chart, different data)
- Output MUST be valid JSON ONLY — no markdown, no explanations, no filler
- Do NOT hallucinate or invent changes that don't exist
- If the pre-computed diff shows a change, validate and classify it
- If the diff shows no change but visual diff detects one, it is likely
  an image/formatting change — describe it as an image_change
"""

BATCH_PROMPT = """
Analyse the following CHANGED PAGES from a PDF comparison.
For each page I provide:
  1. The page number
  2. Pre-computed text diff lines (DELETE/INSERT/REPLACE operations)
  3. Visual similarity score (1.0 = identical, lower = more different)
  4. Original and revised text for context

{page_blocks}

Return STRICT JSON in this EXACT schema (no extra keys, no markdown):

{{
  "summary": {{
    "overall_change": "NONE | MINOR | MAJOR",
    "confidence": <float 0.0-1.0>,
    "change_description": "<one sentence describing the overall change>"
  }},
  "text_changes": [
    {{
      "type": "ADDED | REMOVED | MODIFIED",
      "page": <integer page number>,
      "section": "<heading or area where change occurs>",
      "original": "<exact original text, empty if ADDED>",
      "revised": "<exact revised text, empty if REMOVED>",
      "significance": "LOW | MEDIUM | HIGH"
    }}
  ],
  "image_changes": [
    {{
      "page": <integer page number>,
      "description": "<detailed description of what changed visually>",
      "impact": "LOW | MEDIUM | HIGH",
      "element_type": "<type of element: chart | table | diagram | screenshot | icon | photo>"
    }}
  ]
}}
"""


# ── Helpers ──────────────────────────────────────────────────────────

def _safe_json_parse(raw: str) -> Dict[str, Any]:
    """Safely extract and parse JSON from LLM output."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Groq returned malformed JSON:\n%s", raw[:500])
        raise RuntimeError(f"Groq returned malformed JSON:\n{raw[:300]}") from exc


def _summarize_line_diff(line_diff: List[Dict[str, Any]], max_lines: int = 30) -> str:
    """Condense a line-level diff into a compact summary for the LLM.

    Only includes changed lines (delete/insert/replace), skips equal lines.
    Truncates to *max_lines* to stay within token budget.
    """
    summary_lines: List[str] = []
    for entry in line_diff:
        if entry["type"] == "equal":
            continue
        left = entry.get("left_content", "").strip()
        right = entry.get("right_content", "").strip()
        if entry["type"] == "delete":
            summary_lines.append(f"  DELETE L{entry.get('left_line_no', '?')}: {left[:120]}")
        elif entry["type"] == "insert":
            summary_lines.append(f"  INSERT R{entry.get('right_line_no', '?')}: {right[:120]}")
        elif entry["type"] == "replace":
            summary_lines.append(
                f"  REPLACE L{entry.get('left_line_no', '?')}: \"{left[:80]}\" → \"{right[:80]}\""
            )
        if len(summary_lines) >= max_lines:
            summary_lines.append(f"  ... ({len(line_diff)} total diff lines, truncated)")
            break
    return "\n".join(summary_lines) if summary_lines else "  (no text differences detected)"


def _build_page_block(page_info: Dict[str, Any]) -> str:
    """Build a structured text block for one changed page."""
    page_num = page_info["page"]
    similarity = page_info.get("image_similarity", 1.0)
    diff_summary = page_info.get("diff_summary", "(no diff available)")
    original_text = page_info.get("original_text", "")[:2000]
    revised_text = page_info.get("revised_text", "")[:2000]

    return f"""
═══ PAGE {page_num} ═══
Visual similarity: {similarity:.4f} {'(visual changes detected)' if similarity < 0.98 else '(visually similar)'}
Text diff:
{diff_summary}

Original text (first 2000 chars):
{original_text}

Revised text (first 2000 chars):
{revised_text}
"""


# ── Public API ───────────────────────────────────────────────────────

def ai_compare(
    changed_pages: List[Dict[str, Any]],
    image_summary: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run AI semantic comparison via Groq on CHANGED PAGES ONLY.

    Args:
        changed_pages: List of dicts, each with keys:
            page, original_text, revised_text, diff_summary, image_similarity
        image_summary: Per-page visual diff summary (all pages).

    Raises RuntimeError if GROQ_API_KEY is not set.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in environment.")

    # If no pages changed, return immediately
    if not changed_pages:
        return {
            "summary": {
                "overall_change": "NONE",
                "confidence": 1.0,
                "change_description": "No differences detected between the documents.",
            },
            "text_changes": [],
            "image_changes": [],
        }

    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    # ── Build page blocks for changed pages ──
    # Process in batches of 5 pages to stay within context limits.
    # Each page gets ~4000 chars (2000 original + 2000 revised + diff summary).
    BATCH_SIZE = 5
    all_text_changes: List[Dict[str, Any]] = []
    all_image_changes: List[Dict[str, Any]] = []
    overall_change = "NONE"
    total_confidence = 0.0
    descriptions: List[str] = []
    batch_count = 0

    for i in range(0, len(changed_pages), BATCH_SIZE):
        batch = changed_pages[i : i + BATCH_SIZE]
        page_blocks = "\n".join(_build_page_block(p) for p in batch)

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": BATCH_PROMPT.format(page_blocks=page_blocks),
                    },
                ],
            )

            content = response.choices[0].message.content.strip()
            batch_result = _safe_json_parse(content)
            batch_count += 1

            # Accumulate results
            all_text_changes.extend(batch_result.get("text_changes", []))
            all_image_changes.extend(batch_result.get("image_changes", []))

            batch_summary = batch_result.get("summary", {})
            batch_change = batch_summary.get("overall_change", "NONE")
            if batch_change == "MAJOR":
                overall_change = "MAJOR"
            elif batch_change == "MINOR" and overall_change != "MAJOR":
                overall_change = "MINOR"

            total_confidence += batch_summary.get("confidence", 0.0)
            desc = batch_summary.get("change_description", "")
            if desc:
                descriptions.append(desc)

        except Exception as exc:
            logger.warning(
                "AI batch comparison failed for pages %s: %s",
                [p["page"] for p in batch],
                exc,
            )
            # Continue with remaining batches

    # ── Aggregate results ──
    avg_confidence = total_confidence / max(batch_count, 1)

    result: Dict[str, Any] = {
        "summary": {
            "overall_change": overall_change,
            "confidence": round(avg_confidence, 3),
            "change_description": "; ".join(descriptions) if descriptions else "Unable to determine",
        },
        "text_changes": all_text_changes,
        "image_changes": all_image_changes,
    }

    # Ensure every text change has the required fields
    for change in result["text_changes"]:
        change.setdefault("type", "MODIFIED")
        change.setdefault("page", 1)
        change.setdefault("section", "")
        change.setdefault("original", "")
        change.setdefault("revised", "")
        change.setdefault("significance", "MEDIUM")

    # Ensure every image change has the required fields
    for change in result["image_changes"]:
        change.setdefault("page", 1)
        change.setdefault("description", "Visual change detected")
        change.setdefault("impact", "MEDIUM")
        change.setdefault("element_type", "unknown")

    logger.info(
        "AI comparison complete: %s, confidence=%.2f, %d text changes, "
        "%d image changes (%d batches, %d changed pages)",
        result["summary"].get("overall_change"),
        result["summary"].get("confidence", 0),
        len(result["text_changes"]),
        len(result["image_changes"]),
        batch_count,
        len(changed_pages),
    )

    return result
