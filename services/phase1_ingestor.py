import os
import json
import gzip
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

CACHE_DIR = "data/cache"
MANIFEST_PATH = "data/cache/manifest.json"

class JobFilterCriteria(BaseModel):
    target_roles: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    max_days_old: Optional[int] = None
    is_remote_only: bool = False
    excluded_keywords: List[str] = Field(default_factory=list)

class Phase1IngestionEngine:
    def __init__(self, filter_criteria: Optional[JobFilterCriteria] = None, logger_cb: Optional[Callable[[str, str], None]] = None):
        self.filters = filter_criteria or JobFilterCriteria()
        self.logger_cb = logger_cb

    def log(self, message: str, level: str = "info"):
        print(f"[{level.upper()}] {message}")
        if self.logger_cb:
            try:
                self.logger_cb(message, level)
            except Exception:
                pass

    def _matches_filters(self, title: str, location: str, posted_date_str: Optional[str]) -> bool:
        title_lower = (title or "").lower()
        loc_lower = (location or "").lower()

        # 1. Excluded Keywords
        if self.filters.excluded_keywords:
            for ex in self.filters.excluded_keywords:
                clean_ex = ex.strip().lower()
                if clean_ex and clean_ex in title_lower:
                    return False

        # 2. Target Roles (Empty = match all)
        active_roles = [r.strip().lower() for r in self.filters.target_roles if r.strip()]
        if active_roles:
            if not any(role in title_lower for role in active_roles):
                return False

        # 3. Locations (Empty = match all)
        active_locs = [l.strip().lower() for l in self.filters.locations if l.strip()]
        if active_locs:
            matched_loc = any(loc in loc_lower for loc in active_locs)
            if not matched_loc and not (self.filters.is_remote_only and "remote" in loc_lower):
                return False

        if self.filters.is_remote_only and "remote" not in loc_lower:
            return False

        # 4. Date Freshness
        if self.filters.max_days_old is not None and posted_date_str:
            try:
                posted_dt = datetime.fromisoformat(str(posted_date_str).replace("Z", "+00:00"))
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.filters.max_days_old)
                if posted_dt < cutoff:
                    return False
            except Exception:
                pass

        return True

    def load_from_local_cache(self) -> List[Dict[str, Any]]:
        """Reads local offline gzipped chunks in memory in sub-seconds."""
        if not os.path.exists(MANIFEST_PATH):
            self.log("No local offline cache found. Please run the offline cron scraper first.", "warning")
            return []

        with open(MANIFEST_PATH, "r") as f:
            manifest = json.load(f)

        chunks = manifest.get("chunks", [])
        total_cached = manifest.get("total_jobs", 0)
        last_updated = manifest.get("last_updated", "Unknown")

        self.log(f"Reading local cache ({total_cached} total jobs across {len(chunks)} chunks, synced at {last_updated})...", "info")

        matched_jobs = []

        for chunk_file in chunks:
            chunk_path = os.path.join(CACHE_DIR, chunk_file)
            if os.path.exists(chunk_path):
                try:
                    with gzip.open(chunk_path, "rt", encoding="utf-8") as gz:
                        jobs_list = json.load(gz)
                        for item in jobs_list:
                            if self._matches_filters(item.get("title", ""), item.get("location", ""), item.get("posted_date")):
                                matched_jobs.append(item)
                except Exception as e:
                    self.log(f"Error reading {chunk_file}: {e}", "warning")

        self.log(f"Instant filter complete! {len(matched_jobs)} matching jobs loaded in RAM.", "success")
        return matched_jobs