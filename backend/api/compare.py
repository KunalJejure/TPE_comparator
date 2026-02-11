"""POST /api/compare — upload two PDFs and get a structured diff result."""

import shutil
import uuid
import logging
from typing import Dict, Any, List

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.config import UPLOAD_DIR
from backend.services.pdf_parser import extract_text, page_to_image
from backend.services.visual_diff import visual_diff

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/compare")
async def compare_pdfs(
    original: UploadFile = File(...),
    revised: UploadFile = File(...),
) -> Dict[str, Any]:

    # Validate file extensions (be lenient — accept any .pdf or empty filename)
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

        total_pages = min(len(texts_original), len(texts_revised))

        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDFs have no pages to compare")

        # --- Image diff (page level) ---
        image_diffs: List[Dict[str, Any]] = []

        for page in range(total_pages):
            img1 = page_to_image(str(original_path), page)
            img2 = page_to_image(str(revised_path), page)

            _diff_img, similarity = visual_diff(img1, img2)

            image_diffs.append({
                "page": page + 1,
                "similarity": round(float(similarity), 3),
                "change": "PASS" if similarity > 0.98 else "FAIL",
            })

        # --- AI semantic comparison (graceful fallback) ---
        ai_result = None
        try:
            from backend.services.ai_compare import ai_compare

            ai_result = ai_compare(
                text1="\n".join(texts_original),
                text2="\n".join(texts_revised),
                image_summary=image_diffs,
            )
        except Exception as exc:
            logger.warning("AI comparison failed (continuing without it): %s", exc)
            ai_result = {
                "summary": {"overall_change": "UNKNOWN", "confidence": 0.0},
                "text_changes": [],
                "image_changes": [],
            }

        # --- Merge page-level results ---
        page_results = []

        for page in range(1, total_pages + 1):
            page_text_changes = [
                c for c in ai_result.get("text_changes", [])
                if c.get("page") == page
            ]
            page_images = [i for i in image_diffs if i["page"] == page]

            page_status = "PASS"
            if page_text_changes or (page_images and page_images[0]["change"] == "FAIL"):
                page_status = "FAIL"

            page_results.append({
                "page": page,
                "status": page_status,
                "confidence": ai_result["summary"]["confidence"],
                "text_changes": page_text_changes,
                "image_similarity": page_images[0]["similarity"] if page_images else 1.0,
            })

        return {
            "job_id": job_id,
            "total_pages": total_pages,
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
