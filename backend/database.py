import sqlite3
import logging
import json
import os
import secrets
from pathlib import Path
from datetime import datetime
from threading import Lock
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "history.db"
_db_lock = Lock()

# Maximum records to keep
MAX_RESULTS = 10
MAX_SCOPE_VALIDATIONS = 10

@contextmanager
def get_db(row_factory=None):
    """Context manager for SQLite connections with locking and WAL mode."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        if row_factory:
            conn.row_factory = row_factory
        try:
            yield conn
        finally:
            conn.close()

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Comparisons table
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
            
            # Migration check
            cursor.execute("PRAGMA table_info(comparisons)")
            if "result_json" not in [info[1] for info in cursor.fetchall()]:
                cursor.execute("ALTER TABLE comparisons ADD COLUMN result_json TEXT")

            # API Keys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_value TEXT UNIQUE NOT NULL,
                    owner TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Requalification tables
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

            # Scope Validation table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scope_validations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    document_filename TEXT NOT NULL,
                    scope_items_json TEXT,
                    matched_count INTEGER DEFAULT 0,
                    total_count INTEGER DEFAULT 0,
                    coverage_pct REAL DEFAULT 0.0,
                    result_json TEXT
                )
            """)
            
            cursor.execute("PRAGMA journal_mode=WAL;")
            conn.commit()
            logger.info("Database initialized at %s", DB_PATH)
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)

# --- Comparison Functions ---

def add_comparison(original, revised, pages, status, report_url=None, result_json=None):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO comparisons (timestamp, original_filename, revised_filename, total_pages, status, report_url, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts, original, revised, pages, status, report_url, result_json))
            new_id = cursor.lastrowid
            conn.commit()
        prune_old_comparisons()
        return new_id
    except Exception as e:
        logger.error("Failed to add comparison: %s", e)
        return None

def prune_old_comparisons():
    try:
        from backend.config import REPORTS_DIR
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, report_url FROM comparisons WHERE id NOT IN (SELECT id FROM comparisons ORDER BY id DESC LIMIT ?)", (MAX_RESULTS,))
            rows = cursor.fetchall()
            for row in rows:
                if row[1]:
                    path = REPORTS_DIR / (row[1].split("/")[-1])
                    if path.exists(): path.unlink()
            
            if rows:
                old_ids = [r[0] for r in rows]
                placeholders = ",".join("?" * len(old_ids))
                cursor.execute(f"DELETE FROM comparisons WHERE id IN ({placeholders})", old_ids)
                conn.commit()
    except Exception as e:
        logger.error("Pruning failed: %s", e)

def get_comparison_result(comparison_id):
    with get_db(row_factory=sqlite3.Row) as conn:
        row = conn.execute("SELECT result_json FROM comparisons WHERE id = ?", (comparison_id,)).fetchone()
        return row["result_json"] if row else None

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
        with get_db(row_factory=sqlite3.Row) as conn:
            cursor = conn.cursor()
            
            row = cursor.execute("SELECT COUNT(*) FROM comparisons").fetchone()
            stats["total_comparisons"] = row[0] if row else 0
            
            if stats["total_comparisons"] > 0:
                row = cursor.execute("SELECT COUNT(*) FROM comparisons WHERE status != 'FAIL'").fetchone()
                success_count = row[0] if row else 0
                stats["success_rate"] = round((success_count / stats["total_comparisons"]) * 100, 1)
            
            row = cursor.execute("SELECT AVG(total_pages) FROM comparisons").fetchone()
            stats["avg_pages"] = round(row[0], 1) if row and row[0] else 0
            
            rows = cursor.execute("""
                SELECT substr(timestamp, 1, 10) as day, COUNT(*) as count 
                FROM comparisons GROUP BY day ORDER BY day DESC LIMIT 30
            """).fetchall()
            stats["activity_trend"] = [{"date": r["day"], "count": r["count"]} for r in rows][::-1]
            
            row = cursor.execute("""
                SELECT 
                    SUM(CASE WHEN total_pages <= 10 THEN 1 ELSE 0 END) as small,
                    SUM(CASE WHEN total_pages > 10 AND total_pages <= 50 THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN total_pages > 50 THEN 1 ELSE 0 END) as large
                FROM comparisons
            """).fetchone()
            if row:
                stats["page_distribution"] = {"small": row[0] or 0, "medium": row[1] or 0, "large": row[2] or 0}
    except Exception as e:
        logger.error("Failed to fetch stats: %s", e)
    return stats

def get_all_comparisons(status_filter=None, start_date=None, end_date=None):
    query = "SELECT id, timestamp, original_filename, revised_filename, total_pages, status, report_url FROM comparisons WHERE 1=1"
    params = []
    if status_filter: query += " AND status = ?"; params.append(status_filter)
    if start_date: query += " AND substr(timestamp, 1, 10) >= ?"; params.append(start_date)
    if end_date: query += " AND substr(timestamp, 1, 10) <= ?"; params.append(end_date)
    query += " ORDER BY id DESC"
    with get_db(row_factory=sqlite3.Row) as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]

# --- Requalification Functions ---

def create_requal_session(name, pair_count):
    with get_db() as conn:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute("INSERT INTO requalification_sessions (name, created_at, pair_count, status) VALUES (?, ?, ?, 'IN_PROGRESS')", (name, ts, pair_count))
        conn.commit()
        return cursor.lastrowid

def add_requal_pair(session_id, pair_idx, original, revised, pages, status, result_json=None):
    with get_db() as conn:
        conn.execute("INSERT INTO requalification_pairs (session_id, pair_index, original_filename, revised_filename, total_pages, status, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (session_id, pair_idx, original, revised, pages, status, result_json))
        conn.commit()

def update_requal_session_status(session_id: int, status: str):
    with get_db() as conn:
        conn.execute("UPDATE requalification_sessions SET status = ? WHERE id = ?", (status, session_id))
        conn.commit()

def get_requal_sessions():
    with get_db(row_factory=sqlite3.Row) as conn:
        return [dict(r) for r in conn.execute("""
            SELECT s.*, COUNT(p.id) as completed_pairs, SUM(CASE WHEN p.status IN ('PASS', 'NO CHANGES') THEN 1 ELSE 0 END) as passed_pairs
            FROM requalification_sessions s LEFT JOIN requalification_pairs p ON s.id = p.session_id
            GROUP BY s.id ORDER BY s.id DESC
        """).fetchall()]

def get_requal_session_detail(session_id):
    with get_db(row_factory=sqlite3.Row) as conn:
        session = conn.execute("SELECT * FROM requalification_sessions WHERE id = ?", (session_id,)).fetchone()
        if not session: return None
        pairs = conn.execute("SELECT * FROM requalification_pairs WHERE session_id = ? ORDER BY pair_index", (session_id,)).fetchall()
        res = dict(session)
        res["pairs"] = [dict(p) for p in pairs]
        for p in res["pairs"]:
            p["result_data"] = json.loads(p["result_json"]) if p.get("result_json") else None
            del p["result_json"]
        return res

def delete_requal_session(session_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM requalification_pairs WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM requalification_sessions WHERE id = ?", (session_id,))
        conn.commit()

# --- Scope Validation Functions ---

def add_scope_validation(document_filename, scope_items_json, matched_count, total_count, coverage_pct, result_json=None):
    with get_db() as conn:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO scope_validations (timestamp, document_filename, scope_items_json, matched_count, total_count, coverage_pct, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (ts, document_filename, scope_items_json, matched_count, total_count, coverage_pct, result_json))
        conn.execute("DELETE FROM scope_validations WHERE id NOT IN (SELECT id FROM scope_validations ORDER BY id DESC LIMIT ?)", (MAX_SCOPE_VALIDATIONS,))
        conn.commit()

def get_scope_validations():
    with get_db(row_factory=sqlite3.Row) as conn:
        return [dict(r) for r in conn.execute("SELECT id, timestamp, document_filename, matched_count, total_count, coverage_pct FROM scope_validations ORDER BY id DESC").fetchall()]

def get_scope_validation_detail(record_id):
    with get_db(row_factory=sqlite3.Row) as conn:
        row = conn.execute("SELECT * FROM scope_validations WHERE id = ?", (record_id,)).fetchone()
        if not row: return None
        res = dict(row)
        res["result_data"] = json.loads(res["result_json"]) if res.get("result_json") else None
        return res

def delete_scope_validation(record_id):
    with get_db() as conn:
        conn.execute("DELETE FROM scope_validations WHERE id = ?", (record_id,))
        conn.commit()

# --- API Key Functions ---

def create_api_key(owner):
    key = "fsb_" + secrets.token_urlsafe(32)
    with get_db() as conn:
        conn.execute("INSERT INTO api_keys (key_value, owner, created_at) VALUES (?, ?, ?)", (key, owner, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    return key

def validate_api_key(key):
    with get_db() as conn:
        return conn.execute("SELECT id FROM api_keys WHERE key_value = ? AND is_active = 1", (key,)).fetchone() is not None
