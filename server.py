import os
import json
import time
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional

from services.intelligence_service.vector_matcher import VectorMatcher

app = FastAPI(title="Autonomous Job Agent - Local Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

matcher = VectorMatcher()

PROFILE_PATH = "config/profile.json"
CACHE_DIR = "data/cache"


@app.get("/api/profile")
def get_profile():
    if not os.path.exists(PROFILE_PATH):
        raise HTTPException(status_code=404, detail="config/profile.json not found")
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/stats")
def get_stats():
    jobs = matcher.load_cache_jobs(CACHE_DIR)
    return {
        "total_jobs_in_cache": len(jobs),
        "cache_directory": CACHE_DIR,
        "fastembed_model": matcher.model_name
    }


@app.get("/api/match/stream")
async def match_jobs_stream(
    keywords: str = "",
    location: str = "",
    ats: str = "all",
    threshold: float = 0.50,
    top_k: Optional[int] = None
):
    """Streams real-time execution logs and all ranked results via SSE."""

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
        yield f"data: {json.dumps({'type': 'log', 'msg': f'[PROFILE] Profile loaded: {candidate_name}'})}\n\n"

        yield f"data: {json.dumps({'type': 'log', 'msg': f'[CACHE] Reading chunks from {CACHE_DIR}...'})}\n\n"
        t0 = time.time()
        jobs = matcher.load_cache_jobs(CACHE_DIR)
        t_cache = time.time() - t0
        yield f"data: {json.dumps({'type': 'log', 'msg': f'[CACHE] Loaded {len(jobs)} total jobs into RAM in {t_cache:.2f}s'})}\n\n"

        # Stage 1: Pre-Filtering
        filtered_jobs = jobs

        if keywords.strip():
            terms = [t.strip().lower() for t in keywords.split(",") if t.strip()]
            filtered_jobs = [
                j for j in filtered_jobs
                if any(t in (j.get("title", "") + " " + j.get("description", "")).lower() for t in terms)
            ]
            yield f"data: {json.dumps({'type': 'log', 'msg': f'[FILTER] Keyword filter matched: {len(filtered_jobs)} jobs'})}\n\n"

        if location.strip():
            loc_term = location.strip().lower()
            filtered_jobs = [j for j in filtered_jobs if loc_term in (j.get("location") or "").lower()]
            yield f"data: {json.dumps({'type': 'log', 'msg': f'[FILTER] Location filter matched: {len(filtered_jobs)} jobs'})}\n\n"

        if ats.strip() and ats != "all":
            ats_term = ats.strip().lower()
            filtered_jobs = [j for j in filtered_jobs if ats_term == (j.get("ats_provider") or "").lower()]
            yield f"data: {json.dumps({'type': 'log', 'msg': f'[FILTER] ATS filter matched: {len(filtered_jobs)} jobs'})}\n\n"

        if not filtered_jobs:
            yield f"data: {json.dumps({'type': 'log', 'msg': '[!] No jobs matched pre-filters.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'results': [], 'matched': 0, 'prefiltered': 0})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'log', 'msg': f'[VECTOR] Computing 384-d Cosine Similarity for {len(filtered_jobs)} candidates...'})}\n\n"

        # Stage 2: FastEmbed Vector Scoring across ALL matched jobs
        t_vec = time.time()
        k_limit = top_k if (top_k and top_k > 0) else len(filtered_jobs)

        results = matcher.score_jobs(
            profile_text=profile_doc,
            jobs=filtered_jobs,
            threshold=threshold,
            top_k=k_limit,
            batch_size=128
        )
        t_vec_elapsed = time.time() - t_vec

        yield f"data: {json.dumps({'type': 'log', 'msg': f'[VECTOR] Scoring complete in {t_vec_elapsed:.2f}s. {len(results)} positions >= {int(threshold * 100)}%'})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'results': results, 'matched': len(results), 'total_in_cache': len(jobs), 'prefiltered': len(filtered_jobs)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)