import os
import re
import asyncio
from typing import Dict, Any
from playwright.async_api import async_playwright

from services.intelligence_service.form_qa_agent import FormQAAgent
from services.intelligence_service.ats_adapters import get_adapter_for_job


class JobApplier:
    def __init__(self, resume_path: str = "data/SURYA.pdf", model_name: str = "llama3.1"):
        self.resume_path = os.path.abspath(resume_path)
        self.screenshots_dir = os.path.abspath("data/screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)
        self.qa_agent = FormQAAgent(model_name=model_name)

    async def preview_application(self, job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        """Fills the form in headless mode to give you an instant preview."""
        apply_url = job.get("apply_url") or job.get("url")
        if not apply_url:
            return {"status": "error", "message": "No apply URL found."}

        ats_provider = (job.get("ats_provider") or "").lower()

        if "workday" in ats_provider or "myworkdayjobs" in apply_url:
            return {
                "status": "held",
                "message": "Workday applications are on hold for dedicated login handling."
            }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                print(f"[Applier] Navigating to {apply_url}...")
                await page.goto(apply_url, timeout=40000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                adapter = get_adapter_for_job(ats_provider, page, self.resume_path, self.qa_agent)
                fill_res = await adapter.fill_form(job, profile)

                clean_comp = re.sub(r'[^a-zA-Z0-9]', '_', job.get('company', 'company')).lower()[:15]
                shot_name = f"preview_{clean_comp}_{int(asyncio.get_event_loop().time())}.png"
                shot_path = os.path.join(self.screenshots_dir, shot_name)

                await page.wait_for_timeout(1000)
                await page.screenshot(path=shot_path, full_page=True)

                await browser.close()
                return {
                    "status": "success",
                    "ats_used": adapter.__class__.__name__,
                    "resume_attached": fill_res.get("resume_attached", False),
                    "mapped_fields": fill_res.get("mapped_fields", []),
                    "qa_records": fill_res.get("qa_records", []),
                    "screenshot_url": f"/api/screenshots/{shot_name}"
                }

            except Exception as e:
                await browser.close()
                return {"status": "error", "message": str(e)}

    async def submit_application(self, job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Launches VISIBLE (headed) browser so you can solve CAPTCHA puzzles if prompted,
        and waits until the actual confirmation page is verified.
        """
        apply_url = job.get("apply_url") or job.get("url")
        if not apply_url:
            return {"status": "error", "message": "No apply URL found."}

        ats_provider = (job.get("ats_provider") or "").lower()

        async with async_playwright() as p:
            # Launch in HEADED mode so CAPTCHA challenges are visible and solvable
            browser = await p.chromium.launch(headless=False, slow_mo=50)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                print(f"[Submitter] Opening live browser for {job.get('company')}...")
                await page.goto(apply_url, timeout=45000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                adapter = get_adapter_for_job(ats_provider, page, self.resume_path, self.qa_agent)
                await adapter.fill_form(job, profile)

                # Perform submit and wait for true confirmation
                submit_res = await adapter.submit()

                clean_comp = re.sub(r'[^a-zA-Z0-9]', '_', job.get('company', 'company')).lower()[:15]
                shot_name = f"submitted_{clean_comp}_{int(asyncio.get_event_loop().time())}.png"
                shot_path = os.path.join(self.screenshots_dir, shot_name)
                await page.screenshot(path=shot_path, full_page=True)

                await browser.close()

                if submit_res.get("confirmed"):
                    return {
                        "status": "success",
                        "message": submit_res.get("message"),
                        "screenshot_url": f"/api/screenshots/{shot_name}"
                    }
                else:
                    return {
                        "status": "error",
                        "message": submit_res.get("message"),
                        "screenshot_url": f"/api/screenshots/{shot_name}"
                    }

            except Exception as e:
                await browser.close()
                return {"status": "error", "message": str(e)}