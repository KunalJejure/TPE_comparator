import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.config import UPLOAD_DIR
from utils.pdf_parser import extract_text, page_to_image
from app.services.visual_diff import visual_diff
from utils.ai_pdf_compare import ai_compare

router = APIRouter()


@router.post("/compare")
async def compare_pdfs(
    original: UploadFile = File(...),
    revised: UploadFile = File(...),
) -> Dict[str, Any]:

    if not original.filename.endswith(".pdf") or not revised.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # --- Create isolated working directory ---
    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    original_path = job_dir / "original.pdf"
    revised_path = job_dir / "revised.pdf"

    with open(original_path, "wb") as f:
        shutil.copyfileobj(original.file, f)

    with open(revised_path, "wb") as f:
        shutil.copyfileobj(revised.file, f)

    # --- TEXT EXTRACTION (ALL PAGES) ---
    texts_original = extract_text(str(original_path))
    texts_revised = extract_text(str(revised_path))

    total_pages = min(len(texts_original), len(texts_revised))

    # --- IMAGE DIFF (PAGE LEVEL) ---
    image_diffs: List[Dict[str, Any]] = []

    for page in range(total_pages):
        img1 = page_to_image(str(original_path), page)
        img2 = page_to_image(str(revised_path), page)

        diff_img, similarity = visual_diff(img1, img2)

        image_diffs.append(
            {
                "page": page + 1,
                "similarity": round(float(similarity), 3),
                "change": "PASS" if similarity > 0.98 else "FAIL",
            }
        )

    # --- AI SEMANTIC COMPARISON (WHOLE DOC) ---
    ai_result = ai_compare(
        text1="\n".join(texts_original),
        text2="\n".join(texts_revised),
        image_summary=image_diffs,
    )

    # --- MERGE PAGE-LEVEL CONFIDENCE ---
    page_results = []

    for page in range(1, total_pages + 1):
        page_text_changes = [
            c for c in ai_result.get("text_changes", [])
            if c.get("page") == page
        ]

        page_images = [
            i for i in image_diffs if i["page"] == page
        ]

        page_status = "PASS"
        if page_text_changes or (page_images and page_images[0]["change"] == "FAIL"):
            page_status = "FAIL"

        page_results.append(
            {
                "page": page,
                "status": page_status,
                "confidence": ai_result["summary"]["confidence"],
                "text_changes": page_text_changes,
                "image_similarity": page_images[0]["similarity"] if page_images else 1.0,
            }
        )

    # --- FINAL RESPONSE (SINGLE OBJECT) ---
    return {
        "job_id": job_id,
        "total_pages": total_pages,
        "overall": ai_result["summary"],
        "pages": page_results,
    }
