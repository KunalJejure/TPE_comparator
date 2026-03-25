"""Supabase Database Implementation — Replaces SQLite with Supabase SDK."""

import logging
import json
import secrets
from datetime import datetime
from backend.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Maximum records to keep (Supabase handle pruning if needed, but we can do it here too)
MAX_RESULTS = 10
MAX_SCOPE_VALIDATIONS = 10

def init_db():
    """
    In Supabase, tables should be created via the SQL Editor.
    This function now acts as a connection check.
    """
    supabase = get_supabase()
    if supabase:
        try:
            # Simple check to see if we can connect
            supabase.table("comparisons").select("id", count="exact").limit(1).execute()
            logger.info("Supabase connection verified.")
        except Exception as e:
            logger.error("Supabase connection check failed: %s", e)
    else:
        logger.warning("Supabase client not initialised.")

# --- Comparison Functions ---

def add_comparison(original, revised, pages, status, report_url=None, result_json=None):
    try:
        supabase = get_supabase()
        processed_json = result_json if isinstance(result_json, (dict, list)) else json.loads(result_json) if result_json else None
        data = {
            "original_filename": original,
            "revised_filename": revised,
            "total_pages": pages,
            "status": status,
            "report_url": report_url,
            "result_json": processed_json
        }
        res = supabase.table("comparisons").insert(data).execute()
        
        # Get the new ID from the response
        if res.data:
            new_id = res.data[0]['id']
            prune_old_comparisons()
            return new_id
        return None
    except Exception as e:
        logger.error("Failed to add comparison to Supabase: %s", e)
        return None

def prune_old_comparisons():
    """Prunes old comparisons from Supabase and deletes their image data on disk."""
    try:
        from backend.config import COMPARISONS_DATA_DIR
        import shutil
        
        supabase = get_supabase()
        # Fetch records ordered by ID descending to identify which ones to keep
        res = supabase.table("comparisons").select("*").order("id", desc=True).execute()
        if res.data and len(res.data) > MAX_RESULTS:
            # Records to keep are the first MAX_RESULTS
            # Records to delete are the rest
            to_delete_records = res.data[MAX_RESULTS:]
            to_delete_ids = [r['id'] for r in to_delete_records]
            
            # 1. Delete matching image directories on disk
            for rec in to_delete_records:
                # The job_id is stored in the result_json
                res_json = rec.get("result_json")
                if res_json and isinstance(res_json, dict):
                    job_id = res_json.get("job_id")
                    if job_id:
                        job_dir = COMPARISONS_DATA_DIR / job_id
                        if job_dir.exists():
                            shutil.rmtree(job_dir, ignore_errors=True)
                            logger.info(f"Deleted image directory for pruned comparison: {job_id}")

            # 2. Delete from Supabase
            supabase.table("comparisons").delete().in_("id", to_delete_ids).execute()
            logger.info("Pruned %d old comparisons from Supabase.", len(to_delete_ids))
    except Exception as e:
        logger.error("Pruning failed: %s", e)

def get_comparison_result(comparison_id):
    try:
        supabase = get_supabase()
        res = supabase.table("comparisons").select("result_json").eq("id", comparison_id).maybe_single().execute()
        if res.data:
            return json.dumps(res.data["result_json"]) if res.data["result_json"] else None
        return None
    except Exception as e:
        logger.error("Failed to fetch comparison result: %s", e)
        return None

def get_comparison_stats():
    """Fetch high-level statistics using client-side aggregation."""
    stats = {
        "total_comparisons": 0,
        "success_rate": 0.0,
        "avg_pages": 0.0,
        "activity_trend": [],
        "page_distribution": {"small": 0, "medium": 0, "large": 0}
    }
    try:
        supabase = get_supabase()
        
        # 1. Total comparisons
        res = supabase.table("comparisons").select("id, status, total_pages, timestamp").execute()
        rows = res.data if res.data else []
        
        stats["total_comparisons"] = len(rows)
        if stats["total_comparisons"] > 0:
            # 2. Success rate
            success_count = sum(1 for r in rows if r["status"] != 'FAIL')
            stats["success_rate"] = round((success_count / stats["total_comparisons"]) * 100, 1)
            
            # 3. Avg pages
            total_pages = sum(r["total_pages"] for r in rows if r["total_pages"])
            stats["avg_pages"] = round(total_pages / stats["total_comparisons"], 1)
            
            # 4. Activity Trend (Group by day) - Simple client-side grouping
            trends = {}
            for r in rows:
                # Supabase timestamp is usually ISO like '2023-10-01T12:00:00'
                day = r["timestamp"].split('T')[0] if 'T' in r["timestamp"] else r["timestamp"].split(' ')[0]
                trends[day] = trends.get(day, 0) + 1
            
            # Sort days and take last 30
            sorted_days = sorted(trends.keys(), reverse=True)[:30]
            stats["activity_trend"] = [{"date": d, "count": trends[d]} for d in sorted_days][::-1]
            
            # 5. Page Distribution
            dist = {"small": 0, "medium": 0, "large": 0}
            for r in rows:
                p = r["total_pages"] or 0
                if p <= 10: dist["small"] += 1
                elif p <= 50: dist["medium"] += 1
                else: dist["large"] += 1
            stats["page_distribution"] = dist
            
    except Exception as e:
        logger.error("Failed to fetch stats from Supabase: %s", e)
    return stats

def get_all_comparisons(status_filter=None, start_date=None, end_date=None):
    try:
        supabase = get_supabase()
        query = supabase.table("comparisons").select("id, timestamp, original_filename, revised_filename, total_pages, status, report_url")
        
        if status_filter:
            query = query.eq("status", status_filter)
        if start_date:
            query = query.gte("timestamp", start_date)
        if end_date:
            query = query.lte("timestamp", end_date)
            
        res = query.order("id", desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        logger.error("Failed to fetch all comparisons: %s", e)
        return []

# --- Requalification Functions ---

def create_requal_session(name, pair_count):
    try:
        supabase = get_supabase()
        data = {"name": name, "pair_count": pair_count, "status": "IN_PROGRESS"}
        res = supabase.table("requalification_sessions").insert(data).execute()
        return res.data[0]['id'] if res.data else None
    except Exception as e:
        logger.error("Failed to create requal session: %s", e)
        return None

def add_requal_pair(session_id, pair_idx, original, revised, pages, status, result_json=None):
    try:
        supabase = get_supabase()
        data = {
            "session_id": session_id,
            "pair_index": pair_idx,
            "original_filename": original,
            "revised_filename": revised,
            "total_pages": pages,
            "status": status,
            "result_json": result_json if isinstance(result_json, (dict, list)) else json.loads(result_json) if result_json else None
        }
        supabase.table("requalification_pairs").insert(data).execute()
    except Exception as e:
        logger.error("Failed to add requal pair: %s", e)

def update_requal_session_status(session_id: int, status: str):
    try:
        supabase = get_supabase()
        supabase.table("requalification_sessions").update({"status": status}).eq("id", session_id).execute()
    except Exception as e:
        logger.error("Failed to update requal status: %s", e)

def get_requal_sessions():
    try:
        supabase = get_supabase()
        # Complex join logic is harder in Supabase SDK without RPC, but we can do it in two steps or use RPC.
        # For now, let's fetch sessions and counts separately or just sessions.
        res = supabase.table("requalification_sessions").select("*, requalification_pairs(id, status)").order("id", desc=True).execute()
        
        output = []
        if res.data:
            for s in res.data:
                pairs = s.get("requalification_pairs", [])
                s["completed_pairs"] = len(pairs)
                s["passed_pairs"] = sum(1 for p in pairs if p["status"] in ('PASS', 'NO CHANGES'))
                # Clean up nested data
                del s["requalification_pairs"]
                output.append(s)
        return output
    except Exception as e:
        logger.error("Failed to fetch requal sessions: %s", e)
        return []

def get_requal_session_detail(session_id):
    try:
        supabase = get_supabase()
        # Fetch session
        sess_res = supabase.table("requalification_sessions").select("*").eq("id", session_id).maybe_single().execute()
        if not sess_res.data: return None
        
        # Fetch pairs
        pairs_res = supabase.table("requalification_pairs").select("*").eq("session_id", session_id).order("pair_index").execute()
        
        res = sess_res.data
        res["pairs"] = pairs_res.data if pairs_res.data else []
        
        for p in res["pairs"]:
            p["result_data"] = p["result_json"] # Supabase returns JSONB as dict
            # Keeping 'del p["result_json"]' if compatibility is needed
        return res
    except Exception as e:
        logger.error("Failed to fetch session detail: %s", e)
        return None

def delete_requal_session(session_id: int):
    try:
        supabase = get_supabase()
        # Cascade delete should handle pairs if set up in SQL
        supabase.table("requalification_sessions").delete().eq("id", session_id).execute()
    except Exception as e:
        logger.error("Failed to delete session: %s", e)

# --- Scope Validation Functions ---

def add_scope_validation(document_filename, scope_items_json, matched_count, total_count, coverage_pct, result_json=None):
    try:
        supabase = get_supabase()
        data = {
            "document_filename": document_filename,
            "scope_items_json": scope_items_json if isinstance(scope_items_json, (dict, list)) else json.loads(scope_items_json) if scope_items_json else None,
            "matched_count": matched_count,
            "total_count": total_count,
            "coverage_pct": coverage_pct,
            "result_json": result_json if isinstance(result_json, (dict, list)) else json.loads(result_json) if result_json else None
        }
        supabase.table("scope_validations").insert(data).execute()
        
        # Prune
        res = supabase.table("scope_validations").select("id").order("id", desc=True).execute()
        if res.data and len(res.data) > MAX_SCOPE_VALIDATIONS:
            to_delete = [r['id'] for r in res.data[MAX_SCOPE_VALIDATIONS:]]
            supabase.table("scope_validations").delete().in_("id", to_delete).execute()
    except Exception as e:
        logger.error("Failed to add scope validation: %s", e)

def get_scope_validations():
    try:
        supabase = get_supabase()
        res = supabase.table("scope_validations").select("id, timestamp, document_filename, matched_count, total_count, coverage_pct").order("id", desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        logger.error("Failed to fetch scope validations: %s", e)
        return []

def get_scope_validation_detail(record_id):
    try:
        supabase = get_supabase()
        res = supabase.table("scope_validations").select("*").eq("id", record_id).maybe_single().execute()
        if not res.data: return None
        
        item = res.data
        item["result_data"] = item["result_json"]
        return item
    except Exception as e:
        logger.error("Failed to fetch scope detail: %s", e)
        return None

def delete_scope_validation(record_id):
    try:
        supabase = get_supabase()
        supabase.table("scope_validations").delete().eq("id", record_id).execute()
    except Exception as e:
        logger.error("Failed to delete scope validation: %s", e)

# --- API Key Functions ---

def create_api_key(owner):
    try:
        key = "fsb_" + secrets.token_urlsafe(32)
        supabase = get_supabase()
        data = {"key_value": key, "owner": owner}
        supabase.table("api_keys").insert(data).execute()
        return key
    except Exception as e:
        logger.error("Failed to create API key: %s", e)
        return None

def validate_api_key(key):
    try:
        supabase = get_supabase()
        res = supabase.table("api_keys").select("id").eq("key_value", key).eq("is_active", True).maybe_single().execute()
        return res.data is not None
    except Exception as e:
        logger.error("Failed to validate API key: %s", e)
        return False
