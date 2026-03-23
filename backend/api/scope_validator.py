"""Scope Validator API — validates scope/deliverable coverage in Word documents.

Endpoints:
  POST /api/scope-validator/validate      — Run validation
  POST /api/scope-validator/extract-scope — Extract scope items from a support file
  GET  /api/scope-validator/history       — List last 10 validations
  GET  /api/scope-validator/history/{id}  — Get a specific validation result
  DELETE /api/scope-validator/history/{id} — Delete a validation record
"""

import logging
import json
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from backend.services.docx_parser import extract_docx_rich
from backend.services.text_extractor import extract_text_from_file
from backend.services.scope_matcher import (
    build_tfidf_vectors, 
    find_best_match_in_paragraph, 
    llm_validate_coverage
)
from backend.database import (
    add_scope_validation, 
    get_scope_validations, 
    get_scope_validation_detail, 
    delete_scope_validation
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/extract-scope")
async def extract_scope_items(file: UploadFile = File(...)):
    """Extract potential scope items from a support document."""
    try:
        content = await file.read()
        text = extract_text_from_file(content, file.filename)
        
        # Use a simple split by newline for now, 
        # but could be improved with LLM if needed
        items = [line.strip() for line in text.split("\n") if len(line.strip()) > 10]
        
        # Limit to 50 items for safety
        return {"items": items[:50]}
    except Exception as e:
        logger.error("Scope extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate")
async def validate_scope(
    validation_doc: UploadFile = File(...),
    scope_items_json: str = Form(...),
):
    """Run the 3-layer matching engine to validate scope coverage."""
    try:
        scope_items = json.loads(scope_items_json)
        if not scope_items:
            raise HTTPException(status_code=400, detail="No scope items provided")

        # 1. Parse the validation document
        doc_content = await validation_doc.read()
        if not validation_doc.filename.lower().endswith(".docx"):
            raise HTTPException(status_code=400, detail="Validation document must be .docx")
            
        doc_data = extract_docx_rich(doc_content)
        paragraphs = doc_data["paragraphs"]
        
        if not paragraphs:
            raise HTTPException(status_code=400, detail="Could not extract text from document")

        # 2. Build Layer 1 (TF-IDF)
        vectors = build_tfidf_vectors(scope_items, paragraphs)
        cosine_sim = vectors["cosine_sim"]
        
        results = []
        unmatched_items = []
        borderline_items = []
        
        # 3. Layer 2: Hybrid Keyword/Phrase/Structural matching
        for i, scope_item in enumerate(scope_items):
            best_match = {"ratio": 0.0, "para_idx": -1}
            
            # Use TF-IDF to narrow down paragraphs
            scope_vec = vectors["scope_vectors"][i]
            top_paras = []
            for j, para_vec in enumerate(vectors["para_vectors"]):
                sim = cosine_sim(scope_vec, para_vec)
                if sim > 0: top_paras.append((j, sim))
            
            top_paras.sort(key=lambda x: x[1], reverse=True)
            
            # Exhaustively check top 10 relevant paragraphs
            for p_idx, _ in top_paras[:10]:
                match = find_best_match_in_paragraph(scope_item, paragraphs[p_idx]["text"])
                if match["ratio"] > best_match["ratio"]:
                    best_match = match
                    best_match["para_idx"] = paragraphs[p_idx]["index"]

            res = {
                "scope_item": scope_item,
                "covered": best_match["ratio"] >= 0.75,
                "confidence": round(float(best_match["ratio"]), 3),
                "matched_text": best_match["matched_text"],
                "para_idx": int(best_match["para_idx"]),
                "match_type": best_match["match_type"],
                "reasoning": "High-confidence structural/keyword match" if best_match["ratio"] >= 0.75 else "No strong match found"
            }
            results.append(res)
            
            if best_match["ratio"] < 0.4:
                unmatched_items.append(res)
            elif 0.4 <= best_match["ratio"] < 0.75:
                borderline_items.append(res)

        # 4. Layer 3: LLM Semantic Validation
        llm_results = llm_validate_coverage(unmatched_items, borderline_items, paragraphs)
        
        for r in results:
            if r["scope_item"] in llm_results:
                llm_data = llm_results[r["scope_item"]]
                if llm_data["covered"]:
                    r["covered"] = True
                    r["confidence"] = llm_data["confidence"]
                    r["match_type"] = llm_data["match_type"]
                    r["matched_text"] = llm_data["matched_section"]
                    r["reasoning"] = f"LLM Match: {llm_data['reasoning']}"

        # 5. Summary & Save
        matched_count = sum(1 for r in results if r["covered"])
        total_count = len(results)
        coverage_pct = round((matched_count / total_count) * 100, 1)
        
        full_result = {
            "summary": {
                "document_name": validation_doc.filename,
                "matched_count": matched_count,
                "total_count": total_count,
                "coverage_pct": coverage_pct,
            },
            "results": results,
            "rich_html": doc_data["rich_html"]
        }
        
        add_scope_validation(
            document_filename=validation_doc.filename,
            scope_items_json=scope_items_json,
            matched_count=matched_count,
            total_count=total_count,
            coverage_pct=coverage_pct,
            result_json=json.dumps(full_result)
        )
        
        return full_result
        
    except Exception as e:
        logger.exception("Scope validation failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_history():
    return get_scope_validations()

@router.get("/history/{record_id}")
def get_detail(record_id: int):
    detail = get_scope_validation_detail(record_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Result not found")
    return detail

@router.delete("/history/{record_id}")
def delete_record(record_id: int):
    delete_scope_validation(record_id)
    return {"status": "DELETED"}
