"""POST /api/chat — interactive AI chat about comparison results."""

import logging
import os
import json
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    context: Dict[str, Any]  # The comparison result data
    history: list = []        # Previous chat messages


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(req: ChatRequest):
    """Chat with AI about the PDF comparison results."""

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    # Build a concise context summary from the comparison data
    ctx = req.context
    total_pages = ctx.get("total_pages", 0)
    overall = ctx.get("overall", {})
    pages = ctx.get("pages", [])

    pages_summary = []
    for p in pages:
        page_num = p.get("page", "?")
        status = p.get("status", "?")
        sim = p.get("image_similarity", 0)
        tc = p.get("text_changes", [])
        tc_count = p.get("text_changes_count", len(tc))
        pages_summary.append(
            f"Page {page_num}: status={status}, similarity={sim:.1%}, text_changes={tc_count}"
        )
        if tc:
            for c in tc[:5]:  # limit to 5 changes per page
                pages_summary.append(
                    f"  - {c.get('type','?')}: \"{c.get('original','')[:80]}\" -> \"{c.get('revised','')[:80]}\""
                )

    context_text = f"""PDF Comparison Results:
- Total pages compared: {total_pages}
- Overall change level: {overall.get('overall_change', 'N/A')}
- AI confidence: {overall.get('confidence', 0):.0%}

Per-page breakdown:
{chr(10).join(pages_summary)}
"""

    system_prompt = f"""You are an AI assistant that helps users understand PDF comparison results.
You have access to the full comparison data between two PDF documents.

{context_text}

Rules:
- Answer questions about the comparison results clearly and specifically.
- Reference specific page numbers and exact changes when relevant.
- If asked about something not in the data, say so honestly.
- Be concise but thorough. Use bullet points for clarity.
- If the user asks for a summary, provide a structured overview.
- You can suggest what to look at or what changes are most important.
"""

    # Build messages array
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for h in req.history[-10:]:  # Keep last 10 messages for context window
        messages.append({
            "role": h.get("role", "user"),
            "content": h.get("content", ""),
        })

    # Add current user message
    messages.append({"role": "user", "content": req.message})

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=1024,
            messages=messages,
        )
        reply = response.choices[0].message.content.strip()
        return ChatResponse(reply=reply)

    except Exception as exc:
        logger.exception("Chat API call failed")
        raise HTTPException(status_code=500, detail=f"AI chat failed: {str(exc)}")
