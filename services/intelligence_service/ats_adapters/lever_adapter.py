import os
import asyncio
from typing import Dict, Any
from playwright.async_api import Page
from services.intelligence_service.ats_adapters.base_adapter import BaseATSAdapter
from services.intelligence_service.captcha_handler import CaptchaHandler

class LeverAdapter(BaseATSAdapter):
    async def fill_form(self, job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        personal = profile.get("personal", {})
        mapped_fields = []
        qa_records = []

        # 1. CAPTCHA Check
        captcha_status = await CaptchaHandler.detect_and_solve_captcha(self.page)

        # 2. Resume Upload
        resume_input = self.page.locator('input[type="file"][name="resume"], input[type="file"]')
        resume_attached = False
        if await resume_input.count() > 0 and os.path.exists(self.resume_path):
            await resume_input.first.set_input_files(self.resume_path)
            resume_attached = True
            mapped_fields.append({"field": "Resume File", "value": os.path.basename(self.resume_path)})

        # 3. Field Targets
        field_targets = [
            ("input[name='name']", "Full Name", personal.get("full_name", "")),
            ("input[name='email']", "Email", personal.get("email", "")),
            ("input[name='phone']", "Phone", personal.get("phone", "")),
            ("input[name='org']", "Current Company", "Independent / Available Immediately"),
            ("input[name='urls[LinkedIn]']", "LinkedIn", personal.get("linkedin", "")),
            ("input[name='urls[GitHub]']", "GitHub", personal.get("github", "")),
            ("input[name='urls[Portfolio]'], input[name='urls[Other]']", "Portfolio", personal.get("website", ""))
        ]

        for selector, label, val in field_targets:
            if not val:
                continue
            loc = self.page.locator(selector)
            if await loc.count() > 0 and await loc.first.is_visible():
                await loc.first.fill(val)
                mapped_fields.append({"field": label, "value": val})

        # 4. Custom Questions
        custom_textareas = self.page.locator('textarea')
        for i in range(await custom_textareas.count()):
            ta = custom_textareas.nth(i)
            if not await ta.is_visible():
                continue
            parent_text = await ta.locator('xpath=..').inner_text()
            q_text = parent_text if len(parent_text) < 250 else "Custom Question"
            ans = self.qa_agent.answer_question(q_text, profile, job)
            await ta.fill(ans)
            qa_records.append({"question": q_text.strip()[:120], "answer": ans})

        return {
            "resume_attached": resume_attached,
            "mapped_fields": mapped_fields,
            "qa_records": qa_records,
            "captcha_info": captcha_status
        }

    async def submit(self) -> bool:
        await CaptchaHandler.detect_and_solve_captcha(self.page)
        submit_btn = self.page.locator('button#btn-submit, button:has-text("Submit application"), input[type="submit"]')
        if await submit_btn.count() > 0 and await submit_btn.first.is_visible():
            await submit_btn.first.scroll_into_view_if_needed()
            await submit_btn.first.click(force=True)
            await asyncio.sleep(2)
            await CaptchaHandler.detect_and_solve_captcha(self.page)
            return True
        return False