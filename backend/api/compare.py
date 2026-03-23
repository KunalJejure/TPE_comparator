"""POST /api/compare — upload two PDFs and get a structured diff result
with base64 page images, line-level text diffs, and visual diff overlays.

Handles PDFs with different page counts gracefully:
  • Pages present in both → full text + visual comparison
  • Pages only in original → marked as REMOVED
  • Pages only in revised  → marked as ADDED
"""

import base64
import io
import re
import shutil
import unicodedata
import uuid
import logging
import difflib
from pathlib import Path
from typing import Dict, Any, List, Optional

from PIL import Image
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from backend.config import UPLOAD_DIR, REPORTS_DIR
from backend.services.pdf_parser import extract_text, page_to_image
from backend.services.page_aligner import align_pages
from backend.services.visual_diff import generate_diff_overlay, compute_similarity
from backend.database import add_comparison

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Text normalisation (Step 1 — accuracy improvement) ───────────────

def _normalize_text(text: str) -> str:
    """Normalise text to reduce false-positive diffs.

    Applies:
      • Unicode NFKC normalisation (e.g. ﬁ → fi, ™ → TM)
      • Collapse multiple spaces / tabs into a single space
      • Trim whitespace around newlines
      • Normalise line endings to \\n
      • Strip leading/trailing whitespace
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)       # collapse horizontal whitespace
    text = re.sub(r" *\n *", "\n", text)      # trim spaces around newlines
    text = re.sub(r"\n{3,}", "\n\n", text)    # collapse 3+ blank lines → 2
    return text.strip()


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

def _compute_intra_line_diff(
    left: str, right: str,
) -> Dict[str, List[Dict[str, str]]]:
    """Compute word-level diff tokens for a single replaced line pair.

    Returns ``intra_left`` and ``intra_right`` — lists of
    ``{"text": "...", "type": "equal|delete|insert"}`` tokens that the
    frontend can render with per-word highlighting.
    """
    left_words = left.split(" ")
    right_words = right.split(" ")
    sm = difflib.SequenceMatcher(None, left_words, right_words)

    intra_left: List[Dict[str, str]] = []
    intra_right: List[Dict[str, str]] = []

    for op, li1, li2, ri1, ri2 in sm.get_opcodes():
        if op == "equal":
            intra_left.append({"text": " ".join(left_words[li1:li2]), "type": "equal"})
            intra_right.append({"text": " ".join(right_words[ri1:ri2]), "type": "equal"})
        elif op == "delete":
            intra_left.append({"text": " ".join(left_words[li1:li2]), "type": "delete"})
        elif op == "insert":
            intra_right.append({"text": " ".join(right_words[ri1:ri2]), "type": "insert"})
        elif op == "replace":
            intra_left.append({"text": " ".join(left_words[li1:li2]), "type": "delete"})
            intra_right.append({"text": " ".join(right_words[ri1:ri2]), "type": "insert"})

    return {"intra_left": intra_left, "intra_right": intra_right}


def _build_line_diff(text1: str, text2: str) -> List[Dict[str, Any]]:
    """Build a line-level diff suitable for GitHub-style rendering.

    Each entry:
        type:           'equal' | 'insert' | 'delete' | 'replace'
        left_line_no:   int | None
        right_line_no:  int | None
        left_content:   str
        right_content:  str
        intra_left:     list[{text, type}] | None  (word-level tokens for replace)
        intra_right:    list[{text, type}] | None  (word-level tokens for replace)
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
                left_text = lines1[left_idx] if left_idx is not None else ""
                right_text = lines2[right_idx] if right_idx is not None else ""

                entry: Dict[str, Any] = {
                    "type": "replace",
                    "left_line_no": (left_idx + 1) if left_idx is not None else None,
                    "right_line_no": (right_idx + 1) if right_idx is not None else None,
                    "left_content": left_text,
                    "right_content": right_text,
                }

                # Compute word-level diff when both sides have content
                if left_text and right_text:
                    intra = _compute_intra_line_diff(left_text, right_text)
                    entry["intra_left"] = intra["intra_left"]
                    entry["intra_right"] = intra["intra_right"]

                diff_lines.append(entry)

    return diff_lines



import subprocess
import os

def convert_docx_to_pdf(docx_path: str, pdf_path: str):
    """Convert DOCX to PDF using docx2pdf (Windows) or LibreOffice (Linux)."""
    if os.name == 'nt':
        try:
            from docx2pdf import convert
            convert(docx_path, pdf_path)
            return
        except ImportError:
            logger.warning("docx2pdf not installed on Windows. Trying LibreOffice...")
            pass

    try:
        outdir = os.path.dirname(pdf_path)
        # Try 'libreoffice' command
        cmd = ["libreoffice", "--headless", "--convert-to", "pdf", docx_path, "--outdir", outdir]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            # Fallback to 'soffice'
            cmd[0] = "soffice"
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
        generated = os.path.join(outdir, Path(docx_path).stem + ".pdf")
        if generated != pdf_path and os.path.exists(generated):
            shutil.move(generated, pdf_path)
    except Exception as e:
        raise RuntimeError(f"DOCX to PDF conversion failed: {e}")

# ── Endpoint ─────────────────────────────────────────────────────────



@router.post("/compare")
def compare_pdfs(
    original: UploadFile = File(...),
    revised: UploadFile = File(...),
    start_page: Optional[int] = Form(None),
    end_page: Optional[int] = Form(None),
) -> Dict[str, Any]:

    # Validate file extensions
    orig_name = original.filename or ""
    rev_name = revised.filename or ""

    if orig_name and not (orig_name.lower().endswith(".pdf") or orig_name.lower().endswith(".docx")):
        raise HTTPException(status_code=400, detail="Original file must be a PDF or DOCX")
    if rev_name and not (rev_name.lower().endswith(".pdf") or rev_name.lower().endswith(".docx")):
        raise HTTPException(status_code=400, detail="Revised file must be a PDF or DOCX")

    # --- Create isolated working directory ---
    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    orig_ext = ".docx" if orig_name.lower().endswith(".docx") else ".pdf"
    rev_ext = ".docx" if rev_name.lower().endswith(".docx") else ".pdf"

    original_path = job_dir / f"original{orig_ext}"
    revised_path = job_dir / f"revised{rev_ext}"

    try:
        with open(original_path, "wb") as f:
            shutil.copyfileobj(original.file, f)

        with open(revised_path, "wb") as f:
            shutil.copyfileobj(revised.file, f)

        try:
            if orig_ext == ".docx":
                pdf_path = job_dir / "original.pdf"
                convert_docx_to_pdf(str(original_path), str(pdf_path))
                original_path = pdf_path

            if rev_ext == ".docx":
                pdf_path = job_dir / "revised.pdf"
                convert_docx_to_pdf(str(revised_path), str(pdf_path))
                revised_path = pdf_path
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


        return process_comparison(
            job_id=job_id,
            job_dir=job_dir,
            original_path=original_path,
            revised_path=revised_path,
            orig_name=orig_name,
            rev_name=rev_name,
            start_page=start_page,
            end_page=end_page
        )
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
    """Run AI semantic comparison with graceful fallback.

    Step 3 improvement: sends only CHANGED pages with pre-computed
    diff summaries, so the LLM analyses 100% of real changes instead
    of truncating to the first 12K characters.
    """
    try:
        from backend.services.ai_compare import ai_compare, _summarize_line_diff

        # ── Build changed-pages list ──
        changed_pages: List[Dict[str, Any]] = []
        image_summary: List[Dict[str, Any]] = []

        for p in page_results:
            page_idx = p["page"] - 1  # 0-based index
            has_text_changes = p.get("text_changes_count", 0) > 0
            has_visual_changes = p.get("image_similarity", 1.0) < 0.98
            is_added_or_removed = p.get("disposition") in ("added", "removed")

            image_summary.append({
                "page": p["page"],
                "similarity": p.get("image_similarity", 1.0),
                "change": p.get("status", "PASS"),
                "disposition": p.get("disposition", "compared"),
            })

            # Only include pages with actual changes
            if has_text_changes or has_visual_changes or is_added_or_removed:
                orig_text = texts_original[page_idx] if page_idx < len(texts_original) else ""
                rev_text = texts_revised[page_idx] if page_idx < len(texts_revised) else ""
                diff_summary = _summarize_line_diff(p.get("line_diff", []))

                changed_pages.append({
                    "page": p["page"],
                    "original_text": orig_text,
                    "revised_text": rev_text,
                    "diff_summary": diff_summary,
                    "image_similarity": p.get("image_similarity", 1.0),
                })

        logger.info(
            "AI comparison: %d changed pages out of %d total",
            len(changed_pages), len(page_results),
        )

        return ai_compare(
            changed_pages=changed_pages,
            image_summary=image_summary,
        )
    except Exception as exc:
        logger.warning("AI comparison failed (continuing without it): %s", exc)
        return {
            "summary": {"overall_change": "UNKNOWN", "confidence": 0.0},
            "text_changes": [],
            "image_changes": [],
        }



def process_comparison(
    job_id: str,
    job_dir: Path,
    original_path: Path,
    revised_path: Path,
    orig_name: str,
    rev_name: str,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
) -> dict:
    # --- Text extraction ---

    texts_original = extract_text(str(original_path))
    texts_revised = extract_text(str(revised_path))

    # --- Page range slicing (optional) ---
    # Convert 1-based user input to 0-based slice indices.
    # page_offset tracks the original page number offset for display.
    page_offset = 0
    if start_page is not None or end_page is not None:
        sp = max((start_page or 1) - 1, 0)  # 0-based start
        ep_orig = end_page if end_page else len(texts_original)
        ep_rev = end_page if end_page else len(texts_revised)
        texts_original = texts_original[sp:ep_orig]
        texts_revised = texts_revised[sp:ep_rev]
        page_offset = sp
        logger.info(
            "Job %s — page range applied: pages %d–%d (offset=%d)",
            job_id, sp + 1, max(ep_orig, ep_rev), page_offset,
        )

    orig_page_count = len(texts_original)
    rev_page_count = len(texts_revised)

    if orig_page_count == 0 and rev_page_count == 0:
        raise HTTPException(status_code=400, detail="PDFs have no pages to compare")

    logger.info(
        "Job %s — original: %d pages, revised: %d pages",
        job_id, orig_page_count, rev_page_count,
    )

    # --- Smart page alignment ---
    # Normalise text before alignment for better similarity scoring
    norm_orig = [_normalize_text(t) for t in texts_original]
    norm_rev = [_normalize_text(t) for t in texts_revised]
    alignment = align_pages(norm_orig, norm_rev)
    total_pages = len(alignment)

    logger.info(
        "Job %s — %d alignment pairs (orig=%d, rev=%d)",
        job_id, total_pages, orig_page_count, rev_page_count,
    )

    # --- Per-pair analysis (aligned pages) ---
    page_results: List[Dict[str, Any]] = []
    report_images: List[Image.Image] = []

    for pair_idx, (orig_idx, rev_idx) in enumerate(alignment):
        page_num = pair_idx + 1
        page_data: Dict[str, Any] = {"page": page_num}

        has_original = orig_idx is not None
        has_revised = rev_idx is not None

        # Include the actual source page numbers for display
        page_data["original_page"] = (orig_idx + 1 + page_offset) if has_original else None
        page_data["revised_page"] = (rev_idx + 1 + page_offset) if has_revised else None

        # -- Determine page disposition --
        if has_original and has_revised:
            page_data["disposition"] = "compared"
        elif has_original and not has_revised:
            page_data["disposition"] = "removed"
        else:
            page_data["disposition"] = "added"

        # -- Text diff (line-level) --
        t1 = _normalize_text(texts_original[orig_idx]) if has_original else ""
        t2 = _normalize_text(texts_revised[rev_idx]) if has_revised else ""

        line_diff = _build_line_diff(t1, t2)
        page_data["line_diff"] = line_diff

        # Count changes
        changes_count = sum(1 for d in line_diff if d["type"] != "equal")
        page_data["text_changes_count"] = changes_count

        # -- Image rendering (use offset-adjusted page indices) --
        img1: Optional[Image.Image] = None
        img2: Optional[Image.Image] = None

        if has_original:
            img1 = page_to_image(str(original_path), orig_idx + page_offset)
        if has_revised:
            img2 = page_to_image(str(revised_path), rev_idx + page_offset)

        # Base64 page images
        page_data["original_image"] = _pil_to_base64(img1) if img1 else None
        page_data["revised_image"] = _pil_to_base64(img2) if img2 else None

        # -- Visual diff overlay (only when both pages exist) --
        overlay_img = None
        if img1 and img2:
            overlay_img, orig_hl_img, rev_hl_img, similarity, region_count = generate_diff_overlay(img1, img2)
            page_data["overlay_image"] = _pil_to_base64(overlay_img)
            page_data["original_highlight_image"] = _pil_to_base64(orig_hl_img)
            page_data["revised_highlight_image"] = _pil_to_base64(rev_hl_img)
            page_data["image_similarity"] = round(float(similarity), 4)
            page_data["diff_region_count"] = region_count
        elif img1 or img2:
            page_data["overlay_image"] = None
            page_data["image_similarity"] = 0.0
            page_data["diff_region_count"] = 0
        else:
            page_data["overlay_image"] = None
            page_data["image_similarity"] = 1.0
            page_data["diff_region_count"] = 0

        # -- Page status (significance scoring) --
        has_image_changes = page_data["image_similarity"] < 0.98
        if page_data["disposition"] in ("added", "removed"):
            page_data["status"] = page_data["disposition"].upper()
        elif changes_count > 0 or has_image_changes:
            meaningful_count = 0
            trivial_count = 0
            for d in line_diff:
                if d["type"] == "equal":
                    continue
                left = d.get("left_content", "").strip()
                right = d.get("right_content", "").strip()
                if left == right or (not left and not right):
                    trivial_count += 1
                else:
                    meaningful_count += 1

            if meaningful_count > 0 or has_image_changes:
                page_data["status"] = "FAIL"
            elif trivial_count > 0:
                page_data["status"] = "REVIEW"
            else:
                page_data["status"] = "PASS"
        else:
            page_data["status"] = "PASS"

        page_results.append(page_data)

        # -- Collect images for PDF report --
        current_report_img = None
        if overlay_img:
            current_report_img = overlay_img
        elif img1:
            current_report_img = img1
        elif img2:
            current_report_img = img2

        if current_report_img:
            if current_report_img.mode != "RGB":
                current_report_img = current_report_img.convert("RGB")
            report_images.append(current_report_img)

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

    # --- Generate Report PDF ---
    if report_images:
        report_filename = f"{job_id}_diff.pdf"
        report_path = REPORTS_DIR / report_filename
        try:
            from backend.services.report_gen import create_report
            temp_dict = {
                "overall": ai_result.get("summary", {}),
                "pages": page_results
            }
            pdf_bytes = create_report(temp_dict, report_images)
            with open(report_path, "wb") as f:
                f.write(pdf_bytes)
            report_url = f"/static/reports/{report_filename}"
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            report_url = None
    else:
        report_url = None

    # --- Save to History ---
    # --- Save to History ---
    status = "NO CHANGES"
    if any(p.get("status") != "PASS" for p in page_results):
        status = "CHANGES FOUND"

    import json
    result_content = {
        "job_id": job_id,
        "report_url": report_url,
        "total_pages": total_pages,
        "original_pages": orig_page_count,
        "revised_pages": rev_page_count,
        "original_name": orig_name,
        "revised_name": rev_name,
        "overall": ai_result["summary"],
        "pages": page_results,
    }
    
    try:
        result_json = json.dumps(result_content)
    except Exception as e:
        logger.error(f"Failed to serialize result content: {e}")
        result_json = None

    comp_id = add_comparison(
        orig_name, 
        rev_name, 
        total_pages, 
        status, 
        report_url,
        result_json
    )

    result_content["comparison_id"] = comp_id
    return result_content



import zipfile
import tempfile

@router.post("/batch-compare")
def batch_compare(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Must upload a ZIP file")
        
    batch_job_id = str(uuid.uuid4())
    batch_dir = UPLOAD_DIR / f"batch_{batch_job_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = batch_dir / "upload.zip"
    with open(zip_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    extract_dir = batch_dir / "extracted"
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            
        # Find all files by walking the extract directory
        original_files = {}
        revised_files = {}
        
        for root, dirs, files in os.walk(extract_dir):
            for filename in files:
                if filename.startswith('.'): continue
                # Identify if it belongs to original or revised
                lower_folder = os.path.basename(root).lower()
                path = Path(root) / filename
                if "original" in lower_folder or "orig" in lower_folder:
                    original_files[filename] = path
                elif "revised" in lower_folder or "rev" in lower_folder:
                    revised_files[filename] = path
                    
        # Match pairs
        results = []
        import traceback
        for filename in original_files:
            if filename in revised_files:
                orig_path = original_files[filename]
                rev_path = revised_files[filename]
                job_id = str(uuid.uuid4())
                
                # We need to copy them to a specific job dir if process_comparison requires it
                job_dir = UPLOAD_DIR / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                
                try:
                    res = process_comparison(
                        job_id=job_id,
                        job_dir=job_dir,
                        original_path=orig_path,
                        revised_path=rev_path,
                        orig_name=orig_path.name,
                        rev_name=rev_path.name,
                    )
                    results.append({"pair": filename, "status": "success", "result": res})
                except Exception as e:
                    logger.error(f"Batch pair failed: {e}")
                    results.append({"pair": filename, "status": "error", "message": str(e)})
                    
        return {"batch_id": batch_job_id, "total_pairs": len(results), "results": results}
    except Exception as e:
        logger.exception("Batch failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(batch_dir, ignore_errors=True)
