import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "history.db"
_db_lock = Lock()

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
                    report_url TEXT
                )
            """)
            conn.commit()
            conn.close()
            logger.info("Database initialized at %s", DB_PATH)
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)

def add_comparison(original, revised, pages, status, report_url=None):
    """Add a new comparison record to the history."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO comparisons (timestamp, original_filename, revised_filename, total_pages, status, report_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (timestamp, original, revised, pages, status, report_url))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error("Failed to add comparison to history: %s", e)

def get_recent_comparisons(limit=10):
    """Fetch the recent comparisons from history."""
    try:
        with _db_lock:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM comparisons ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to fetch comparison history: %s", e)
        return []
