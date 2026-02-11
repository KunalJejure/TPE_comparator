import os
import json
from typing import Dict, Any, List

from openai import OpenAI
import dotenv

# Load .env file
dotenv.load_dotenv()

# 🔑 GROQ API KEY
# Make sure this exists in your environment or .env file:
# GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Please set it in environment variables or .env file."
    )

# ✅ OpenAI SDK pointing to Groq
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

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
    """
    Safely extract and parse JSON from LLM output.
    Handles ```json ... ``` and stray text.
    """
    raw = raw.strip()

    # Remove Markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw.replace("json", "", 1).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Groq returned malformed JSON:\n{raw}"
        ) from exc


def ai_compare(
    text1: str,
    text2: str,
    image_summary: List[Dict[str, Any]],
) -> Dict[str, Any]:

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # ✅ ACTIVE GROQ MODEL
        temperature=0,  # 🔒 deterministic
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    text1=text1[:12000],  # safety trim
                    text2=text2[:12000],
                    image_summary=json.dumps(image_summary),
                ),
            },
        ],
    )

    content = response.choices[0].message.content.strip()
    return _safe_json_parse(content)
