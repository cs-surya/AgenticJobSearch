import asyncio
import json
import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from services.phase1_ingestor import Phase1IngestionEngine, JobFilterCriteria
from cron_scrapper import run_offline_scraper

app = FastAPI(title="Job Agent Dashboard - Phase 1 Offline")

os.makedirs("templates", exist_ok=True)
templates = Jinja2Templates(directory="templates")
CONFIG_PATH = "config/filter_config.json"
MANIFEST_PATH = "data/cache/manifest.json"

SESSION_JOBS: List[Dict[str, Any]] = []

class LogBroker:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def emit(self, msg: str, level: str = "info"):
        payload = json.dumps({"message": msg, "level": level})
        for ws in self.connections:
            try:
                await ws.send_text(payload)
            except Exception:
                pass

broker = LogBroker()

class FilterRequest(BaseModel):
    target_roles: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    max_days_old: Optional[int] = None
    is_remote_only: bool = False
    excluded_keywords: List[str] = Field(default_factory=list)

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/cache-info")
async def get_cache_info():
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_jobs": 0, "total_chunks": 0, "last_updated": "Never"}

@app.get("/api/filters")
async def get_filters():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "target_roles": [],
        "locations": [],
        "max_days_old": None,
        "is_remote_only": False,
        "excluded_keywords": []
    }

@app.post("/api/filters/save")
async def save_filters(filters: FilterRequest):
    os.makedirs("config", exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(filters.model_dump(), f, indent=2)
    return {"status": "saved"}

@app.get("/api/jobs")
async def get_jobs():
    return SESSION_JOBS[:400]

@app.post("/api/actions/filter")
async def filter_local_jobs(req: FilterRequest, bg: BackgroundTasks):
    global SESSION_JOBS
    loop = asyncio.get_running_loop()

    def sync_logger(msg: str, lvl: str = "info"):
        asyncio.run_coroutine_threadsafe(broker.emit(msg, lvl), loop)

    async def run_filter():
        global SESSION_JOBS
        criteria = JobFilterCriteria(
            target_roles=req.target_roles,
            locations=req.locations,
            max_days_old=req.max_days_old,
            is_remote_only=req.is_remote_only,
            excluded_keywords=req.excluded_keywords
        )
        engine = Phase1IngestionEngine(filter_criteria=criteria, logger_cb=sync_logger)
        SESSION_JOBS = await loop.run_in_executor(None, engine.load_from_local_cache)

    bg.add_task(run_filter)
    return {"status": "started"}

@app.post("/api/actions/offline-sync")
async def trigger_offline_sync(bg: BackgroundTasks):
    loop = asyncio.get_running_loop()

    async def run_sync():
        await broker.emit("Starting full offline background scraper across 50,000+ boards...", "info")
        try:
            total = await run_offline_scraper()
            await broker.emit(f"Offline Sync Completed! Cached {total} jobs locally.", "success")
        except Exception as e:
            await broker.emit(f"Offline Sync Error: {e}", "warning")

    bg.add_task(run_sync)
    return {"status": "sync_started"}

@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await broker.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        broker.disconnect(ws)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_ui:app", host="127.0.0.1", port=8000, reload=True)