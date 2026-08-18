import os
import json
import time
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from services.intelligence_service.vector_matcher import VectorMatcher
from services.intelligence_service.job_applier import JobApplier
from services.intelligence_service.state_tracker import StateTracker

app = FastAPI(title="JobAgent Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

matcher = VectorMatcher()
applier = JobApplier(resume_path="data/SURYA.pdf", model_name="llama3.1")
tracker = StateTracker()

PROFILE_PATH = "config/profile.json"
CACHE_DIR = "data/cache"
SCREENSHOTS_DIR = "data/screenshots"

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

class JobActionRequest(BaseModel):
    job: Dict[str, Any]

@app.get("/api/profile")
def get_profile():
    if not os.path.exists(PROFILE_PATH):
        raise HTTPException(status_code=404, detail="config/profile.json not found")
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/stats")
def get_stats():
    jobs = matcher.load_cache_jobs(CACHE_DIR)
    app_stats = tracker.get_stats()
    return {
        "total_jobs_in_cache": len(jobs),
        "fastembed_model": matcher.model_name,
        "application_stats": app_stats
    }

@app.get("/api/match/stream")
async def match_jobs_stream(
    keywords: str = "",
    location: str = "",
    ats: str = "all",
    threshold: float = 0.50,
    top_k: Optional[int] = None
):
    async def event_generator():
        yield f"data: {json.dumps({'type': 'log', 'msg': '[INIT] Loading candidate profile from config/profile.json...'})}\n\n"
        await asyncio.sleep(0.02)

        if not os.path.exists(PROFILE_PATH):
            yield f"data: {json.dumps({'type': 'error', 'msg': 'Error: config/profile.json not found!'})}\n\n"
            return

        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            profile_data = json.load(f)

        candidate_name = profile_data.get("personal", {}).get("full_name", "Candidate")
        profile_doc = matcher.build_profile_semantic_doc(profile_data)
        yield f"data: {json.dumps({'type': 'log', 'msg': f'[PROFILE] Loaded: {candidate_name}'})}\n\n"

        jobs = matcher.load_cache_jobs(CACHE_DIR)
        yield f"data: {json.dumps({'type': 'log', 'msg': f'[CACHE] Loaded {len(jobs)} total jobs into RAM'})}\n\n"

        filtered_jobs = jobs
        if keywords.strip():
            terms = [t.strip().lower() for t in keywords.split(",") if t.strip()]
            filtered_jobs = [
                j for j in filtered_jobs
                if any(t in (j.get("title", "") + " " + j.get("description", "")).lower() for t in terms)
            ]

        if location.strip():
            loc_term = location.strip().lower()
            filtered_jobs = [j for j in filtered_jobs if loc_term in (j.get("location") or "").lower()]

        if ats.strip() and ats != "all":
            ats_term = ats.strip().lower()
            filtered_jobs = [j for j in filtered_jobs if ats_term == (j.get("ats_provider") or "").lower()]

        if not filtered_jobs:
            yield f"data: {json.dumps({'type': 'done', 'results': [], 'matched': 0})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'log', 'msg': f'[VECTOR] Computing 384-d Cosine Similarity for {len(filtered_jobs)} candidates...'})}\n\n"

        k_limit = top_k if (top_k and top_k > 0) else len(filtered_jobs)
        results = matcher.score_jobs(
            profile_text=profile_doc,
            jobs=filtered_jobs,
            threshold=threshold,
            top_k=k_limit,
            batch_size=128
        )

        yield f"data: {json.dumps({'type': 'done', 'results': results, 'matched': len(results)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/apply/preview")
async def preview_application_endpoint(req: JobActionRequest):
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    job = req.job
    tracker.update_status(job, "PREVIEWING")
    result = await applier.preview_application(job, profile_data)
    return result

@app.post("/api/apply/approve")
async def approve_and_submit_endpoint(req: JobActionRequest):
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    job = req.job
    tracker.update_status(job, "SUBMITTING")
    result = await applier.submit_application(job, profile_data)

    if result.get("status") in ("success", "warning"):
        tracker.update_status(
            job,
            "APPLIED",
            screenshot_url=result.get("screenshot_url")
        )
    else:
        tracker.update_status(
            job,
            "FAILED",
            error_message=result.get("message")
        )

    return result

@app.get("/api/screenshots/{filename}")
def get_screenshot(filename: str):
    file_path = os.path.join(SCREENSHOTS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(file_path, media_type="image/png")

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)