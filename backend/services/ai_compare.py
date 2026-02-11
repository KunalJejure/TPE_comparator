from __future__ import annotations

"""AI-powered semantic PDF comparison via Groq (OpenAI-compatible).

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
- Assign image change impact based on visual significance:
  LOW  = minor cosmetic (colour shade, alignment tweak)
  MEDIUM = noticeable UI change (new element, removed section)
  HIGH = major layout or data change (redesigned chart, different data)
- Output MUST be valid JSON ONLY — no markdown, no explanations, no filler
- Do NOT hallucinate or invent changes that don't exist
"""

USER_PROMPT = """
Compare the following two PDF document revisions page by page.

ORIGINAL TEXT (per page, separated by ===PAGE===):
{text1}

REVISED TEXT (per page, separated by ===PAGE===):
{text2}

IMAGE DIFFERENCES (computed via pixel-level visual diff):
{image_summary}

The image differences above give similarity scores per page. A score below
0.98 means the page contains visual changes. Focus your image analysis on
those pages.

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


def _format_texts_by_page(texts: List[str]) -> str:
    """Format page texts with clear page separators for the LLM."""
    parts = []
    for i, text in enumerate(texts):
        parts.append(f"--- PAGE {i + 1} ---\n{text.strip()}")
    return "\n===PAGE===\n".join(parts)


def ai_compare(
    text1: str,
    text2: str,
    image_summary: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run AI semantic comparison via Groq.

    Raises RuntimeError if GROQ_API_KEY is not set.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in environment.")

    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    # Truncate to stay within context limits
    max_chars = 12000
    t1 = text1[:max_chars]
    t2 = text2[:max_chars]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    text1=t1,
                    text2=t2,
                    image_summary=json.dumps(image_summary, indent=2),
                ),
            },
        ],
    )

    content = response.choices[0].message.content.strip()
    result = _safe_json_parse(content)

    # Validate and normalise the result structure
    if "summary" not in result:
        result["summary"] = {
            "overall_change": "UNKNOWN",
            "confidence": 0.0,
            "change_description": "Unable to determine",
        }
    if "text_changes" not in result:
        result["text_changes"] = []
    if "image_changes" not in result:
        result["image_changes"] = []

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
        "AI comparison complete: %s, confidence=%.2f, %d text changes, %d image changes",
        result["summary"].get("overall_change"),
        result["summary"].get("confidence", 0),
        len(result["text_changes"]),
        len(result["image_changes"]),
    )

    return result
