"""POST /api/compare — upload two PDFs and get a structured diff result
with base64 page images, line-level text diffs, and visual diff overlays."""

import base64
import io
import shutil
import uuid
import logging
import difflib
from typing import Dict, Any, List

import cv2
import numpy as np
from PIL import Image
from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.config import UPLOAD_DIR
from backend.services.pdf_parser import extract_text, page_to_image
from backend.services.visual_diff import visual_diff, generate_visual_diff

logger = logging.getLogger(__name__)

router = APIRouter()


def _pil_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    """Convert a PIL Image to a base64-encoded data URI."""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _build_line_diff(text1: str, text2: str) -> List[Dict[str, Any]]:
    """Build a unified line-level diff suitable for GitHub-style rendering.

    Each entry has:
        type: 'equal' | 'insert' | 'delete' | 'replace'
        left_line_no: int | None
        right_line_no: int | None
        left_content: str
        right_content: str
    """
    lines1 = text1.splitlines(keepends=False)
    lines2 = text2.splitlines(keepends=False)
    matcher = difflib.SequenceMatcher(None, lines1, lines2)

    diff_lines: List[Dict[str, Any]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                diff_lines.append({
                    "type": "equal",
                    "left_line_no": i1 + k + 1,
                    "right_line_no": j1 + k + 1,
                    "left_content": lines1[i1 + k],
                    "right_content": lines2[j1 + k],
                })
        elif tag == "delete":
            for k in range(i2 - i1):
                diff_lines.append({
                    "type": "delete",
                    "left_line_no": i1 + k + 1,
                    "right_line_no": None,
                    "left_content": lines1[i1 + k],
                    "right_content": "",
                })
        elif tag == "insert":
            for k in range(j2 - j1):
                diff_lines.append({
                    "type": "insert",
                    "left_line_no": None,
                    "right_line_no": j1 + k + 1,
                    "left_content": "",
                    "right_content": lines2[j1 + k],
                })
        elif tag == "replace":
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                left_idx = i1 + k if k < (i2 - i1) else None
                right_idx = j1 + k if k < (j2 - j1) else None
                diff_lines.append({
                    "type": "replace",
                    "left_line_no": left_idx + 1 if left_idx is not None else None,
                    "right_line_no": right_idx + 1 if right_idx is not None else None,
                    "left_content": lines1[left_idx] if left_idx is not None else "",
                    "right_content": lines2[right_idx] if right_idx is not None else "",
                })

    return diff_lines


def _build_word_diff(line1: str, line2: str) -> Dict[str, Any]:
    """Compute word-level inline diff for a pair of lines."""
    words1 = line1.split()
    words2 = line2.split()
    matcher = difflib.SequenceMatcher(None, words1, words2)
    left_parts = []
    right_parts = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            left_parts.append({"type": "equal", "text": " ".join(words1[i1:i2])})
            right_parts.append({"type": "equal", "text": " ".join(words2[j1:j2])})
        elif tag == "delete":
            left_parts.append({"type": "delete", "text": " ".join(words1[i1:i2])})
        elif tag == "insert":
            right_parts.append({"type": "insert", "text": " ".join(words2[j1:j2])})
        elif tag == "replace":
            left_parts.append({"type": "delete", "text": " ".join(words1[i1:i2])})
            right_parts.append({"type": "insert", "text": " ".join(words2[j1:j2])})

    return {"left": left_parts, "right": right_parts}


@router.post("/compare")
async def compare_pdfs(
    original: UploadFile = File(...),
    revised: UploadFile = File(...),
) -> Dict[str, Any]:

    # Validate file extensions
    orig_name = original.filename or ""
    rev_name = revised.filename or ""

    if orig_name and not orig_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Original file must be a PDF")
    if rev_name and not rev_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Revised file must be a PDF")

    # --- Create isolated working directory ---
    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    original_path = job_dir / "original.pdf"
    revised_path = job_dir / "revised.pdf"

    try:
        with open(original_path, "wb") as f:
            shutil.copyfileobj(original.file, f)

        with open(revised_path, "wb") as f:
            shutil.copyfileobj(revised.file, f)

        # --- Text extraction ---
        texts_original = extract_text(str(original_path))
        texts_revised = extract_text(str(revised_path))

        total_pages = max(len(texts_original), len(texts_revised))

        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDFs have no pages to compare")

        # --- Per-page analysis ---
        page_results: List[Dict[str, Any]] = []

        for page_idx in range(total_pages):
            page_data: Dict[str, Any] = {"page": page_idx + 1}

            # -- Text diff (line-level) --
            t1 = texts_original[page_idx] if page_idx < len(texts_original) else ""
            t2 = texts_revised[page_idx] if page_idx < len(texts_revised) else ""

            line_diff = _build_line_diff(t1, t2)
            page_data["line_diff"] = line_diff

            # Count changes
            changes_count = sum(1 for d in line_diff if d["type"] != "equal")
            page_data["text_changes_count"] = changes_count

            # -- Image rendering --
            img1 = None
            img2 = None
            if page_idx < len(texts_original):
                img1 = page_to_image(str(original_path), page_idx)
            if page_idx < len(texts_revised):
                img2 = page_to_image(str(revised_path), page_idx)

            # Base64 page images for side-by-side view
            if img1:
                page_data["original_image"] = _pil_to_base64(img1)
            else:
                page_data["original_image"] = None

            if img2:
                page_data["revised_image"] = _pil_to_base64(img2)
            else:
                page_data["revised_image"] = None

            # -- Visual diff overlay --
            if img1 and img2:
                diff_img, similarity = visual_diff(img1, img2)
                page_data["diff_image"] = _pil_to_base64(diff_img)
                page_data["image_similarity"] = round(float(similarity), 4)

                # Generate the highlighted diff overlay too
                cv1 = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2BGR)
                cv2_img = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2BGR)
                if cv1.shape != cv2_img.shape:
                    cv2_img = cv2.resize(cv2_img, (cv1.shape[1], cv1.shape[0]))
                overlay_bgr, sim_pct = generate_visual_diff(cv1, cv2_img)
                overlay_rgb = cv2.cvtColor(overlay_bgr, cv2.COLOR_BGR2RGB)
                overlay_pil = Image.fromarray(overlay_rgb)
                page_data["overlay_image"] = _pil_to_base64(overlay_pil)
            else:
                page_data["diff_image"] = None
                page_data["overlay_image"] = None
                page_data["image_similarity"] = 0.0 if (img1 or img2) else 1.0

            # -- Page status --
            has_text_changes = changes_count > 0
            has_image_changes = page_data["image_similarity"] < 0.98
            page_data["status"] = "FAIL" if (has_text_changes or has_image_changes) else "PASS"

            page_results.append(page_data)

        # --- AI semantic comparison (graceful fallback) ---
        ai_result = None
        try:
            from backend.services.ai_compare import ai_compare

            image_summary = [
                {"page": p["page"], "similarity": p["image_similarity"],
                 "change": p["status"]}
                for p in page_results
            ]

            ai_result = ai_compare(
                text1="\n".join(texts_original),
                text2="\n".join(texts_revised),
                image_summary=image_summary,
            )
        except Exception as exc:
            logger.warning("AI comparison failed (continuing without it): %s", exc)
            ai_result = {
                "summary": {"overall_change": "UNKNOWN", "confidence": 0.0},
                "text_changes": [],
                "image_changes": [],
            }

        # Enrich page results with AI analysis
        for p in page_results:
            page_num = p["page"]
            p["ai_text_changes"] = [
                c for c in ai_result.get("text_changes", [])
                if c.get("page") == page_num
            ]
            p["ai_image_changes"] = [
                c for c in ai_result.get("image_changes", [])
                if c.get("page") == page_num
            ]
            p["confidence"] = ai_result["summary"].get("confidence", 0.0)

        return {
            "job_id": job_id,
            "total_pages": total_pages,
            "original_name": orig_name,
            "revised_name": rev_name,
            "overall": ai_result["summary"],
            "pages": page_results,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Comparison failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(exc)}")
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
