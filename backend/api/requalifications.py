"""Requalification API — batch PDF pair comparison sessions."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from backend.database import (
    create_requal_session,
    add_requal_pair,
    update_requal_session_status,
    get_requal_sessions,
    get_requal_session_detail,
    delete_requal_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class SessionCreateRequest(BaseModel):
    name: str
    pair_count: int


# Simple in-memory cache for sessions list
_session_cache = {
    "data": None,
    "last_updated": 0
}

def _invalidate_cache():
    global _session_cache
    _session_cache["data"] = None


@router.post("/sessions")
def create_session(req: SessionCreateRequest):
    """Create a new requalification session."""
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Session name is required")
    session_id = create_requal_session(req.name.strip(), req.pair_count)
    if session_id < 0:
        raise HTTPException(status_code=500, detail="Failed to create session")
    
    _invalidate_cache()
    return {"id": session_id, "name": req.name.strip()}


@router.get("/sessions")
def list_sessions():
    """List all requalification sessions."""
    global _session_cache
    if _session_cache["data"] is not None:
        return _session_cache["data"]
    
    sessions = get_requal_sessions()
    _session_cache["data"] = sessions
    return sessions


@router.get("/sessions/{session_id}")
def get_session(session_id: int):
    """Get full session detail with pair results."""
    detail = get_requal_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.post("/sessions/{session_id}/pair")
def add_pair_result(
    session_id: int,
    pair_index: int = Form(...),
    original_filename: str = Form(...),
    revised_filename: str = Form(...),
    total_pages: int = Form(0),
    status: str = Form("PENDING"),
    result_json: str = Form(""),
    comparison_id: Optional[int] = Form(None),
):
    """Store a pair comparison result for a session."""
    final_json = result_json if result_json else None
    
    # If comparison_id is provided, try to fetch the JSON from the main comparisons table
    # This avoids sending huge JSON blobs (base64 images) over the wire again
    if comparison_id:
        from backend.database import get_comparison_result
        try:
            db_json = get_comparison_result(comparison_id)
            if db_json:
                final_json = db_json
        except Exception as e:
            logger.error(f"Failed to fetch linked comparison result {comparison_id}: {e}")

    add_requal_pair(
        session_id=session_id,
        pair_index=pair_index,
        original=original_filename,
        revised=revised_filename,
        total_pages=total_pages,
        status=status,
        result_json=final_json,
    )
    # We generally don't need to invalidate the main session LIST cache here 
    # as pair details are inside the detail view, but the "completed_pairs" count 
    # in the list view might be outdated. 
    # To keep the list view live with progress, we CAN invalidate, but that defeats the purpose during high-load.
    # Let's NOT invalidate on every pair update to protect the DB from read-spam during batch runs.
    # The user can refresh to see updated counts.
    return {"ok": True}


@router.put("/sessions/{session_id}/status")
def update_session_status(session_id: int, status: str):
    """Update session status (COMPLETED / FAILED)."""
    update_requal_session_status(session_id, status)
    _invalidate_cache()
    return {"ok": True}


@router.delete("/sessions/{session_id}")
def remove_session(session_id: int):
    """Delete a session and all its pairs."""
    delete_requal_session(session_id)
    _invalidate_cache()
    return {"ok": True}
