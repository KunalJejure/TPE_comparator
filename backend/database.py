import sqlite3
import logging
import json
import os
from pathlib import Path
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "history.db"
_db_lock = Lock()

# Maximum number of comparison results to keep (older ones are auto-pruned)
MAX_RESULTS = 10

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comparisons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    revised_filename TEXT NOT NULL,
                    total_pages INTEGER,
                    status TEXT,
                    report_url TEXT,
                    result_json TEXT
                )
            """)
            
            # Migration: Check if result_json column exists
            cursor.execute("PRAGMA table_info(comparisons)")
            columns = [info[1] for info in cursor.fetchall()]
            if "result_json" not in columns:
                cursor.execute("ALTER TABLE comparisons ADD COLUMN result_json TEXT")

            # ---- Requalification tables ----
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS requalification_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    pair_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'PENDING'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS requalification_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    pair_index INTEGER NOT NULL,
                    original_filename TEXT NOT NULL,
                    revised_filename TEXT NOT NULL,
                    total_pages INTEGER,
                    status TEXT DEFAULT 'PENDING',
                    result_json TEXT,
                    FOREIGN KEY (session_id) REFERENCES requalification_sessions(id)
                )
            """)
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL;")
                
            conn.commit()
            conn.close()
            logger.info("Database initialized at %s", DB_PATH)
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)


# ================================================================
# COMPARISON FUNCTIONS
# ================================================================

def add_comparison(original, revised, pages, status, report_url=None, result_json=None):
    """Add a new comparison record to the history."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO comparisons (timestamp, original_filename, revised_filename, total_pages, status, report_url, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, original, revised, pages, status, report_url, result_json))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()

        # Auto-prune: keep only the last MAX_RESULTS comparisons
        prune_old_comparisons()

        return new_id
    except Exception as e:
        logger.error("Failed to add comparison to history: %s", e)
        return None


def prune_old_comparisons():
    """Delete comparisons beyond the most recent MAX_RESULTS, including their report PDFs."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Find IDs and report URLs of rows to delete
            cursor.execute("""
                SELECT id, report_url FROM comparisons
                WHERE id NOT IN (
                    SELECT id FROM comparisons ORDER BY id DESC LIMIT ?
                )
            """, (MAX_RESULTS,))
            old_rows = cursor.fetchall()

            if not old_rows:
                conn.close()
                return

            # Delete associated report PDFs from disk
            from backend.config import REPORTS_DIR
            for row in old_rows:
                report_url = row[1]
                if report_url:
                    # Extract filename from URL like /static/reports/xxx_diff.pdf
                    filename = report_url.split("/")[-1] if "/" in report_url else report_url
                    report_path = REPORTS_DIR / filename
                    if report_path.exists():
                        try:
                            report_path.unlink()
                            logger.info("Pruned old report: %s", filename)
                        except Exception as e:
                            logger.warning("Could not delete report %s: %s", filename, e)

            # Delete old comparison records from DB
            old_ids = [row[0] for row in old_rows]
            placeholders = ",".join("?" * len(old_ids))
            cursor.execute(f"DELETE FROM comparisons WHERE id IN ({placeholders})", old_ids)
            conn.commit()
            conn.close()
            logger.info("Pruned %d old comparison(s), keeping the last %d.", len(old_ids), MAX_RESULTS)
    except Exception as e:
        logger.error("Failed to prune old comparisons: %s", e)

def get_comparison_result(comparison_id):
    """Fetch the full result JSON for a specific comparison."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT result_json FROM comparisons WHERE id = ?", (comparison_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row["result_json"]:
                return row["result_json"]
            return None
    except Exception as e:
        logger.error("Failed to fetch comparison result: %s", e)
        return None


def get_comparison_stats():
    """Fetch high-level statistics for the reports dashboard."""
    stats = {
        "total_comparisons": 0,
        "success_rate": 0.0,
        "avg_pages": 0.0,
        "activity_trend": [],
        "page_distribution": {"small": 0, "medium": 0, "large": 0}
    }
    
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM comparisons")
            stats["total_comparisons"] = cursor.fetchone()[0]
            
            if stats["total_comparisons"] > 0:
                cursor.execute("SELECT COUNT(*) FROM comparisons WHERE status != 'FAIL'")
                success_count = cursor.fetchone()[0]
                stats["success_rate"] = round((success_count / stats["total_comparisons"]) * 100, 1)
            
            cursor.execute("SELECT AVG(total_pages) FROM comparisons")
            avg = cursor.fetchone()[0]
            stats["avg_pages"] = round(avg, 1) if avg else 0
            
            cursor.execute("""
                SELECT substr(timestamp, 1, 10) as day, COUNT(*) as count 
                FROM comparisons 
                GROUP BY day 
                ORDER BY day DESC 
                LIMIT 30
            """)
            rows = cursor.fetchall()
            stats["activity_trend"] = [{"date": row["day"], "count": row["count"]} for row in rows][::-1]
            
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN total_pages <= 10 THEN 1 ELSE 0 END) as small,
                    SUM(CASE WHEN total_pages > 10 AND total_pages <= 50 THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN total_pages > 50 THEN 1 ELSE 0 END) as large
                FROM comparisons
            """)
            dist = cursor.fetchone()
            if dist:
                stats["page_distribution"] = {
                    "small": dist["small"] or 0,
                    "medium": dist["medium"] or 0,
                    "large": dist["large"] or 0
                }
                
            conn.close()
    except Exception as e:
        logger.error("Failed to fetch comparison stats: %s", e)
        
    return stats

def get_all_comparisons(status_filter=None, start_date=None, end_date=None):
    """Fetch all comparisons with optional filtering."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT id, timestamp, original_filename, revised_filename, total_pages, status, report_url FROM comparisons WHERE 1=1"
            params = []
            
            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)
            
            if start_date:
                query += " AND substr(timestamp, 1, 10) >= ?"
                params.append(start_date)
                
            if end_date:
                query += " AND substr(timestamp, 1, 10) <= ?"
                params.append(end_date)
                
            query += " ORDER BY id DESC"
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to fetch filtered history: %s", e)
        return []


# ================================================================
# REQUALIFICATION DATABASE FUNCTIONS
# ================================================================

def create_requal_session(name: str, pair_count: int) -> int:
    """Create a new requalification session. Returns the session ID."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO requalification_sessions (name, created_at, pair_count, status)
                VALUES (?, ?, ?, 'IN_PROGRESS')
            """, (name, created_at, pair_count))
            session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return session_id
    except Exception as e:
        logger.error("Failed to create requal session: %s", e)
        return -1

def add_requal_pair(session_id: int, pair_index: int, original: str, revised: str,
                    total_pages: int, status: str, result_json: str = None):
    """Add a comparison pair result to a requalification session."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO requalification_pairs 
                (session_id, pair_index, original_filename, revised_filename, total_pages, status, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, pair_index, original, revised, total_pages, status, result_json))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error("Failed to add requal pair: %s", e)

def update_requal_session_status(session_id: int, status: str):
    """Update the status of a requalification session."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE requalification_sessions SET status = ? WHERE id = ?",
                           (status, session_id))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error("Failed to update requal session status: %s", e)

def get_requal_sessions():
    """Fetch all requalification sessions (without pair result JSONs)."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.id, s.name, s.created_at, s.pair_count, s.status,
                       COUNT(p.id) as completed_pairs,
                       SUM(CASE WHEN p.status IN ('PASS', 'NO CHANGES') THEN 1 ELSE 0 END) as passed_pairs
                FROM requalification_sessions s
                LEFT JOIN requalification_pairs p ON s.id = p.session_id
                GROUP BY s.id
                ORDER BY s.id DESC
            """)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to fetch requal sessions: %s", e)
        return []

def get_requal_session_detail(session_id: int):
    """Fetch a session with all its pair results (including result JSONs)."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM requalification_sessions WHERE id = ?", (session_id,))
            session = cursor.fetchone()
            if not session:
                conn.close()
                return None

            cursor.execute("""
                SELECT id, pair_index, original_filename, revised_filename,
                       total_pages, status, result_json
                FROM requalification_pairs
                WHERE session_id = ?
                ORDER BY pair_index
            """, (session_id,))
            pairs = cursor.fetchall()
            conn.close()

            result = dict(session)
            result["pairs"] = []
            for p in pairs:
                pair_dict = dict(p)
                if pair_dict.get("result_json"):
                    try:
                        pair_dict["result_data"] = json.loads(pair_dict["result_json"])
                    except Exception:
                        pair_dict["result_data"] = None
                    del pair_dict["result_json"]
                else:
                    pair_dict["result_data"] = None
                result["pairs"].append(pair_dict)

            return result
    except Exception as e:
        logger.error("Failed to fetch requal session detail: %s", e)
        return None

def delete_requal_session(session_id: int):
    """Delete a requalification session and all its pairs."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM requalification_pairs WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM requalification_sessions WHERE id = ?", (session_id,))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error("Failed to delete requal session: %s", e)
