from __future__ import annotations

"""AI-powered semantic PDF comparison via Groq (OpenAI-compatible)."""

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
You are a deterministic PDF comparison engine.

Rules:
- Ignore logos, watermarks, headers, footers, branding images
- Compare ONLY:
  1. Text content
  2. Meaningful images (charts, tables, diagrams)
- Do NOT hallucinate
- Output MUST be valid JSON ONLY
- Do not include explanations, markdown, or extra text
"""

USER_PROMPT = """
Compare the following PDFs.

ORIGINAL TEXT:
{text1}

REVISED TEXT:
{text2}

IMAGE DIFFERENCES:
{image_summary}

Return STRICT JSON in this EXACT schema:

{{
  "summary": {{
    "overall_change": "NONE | MINOR | MAJOR",
    "confidence": 0.0
  }},
  "text_changes": [
    {{
      "type": "ADDED | REMOVED | MODIFIED",
      "page": number,
      "original": "...",
      "revised": "..."
    }}
  ],
  "image_changes": [
    {{
      "page": number,
      "description": "...",
      "impact": "LOW | MEDIUM | HIGH"
    }}
  ]
}}
"""


def _safe_json_parse(raw: str) -> Dict[str, Any]:
    """Safely extract and parse JSON from LLM output."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw.replace("json", "", 1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Groq returned malformed JSON:\n{raw}") from exc


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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    text1=text1[:12000],
                    text2=text2[:12000],
                    image_summary=json.dumps(image_summary),
                ),
            },
        ],
    )

    content = response.choices[0].message.content.strip()
    return _safe_json_parse(content)
