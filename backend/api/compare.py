"""POST /api/compare — upload two PDFs and get a structured diff result
with base64 page images, line-level text diffs, and visual diff overlays.

Handles PDFs with different page counts gracefully:
  • Pages present in both → full text + visual comparison
  • Pages only in original → marked as REMOVED
  • Pages only in revised  → marked as ADDED
"""

import base64
import io
import shutil
import uuid
import logging
import difflib
from typing import Dict, Any, List, Optional

from PIL import Image
from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.config import UPLOAD_DIR
from backend.services.pdf_parser import extract_text, page_to_image
from backend.services.visual_diff import generate_diff_overlay, compute_similarity

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Image encoding ───────────────────────────────────────────────────
# JPEG quality 82 gives a great quality-to-size ratio.  For a 30-page
# PDF this cuts the response payload roughly 4× versus PNG.
_IMG_FORMAT = "JPEG"
_IMG_QUALITY = 82


def _pil_to_base64(img: Image.Image) -> str:
    """Convert a PIL Image to a base64-encoded data URI (JPEG)."""
    buf = io.BytesIO()
    img.save(buf, format=_IMG_FORMAT, quality=_IMG_QUALITY)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


# ── Text diff helpers ────────────────────────────────────────────────

def _build_line_diff(text1: str, text2: str) -> List[Dict[str, Any]]:
    """Build a line-level diff suitable for GitHub-style rendering.

    Each entry:
        type:           'equal' | 'insert' | 'delete' | 'replace'
        left_line_no:   int | None
        right_line_no:  int | None
        left_content:   str
        right_content:  str
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
                    "left_line_no": (left_idx + 1) if left_idx is not None else None,
                    "right_line_no": (right_idx + 1) if right_idx is not None else None,
                    "left_content": lines1[left_idx] if left_idx is not None else "",
                    "right_content": lines2[right_idx] if right_idx is not None else "",
                })

    return diff_lines


# ── Endpoint ─────────────────────────────────────────────────────────

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

        orig_page_count = len(texts_original)
        rev_page_count = len(texts_revised)
        total_pages = max(orig_page_count, rev_page_count)

        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDFs have no pages to compare")

        logger.info(
            "Job %s — original: %d pages, revised: %d pages",
            job_id, orig_page_count, rev_page_count,
        )

        # --- Per-page analysis ---
        page_results: List[Dict[str, Any]] = []

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page_data: Dict[str, Any] = {"page": page_num}

            has_original = page_idx < orig_page_count
            has_revised = page_idx < rev_page_count

            # -- Determine page disposition --
            if has_original and has_revised:
                page_data["disposition"] = "compared"  # both exist
            elif has_original and not has_revised:
                page_data["disposition"] = "removed"   # only in original
            else:
                page_data["disposition"] = "added"      # only in revised

            # -- Text diff (line-level) --
            t1 = texts_original[page_idx] if has_original else ""
            t2 = texts_revised[page_idx] if has_revised else ""

            line_diff = _build_line_diff(t1, t2)
            page_data["line_diff"] = line_diff

            # Count changes
            changes_count = sum(1 for d in line_diff if d["type"] != "equal")
            page_data["text_changes_count"] = changes_count

            # -- Image rendering --
            img1: Optional[Image.Image] = None
            img2: Optional[Image.Image] = None

            if has_original:
                img1 = page_to_image(str(original_path), page_idx)
            if has_revised:
                img2 = page_to_image(str(revised_path), page_idx)

            # Base64 page images (always included for text-diff header)
            page_data["original_image"] = _pil_to_base64(img1) if img1 else None
            page_data["revised_image"] = _pil_to_base64(img2) if img2 else None

            # -- Visual diff overlay (only when both pages exist) --
            if img1 and img2:
                overlay_img, similarity, region_count = generate_diff_overlay(img1, img2)
                page_data["overlay_image"] = _pil_to_base64(overlay_img)
                page_data["image_similarity"] = round(float(similarity), 4)
                page_data["diff_region_count"] = region_count
            elif img1 or img2:
                # Only one side exists → completely different
                page_data["overlay_image"] = None
                page_data["image_similarity"] = 0.0
                page_data["diff_region_count"] = 0
            else:
                page_data["overlay_image"] = None
                page_data["image_similarity"] = 1.0
                page_data["diff_region_count"] = 0

            # -- Page status --
            has_text_changes = changes_count > 0
            has_image_changes = page_data["image_similarity"] < 0.98
            if page_data["disposition"] in ("added", "removed"):
                page_data["status"] = page_data["disposition"].upper()
            elif has_text_changes or has_image_changes:
                page_data["status"] = "FAIL"
            else:
                page_data["status"] = "PASS"

            page_results.append(page_data)

        # --- AI semantic comparison (graceful fallback) ---
        ai_result = _run_ai_comparison(texts_original, texts_revised, page_results)

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
            "original_pages": orig_page_count,
            "revised_pages": rev_page_count,
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


def _run_ai_comparison(
    texts_original: List[str],
    texts_revised: List[str],
    page_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run AI semantic comparison with graceful fallback."""
    try:
        from backend.services.ai_compare import ai_compare

        image_summary = [
            {
                "page": p["page"],
                "similarity": p["image_similarity"],
                "change": p["status"],
                "disposition": p.get("disposition", "compared"),
            }
            for p in page_results
        ]

        return ai_compare(
            text1="\n".join(texts_original),
            text2="\n".join(texts_revised),
            image_summary=image_summary,
        )
    except Exception as exc:
        logger.warning("AI comparison failed (continuing without it): %s", exc)
        return {
            "summary": {"overall_change": "UNKNOWN", "confidence": 0.0},
            "text_changes": [],
            "image_changes": [],
        }
