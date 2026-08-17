import os
import json
import gzip
import asyncio
import httpx
import hashlib
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

CACHE_DIR = "data/cache"
SOURCES_DIR = "data/ats_sources"
CHUNK_SIZE = 5000  # Number of jobs per compressed chunk
CONCURRENCY_LIMIT = 120  # Parallel async connection pool

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}


def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    return BeautifulSoup(raw_html, "html.parser").get_text(separator=" ", strip=True)


def generate_id(provider: str, company: str, ext_id: str) -> str:
    return hashlib.md5(f"{provider}:{company}:{ext_id}".encode()).hexdigest()


def _load_company_slugs(filename: str) -> List[Any]:
    for base_dir in [SOURCES_DIR, "data/atssources"]:
        path = os.path.join(base_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        return raw
                    elif isinstance(raw, dict):
                        return list(raw.keys())
            except Exception:
                pass
    return []


# --- Asynchronous ATS Fetchers ---

async def fetch_greenhouse(client: httpx.AsyncClient, company: str, sem: asyncio.Semaphore) -> List[Dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
    async with sem:
        try:
            r = await client.get(url, timeout=7.0)
            if r.status_code == 200:
                jobs = []
                for item in r.json().get("jobs", []):
                    title = item.get("title", "")
                    loc = item.get("location", {}).get("name", "Unknown")
                    jobs.append({
                        "id": generate_id("greenhouse", company, str(item["id"])),
                        "ats_provider": "greenhouse", "company": company,
                        "title": title, "location": loc,
                        "apply_url": item.get("absolute_url", ""),
                        "description": clean_html(item.get("content", ""))[:1200],
                        "posted_date": item.get("updated_at")
                    })
                return jobs
        except Exception:
            pass
    return []


async def fetch_lever(client: httpx.AsyncClient, company: str, sem: asyncio.Semaphore) -> List[Dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    async with sem:
        try:
            r = await client.get(url, timeout=7.0)
            if r.status_code == 200:
                jobs = []
                for item in r.json():
                    title = item.get("text", "")
                    loc = item.get("categories", {}).get("location", "Unknown")
                    desc = item.get("descriptionPlain", "") or clean_html(item.get("description", ""))
                    jobs.append({
                        "id": generate_id("lever", company, str(item["id"])),
                        "ats_provider": "lever", "company": company,
                        "title": title, "location": loc,
                        "apply_url": item.get("applyUrl", ""),
                        "description": desc[:1200],
                        "posted_date": str(item.get("createdAt")) if item.get("createdAt") else None
                    })
                return jobs
        except Exception:
            pass
    return []


async def fetch_ashby(client: httpx.AsyncClient, company: str, sem: asyncio.Semaphore) -> List[Dict[str, Any]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company}"
    async with sem:
        try:
            r = await client.get(url, timeout=7.0)
            if r.status_code == 200:
                jobs = []
                for item in r.json().get("jobs", []):
                    title = item.get("title", "")
                    loc = item.get("location", "Unknown")
                    jobs.append({
                        "id": generate_id("ashby", company, str(item["id"])),
                        "ats_provider": "ashby", "company": company,
                        "title": title, "location": loc,
                        "apply_url": item.get("jobUrl", ""),
                        "description": clean_html(item.get("descriptionHtml", ""))[:1200],
                        "posted_date": item.get("publishedAt")
                    })
                return jobs
        except Exception:
            pass
    return []


async def fetch_bamboohr(client: httpx.AsyncClient, company: str, sem: asyncio.Semaphore) -> List[Dict[str, Any]]:
    url = f"https://{company}.bamboohr.com/careers/list"
    async with sem:
        try:
            r = await client.get(url, timeout=7.0)
            if r.status_code == 200:
                jobs = []
                for item in r.json().get("result", []):
                    title = item.get("jobOpeningName", "")
                    loc = f"{item.get('location', {}).get('city', '')}, {item.get('location', {}).get('state', '')}"
                    job_id = str(item.get("id", ""))
                    jobs.append({
                        "id": generate_id("bamboohr", company, job_id),
                        "ats_provider": "bamboohr", "company": company,
                        "title": title, "location": loc,
                        "apply_url": f"https://{company}.bamboohr.com/careers/{job_id}",
                        "description": clean_html(item.get("jobDescription", ""))[:1200],
                        "posted_date": str(item.get("dateCreated")) if item.get("dateCreated") else None
                    })
                return jobs
        except Exception:
            pass
    return []


async def fetch_workday(client: httpx.AsyncClient, workday_info: Any, sem: asyncio.Semaphore) -> List[Dict[str, Any]]:
    async with sem:
        try:
            if isinstance(workday_info, dict):
                domain = workday_info.get("domain", "")
                path = workday_info.get("path", "")
                company_name = workday_info.get("name", domain.split(".")[0] if domain else "workday_co")
            else:
                company_name = str(workday_info)
                domain = f"{company_name}.wd1.myworkdayjobs.com"
                path = company_name

            if not domain:
                return []

            url = f"https://{domain}/wday/cxs/{company_name}/{path}/jobs"
            payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
            r = await client.post(url, json=payload, timeout=7.0)
            if r.status_code == 200:
                jobs = []
                for item in r.json().get("jobPostings", []):
                    title = item.get("title", "")
                    loc = item.get("locationsText", "Unknown")
                    ext_path = item.get("externalPath", "")
                    jobs.append({
                        "id": generate_id("workday", company_name, ext_path),
                        "ats_provider": "workday", "company": company_name,
                        "title": title, "location": loc,
                        "apply_url": f"https://{domain}{ext_path}",
                        "description": title,
                        "posted_date": item.get("postedOn")
                    })
                return jobs
        except Exception:
            pass
    return []


async def fetch_icims(client: httpx.AsyncClient, company: str, sem: asyncio.Semaphore) -> List[Dict[str, Any]]:
    url = f"https://careers-{company}.icims.com/jobs/search?in_iframe=1&schema=true"
    async with sem:
        try:
            r = await client.get(url, timeout=7.0)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                jobs = []
                for card in soup.select(".iCIMS_JobListItem, .row"):
                    title_el = card.select_one(".iCIMS_JobHeader, h2, a")
                    loc_el = card.select_one(".iCIMS_JobLocation, .header")
                    if title_el:
                        title = title_el.get_text(strip=True)
                        loc = loc_el.get_text(strip=True) if loc_el else "Unknown"
                        href = title_el.get("href", "")
                        jobs.append({
                            "id": generate_id("icims", company, href),
                            "ats_provider": "icims", "company": company,
                            "title": title, "location": loc,
                            "apply_url": href if href.startswith(
                                "http") else f"https://careers-{company}.icims.com{href}",
                            "description": title,
                            "posted_date": None
                        })
                return jobs
        except Exception:
            pass
    return []


# --- Offline Batch Orchestrator ---

async def run_offline_scraper(limit_per_ats: Optional[int] = None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting High-Speed Offline ATS Scraper...")

    gh = _load_company_slugs("greenhouse_companies.json")
    lever = _load_company_slugs("lever_companies.json")
    ashby = _load_company_slugs("ashby_companies.json")
    bamboo = _load_company_slugs("bamboohr_companies.json")
    workday = _load_company_slugs("workday_companies.json")
    icims = _load_company_slugs("icims_companies.json")

    if limit_per_ats:
        gh, lever, ashby, bamboo, workday, icims = gh[:limit_per_ats], lever[:limit_per_ats], ashby[
                                                                                              :limit_per_ats], bamboo[
                                                                                                               :limit_per_ats], workday[
                                                                                                                                :limit_per_ats], icims[
                                                                                                                                                 :limit_per_ats]

    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
    all_jobs = []

    limits = httpx.Limits(max_keepalive_connections=150, max_connections=200)
    async with httpx.AsyncClient(headers=headers, limits=limits, follow_redirects=True) as client:
        tasks = []

        for item in gh:
            slug = item if isinstance(item, str) else item.get("slug") or item.get("name")
            if slug: tasks.append(fetch_greenhouse(client, str(slug), sem))

        for item in lever:
            slug = item if isinstance(item, str) else item.get("slug") or item.get("name")
            if slug: tasks.append(fetch_lever(client, str(slug), sem))

        for item in ashby:
            slug = item if isinstance(item, str) else item.get("slug") or item.get("name")
            if slug: tasks.append(fetch_ashby(client, str(slug), sem))

        for item in bamboo:
            slug = item if isinstance(item, str) else item.get("subdomain") or item.get("slug")
            if slug: tasks.append(fetch_bamboohr(client, str(slug), sem))

        for item in icims:
            slug = item if isinstance(item, str) else item.get("slug") or item.get("name")
            if slug: tasks.append(fetch_icims(client, str(slug), sem))

        for item in workday:
            tasks.append(fetch_workday(client, item, sem))

        total_boards = len(tasks)
        print(f"Dispatched {total_boards} asynchronous board queries...")

        completed = 0
        for future in asyncio.as_completed(tasks):
            res = await future
            if res:
                all_jobs.extend(res)
            completed += 1
            if completed % 500 == 0 or completed == total_boards:
                print(f"  → Polled {completed}/{total_boards} boards | Found {len(all_jobs)} jobs...")

    # Write Gzipped Chunks
    print(f"\nCompressing and saving {len(all_jobs)} jobs into local cache chunks...")
    chunk_files = []

    for i in range(0, len(all_jobs), CHUNK_SIZE):
        chunk_data = all_jobs[i:i + CHUNK_SIZE]
        chunk_filename = f"jobs_chunk_{i // CHUNK_SIZE}.json.gz"
        chunk_path = os.path.join(CACHE_DIR, chunk_filename)

        with gzip.open(chunk_path, "wt", encoding="utf-8") as gz:
            json.dump(chunk_data, gz)
        chunk_files.append(chunk_filename)

    # Write Manifest
    manifest = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(all_jobs),
        "total_chunks": len(chunk_files),
        "chunks": chunk_files
    }
    with open(os.path.join(CACHE_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"[OK] Offline sync finished! {len(all_jobs)} jobs saved into {len(chunk_files)} compressed chunks under `{CACHE_DIR}/`.")
    return len(all_jobs)


if __name__ == "__main__":
    asyncio.run(run_offline_scraper())