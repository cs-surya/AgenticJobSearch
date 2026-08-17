# tests/test_phase1.py
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from services.phase1_ingestor import Phase1IngestionEngine, JobFilterCriteria


def run_test():
    print("=== Testing Phase 1: Local Ingestion & Filter ===")

    test_filter = JobFilterCriteria(
        target_roles=["Engineer", "Developer", "Software", "Backend", "Full Stack"],
        locations=[],  # Empty = match any location for initial test
        max_days_old=None,  # No age cutoff for initial test
        is_remote_only=False,
        excluded_keywords=[]
    )

    print("Target roles to filter:", test_filter.target_roles)
    engine = Phase1IngestionEngine(filter_criteria=test_filter, max_workers=10)

    print("Fetching jobs from first 5 companies per ATS...")
    saved_count = engine.execute_filtered_ingestion(max_companies_per_ats=5)
    print(f"\n[OK] Successfully saved {saved_count} jobs to SQLite database!\n")

    conn = sqlite3.connect("data/jobs.db")
    c = conn.cursor()
    c.execute("SELECT ats_provider, company, title, location FROM filtered_job_queue LIMIT 10")
    rows = c.fetchall()
    conn.close()

    print("Sample Ingested Rows from SQLite:")
    for r in rows:
        print(f"  [{r[0].upper()}] {r[1]} -> {r[2]} ({r[3]})")


if __name__ == "__main__":
    run_test()