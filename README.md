```markdown
# 🤖 AgenticJobSearch (Phase 1)

> **High-Throughput Autonomous Job Ingestion, Cache-Optimized Indexing & Zero-Infrastructure Client-Side Search Engine.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-brightgreen?style=for-the-badge&logo=github)](https://cs-surya.github.io/AgenticJobSearch/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Phase-1%20Completed-success?style=for-the-badge)](#-phase-1-features--architecture)
[![Roadmap](https://img.shields.io/badge/Phase-2%20Proposal-orange?style=for-the-badge)](#-phase-2-proposal-intelligent-match--autonomous-apply-engine)

---

## 🌐 Live Interactive Testing Page

Test and search the ingested multi-ATS job dataset directly in your browser without spinning up a local server:

👉 **[Launch Live Static Dashboard](https://cs-surya.github.io/AgenticJobSearch/)**

---

## 📌 What is AgenticJobSearch?

**AgenticJobSearch** is an intelligent, end-to-end job discovery and autonomous application framework.

* **Phase 1 (Current Branch):** Focuses on automated, scheduled ingestion across major ATS platforms (Greenhouse, Lever, Ashby, and Direct Board endpoints), compressing and caching thousands of jobs into structured chunks that can be searched entirely on the client-side with zero backend hosting costs.
* **Phase 2 (Upcoming):** Integrates local vector embeddings (`FastEmbed`), local LLM RAG (`Ollama / llama3.1`), dynamic PDF resume tailoring (`Typst`), and Playwright browser automation for one-click verified applications.

---

## 🚀 Phase 1: Features & Architecture


```

```
                              PHASE 1 PIPELINE

```

┌─────────────────┐       ┌──────────────────────┐       ┌────────────────────────┐
│  ATS Providers  │       │  Scheduled Scrapers  │       │ Gzip Chunk Aggregator  │
│ • Greenhouse    │ ────► │ • Rate-Limited API   │ ────► │ • Chunk partitioning   │
│ • Lever         │       │ • Cron / GH Actions  │       │ • Compression (.gz)    │
│ • Ashby / Direct│       │ • De-duplication     │       │ • Metadata extraction  │
└─────────────────┘       └──────────────────────┘       └────────────────────────┘
│
▼
┌────────────────────────┐
│  Static Web Dashboard  │
│  (GitHub Pages Hosted) │
│ • Stream decompression │
│ • Instant JS filtering │
│ • Zero backend hosting │
└────────────────────────┘

```

### 1. Multi-ATS Ingestion Engine
* High-throughput asynchronous scrapers built to ingest job listings from major Applicant Tracking Systems:
  * **Greenhouse** (`boards.greenhouse.io`, `job-boards.greenhouse.io`)
  * **Lever** (`jobs.lever.co`)
  * **Ashby** (`jobs.ashbyhq.com`)
  * Direct custom company career feeds.
* Standardized payload schema extracting job ID, title, company, clean description, location, apply URL, and provider tags.

### 2. Compressed Chunk Caching
* Jobs are partitioned into compressed JSON chunks (`data/cache/jobs_chunk_*.json.gz`).
* Keeps repository footprints light while enabling high-concurrency client-side stream decompression (`DecompressionStream`) directly in the browser.

### 3. Client-Side Zero-Cost Search Platform
* Static HTML5/CSS3/Vanilla JS single-page interface hosted on **GitHub Pages**.
* Client-side keyword search, location matching, ATS board filtering, and pagination over thousands of listings without requiring a live cloud backend or database.

### 4. Automated Scraping & Cron CI/CD
* Configured for headless automated periodic updates via GitHub Actions or local cron triggers to keep the active job index fresh.

---

## 📁 Repository Structure

```text
AgenticJobSearch/
├── .github/
│   └── workflows/                # Automated scraping & cache update actions
├── data/
│   └── cache/                    # Partitioned & compressed job chunks (.json.gz)
├── services/
│   └── scrapers/                 # Modular ATS scraper engines
│       ├── greenhouse_scraper.py
│       ├── lever_scraper.py
│       ├── ashby_scraper.py
│       └── base_scraper.py
├── scripts/
│   ├── run_scrapers.py           # Ingestion orchestrator
│   └── consolidate_cache.py      # Cache chunk compressor & aggregator
├── static/
│   ├── index.html                # Client-side web dashboard
│   ├── style.css                 # Clean dark-mode UI
│   └── app.js                    # Chunk loader, stream decompressor & filter engine
└── requirements.txt

```

---

## 🛠️ Quick Start (Local Setup)

### 1. Clone & Install Dependencies

```bash
git clone [https://github.com/cs-surya/AgenticJobSearch.git](https://github.com/cs-surya/AgenticJobSearch.git)
cd AgenticJobSearch

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

```

### 2. Run the Scrapers

To fetch the latest jobs and regenerate the cache chunks:

```bash
python scripts/run_scrapers.py

```

### 3. Launch Local Static Preview

You can run any local static file server:

```bash
# Using Python built-in HTTP server
cd static
python -m http.server 8000

```

Open `http://localhost:8000` in your browser.

---

## 🔮 Phase 2 Proposal: Intelligent Match & Autonomous Apply Engine

Phase 2 advances the project from a static search index into an **Agentic AI Job Application System**:

| Feature | Description |
| --- | --- |
| **384-d Semantic Vector Matcher** | Uses `FastEmbed` (`BAAI/bge-small-en-v1.5`) to compute vector cosine similarity between candidate resume/skills (`config/profile.json`) and raw job descriptions in real-time. |
| **Local LLM Form Q&A (`Ollama`)** | Connects `llama3.1` to dynamically answer novel open-ended screening questions, salary expectations, and work authorizations strictly grounded in candidate facts. |
| **Universal DOM Automation (`Playwright`)** | Pierces nested iframes, Shadow DOMs, React-Select comboboxes, and places autocomplete APIs (Country code `+91`, city autocomplete) with native React state bindings. |
| **Human-in-the-Loop Verification** | Side-by-side **Preview & Verify Modal** capturing full-page headless snapshots before triggering visible live browser submission. |
| **SQLite Application Tracker** | Persistent tracking in `data/applications.db` recording status (`PREVIEWING`, `APPLIED`, `FAILED`), timestamps, and submission proof screenshots. |
| **Dynamic Typst Resume Compiler** | Real-time resume customization engine rendering job-tailored PDF variants on the fly. |

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.

```

```
