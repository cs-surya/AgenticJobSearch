# probe.py - Isolated Probe Script
import os
import json
import httpx

print("=== Diagnostic Probe Starting ===")

# 1. Inspect Local Directory & Files
search_dirs = ["data/ats_sources", "data/atssources"]
found_dir = None
for d in search_dirs:
    if os.path.exists(d):
        found_dir = d
        break

if not found_dir:
    print(f"[FAIL] Neither 'data/ats_sources' nor 'data/atssources' directory was found.")
else:
    print(f"[OK] Found directory: {found_dir}")
    files = os.listdir(found_dir)
    print(f"     Found files: {files}")

    # Inspect greenhouse_companies.json structure
    gh_file = os.path.join(found_dir, "greenhouse_companies.json")
    if os.path.exists(gh_file):
        with open(gh_file, "r") as f:
            sample_data = json.load(f)
            data_type = type(sample_data).__name__
            length = len(sample_data)
            preview = sample_data[:3] if isinstance(sample_data, list) else list(sample_data.keys())[:3]
            print(f"[OK] greenhouse_companies.json loaded. Type: {data_type}, Count: {length}")
            print(f"     Sample items: {preview}")
    else:
        print("[WARN] greenhouse_companies.json not in folder.")

# 2. Test Live Network Request (Greenhouse & Lever live public endpoints)
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

print("\n--- Testing Live API Handshake ---")
test_companies = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/stripe/jobs"),
    ("lever", "https://api.lever.co/v0/postings/palantir?mode=json"),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/openai")
]

for provider, url in test_companies:
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            resp = client.get(url)
            print(f"[{provider.upper()}] Status: {resp.status_code} | Raw Length: {len(resp.text)} chars")
            if resp.status_code == 200:
                data = resp.json()
                if provider == "greenhouse":
                    jobs = data.get("jobs", [])
                    print(
                        f"   ✓ Extracted {len(jobs)} active jobs. First title: '{jobs[0]['title'] if jobs else 'N/A'}'")
                elif provider == "lever":
                    print(
                        f"   ✓ Extracted {len(data)} active jobs. First title: '{data[0]['text'] if data else 'N/A'}'")
                elif provider == "ashby":
                    jobs = data.get("jobs", [])
                    print(
                        f"   ✓ Extracted {len(jobs)} active jobs. First title: '{jobs[0]['title'] if jobs else 'N/A'}'")
            else:
                print(f"   ✗ Failed with status {resp.status_code}")
    except Exception as e:
        print(f"   ✗ Network/Connection error on {provider}: {e}")

print("\n=== Probe Complete ===")