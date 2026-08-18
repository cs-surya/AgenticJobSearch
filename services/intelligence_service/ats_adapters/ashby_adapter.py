import os
from typing import Dict, Any
from playwright.async_api import Page
from services.intelligence_service.ats_adapters.base_adapter import BaseATSAdapter

class AshbyAdapter(BaseATSAdapter):
    async def fill_form(self, job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        personal = profile.get("personal", {})
        first_name = personal.get("full_name", "").split()[0]
        last_name = " ".join(personal.get("full_name", "").split()[1:]) or first_name

        mapped_fields = []
        qa_records = []

        # 1. Resume Input
        resume_input = self.page.locator('input[type="file"]')
        resume_attached = False
        if await resume_input.count() > 0 and os.path.exists(self.resume_path):
            await resume_input.first.set_input_files(self.resume_path)
            resume_attached = True

        # 2. Text Inputs by Label/Placeholder
        field_targets = [
            ("input[name*='name' i], input[placeholder*='name' i]", "Full Name", personal.get("full_name", "")),
            ("input[name*='email' i], input[placeholder*='email' i]", "Email", personal.get("email", "")),
            ("input[name*='phone' i], input[placeholder*='phone' i]", "Phone", personal.get("phone", "")),
            ("input[name*='linkedin' i], input[placeholder*='linkedin' i]", "LinkedIn", personal.get("linkedin", "")),
            ("input[name*='github' i], input[placeholder*='github' i]", "GitHub", personal.get("github", ""))
        ]

        for selector, label, val in field_targets:
            if not val:
                continue
            loc = self.page.locator(selector)
            if await loc.count() > 0 and await loc.first.is_visible():
                await loc.first.fill(val)
                mapped_fields.append({"field": label, "value": val})

        # 3. Dynamic Textareas
        textareas = self.page.locator('textarea')
        for i in range(await textareas.count()):
            ta = textareas.nth(i)
            if not await ta.is_visible():
                continue
            q_text = await ta.get_attribute("aria-label") or await ta.get_attribute("placeholder") or "Application Question"
            ans = self.qa_agent.answer_question(q_text, profile, job)
            await ta.fill(ans)
            qa_records.append({"question": q_text.strip()[:120], "answer": ans})

        return {
            "resume_attached": resume_attached,
            "mapped_fields": mapped_fields,
            "qa_records": qa_records
        }

    async def submit(self) -> bool:
        submit_btn = self.page.locator('button[type="submit"], button:has-text("Submit Application")')
        if await submit_btn.count() > 0 and await submit_btn.first.is_visible():
            await submit_btn.first.click()
            return True
        return False