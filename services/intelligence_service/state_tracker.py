import sqlite3
import os
import json
from typing import Dict, Any, Optional, List

class StateTracker:
    def __init__(self, db_path: str = "data/applications.db"):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    job_id TEXT PRIMARY KEY,
                    company TEXT,
                    title TEXT,
                    apply_url TEXT,
                    ats_provider TEXT,
                    similarity_score REAL,
                    status TEXT,
                    qa_records TEXT,
                    screenshot_url TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_applied_or_in_progress(self, job_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM applications WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row and row[0] in ("APPLIED", "IN_PROGRESS"):
                return True
        return False

    def update_status(
        self,
        job: Dict[str, Any],
        status: str,
        qa_records: Optional[List[Dict[str, Any]]] = None,
        screenshot_url: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        job_id = job.get("job_id") or f"{job.get('company')}_{job.get('title')}_{job.get('apply_url')}"
        qa_json = json.dumps(qa_records) if qa_records else None

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO applications (
                    job_id, company, title, apply_url, ats_provider, similarity_score,
                    status, qa_records, screenshot_url, error_message, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    qa_records = coalesce(excluded.qa_records, applications.qa_records),
                    screenshot_url = coalesce(excluded.screenshot_url, applications.screenshot_url),
                    error_message = coalesce(excluded.error_message, applications.error_message),
                    updated_at = CURRENT_TIMESTAMP
            """, (
                job_id,
                job.get("company", ""),
                job.get("title", ""),
                job.get("apply_url") or job.get("url", ""),
                job.get("ats_provider", "direct"),
                job.get("match_percentage", 0.0),
                status,
                qa_json,
                screenshot_url,
                error_message
            ))
            conn.commit()

    def get_stats(self) -> Dict[str, int]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")
            rows = cursor.fetchall()
            return {status: count for status, count in rows}