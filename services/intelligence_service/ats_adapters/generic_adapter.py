import os
import re
from typing import Dict, Any
from playwright.async_api import Page
from services.intelligence_service.ats_adapters.base_adapter import BaseATSAdapter


class GenericHeuristicAdapter(BaseATSAdapter):
    async def fill_form(self, job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        personal = profile.get("personal", {})
        first_name = personal.get("full_name", "").split()[0]
        last_name = " ".join(personal.get("full_name", "").split()[1:]) or first_name

        mapped_fields = []
        qa_records = []

        # 1. Attach Resume
        file_inputs = self.page.locator('input[type="file"]')
        resume_attached = False
        if await file_inputs.count() > 0 and os.path.exists(self.resume_path):
            await file_inputs.first.set_input_files(self.resume_path)
            resume_attached = True

        # 2. Heuristic Text Inputs
        field_map = [
            (r"first.*name|given.*name", "First Name", first_name),
            (r"^last.*name|family.*name|surname", "Last Name", last_name),
            (r"^name|full.*name", "Full Name", personal.get("full_name", "")),
            (r"email", "Email", personal.get("email", "")),
            (r"phone|mobile|tel", "Phone", personal.get("phone", "")),
            (r"linkedin", "LinkedIn", personal.get("linkedin", "")),
            (r"github", "GitHub", personal.get("github", "")),
            (r"website|portfolio|blog", "Portfolio", personal.get("website", "")),
        ]

        text_inputs = self.page.locator('input[type="text"], input[type="email"], input[type="tel"]')
        for i in range(await text_inputs.count()):
            inp = text_inputs.nth(i)
            if not await inp.is_visible():
                continue
            meta = f"{await inp.get_attribute('name') or ''} {await inp.get_attribute('id') or ''} {await inp.get_attribute('placeholder') or ''} {await inp.get_attribute('aria-label') or ''}".lower()

            for pattern, label_name, val in field_map:
                if val and re.search(pattern, meta):
                    curr = await inp.input_value()
                    if not curr:
                        await inp.fill(val)
                    mapped_fields.append({"field": label_name, "value": val})
                    break

        # 3. Dynamic Textareas
        textareas = self.page.locator('textarea')
        for i in range(await textareas.count()):
            ta = textareas.nth(i)
            if not await ta.is_visible():
                continue
            q_label = await ta.get_attribute('aria-label') or await ta.get_attribute('placeholder') or "Question"
            ans = self.qa_agent.answer_question(q_label, profile, job)
            await ta.fill(ans)
            qa_records.append({"question": q_label[:120], "answer": ans})

        return {
            "resume_attached": resume_attached,
            "mapped_fields": mapped_fields,
            "qa_records": qa_records
        }

    async def submit(self) -> bool:
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Submit Application")'
        ]
        for sel in submit_selectors:
            btn = self.page.locator(sel)
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                return True
        return False