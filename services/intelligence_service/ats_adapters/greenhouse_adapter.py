import os
import re
import asyncio
from typing import Dict, Any, List
from playwright.async_api import Page
from services.intelligence_service.ats_adapters.base_adapter import BaseATSAdapter
from services.intelligence_service.captcha_handler import CaptchaHandler


class GreenhouseAdapter(BaseATSAdapter):
    async def _dismiss_overlays(self):
        try:
            cookie_btn = self.page.locator(
                'button:has-text("Accept"), button:has-text("Agree"), button:has-text("Close"), button[aria-label="Close"], #onetrust-accept-btn-handler'
            )
            if await cookie_btn.count() > 0 and await cookie_btn.first.is_visible():
                await cookie_btn.first.click(timeout=1500)
        except Exception:
            pass

        try:
            await self.page.evaluate("""
                () => {
                    const selectors = ['#onetrust-banner-sdk', '.cookie-banner', '[id*="cookie" i]', '[class*="consent" i]'];
                    selectors.forEach(s => {
                        document.querySelectorAll(s).forEach(el => el.remove());
                    });
                }
            """)
        except Exception:
            pass

    async def fill_form(self, job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        personal = profile.get("personal", {})
        full_name = personal.get("full_name", "").strip() or "Surya CS"

        name_parts = full_name.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])
        else:
            first_name = full_name
            last_name = full_name

        email = personal.get("email", "")
        phone = personal.get("phone", "")
        linkedin = personal.get("linkedin", "")
        website = personal.get("website", "")
        github = personal.get("github", "")
        location_val = personal.get("location") or personal.get("city") or "Coimbatore, Tamil Nadu, India"

        mapped_fields = []
        qa_records = []

        print(f"\n[Greenhouse] >>> Starting Form Ingestion for {job.get('company')}...")

        await self._dismiss_overlays()

        # 1. SCROLL DOWN TO INITIALIZE LAZY DOM ELEMENTS
        await self.page.evaluate("""
            window.scrollTo({ top: document.body.scrollHeight / 2, behavior: 'smooth' });
        """)
        await asyncio.sleep(1.5)

        # 2. ATTACH RESUME
        resume_attached = False
        if os.path.exists(self.resume_path):
            file_inputs = self.page.locator('input[type="file"]')
            for i in range(await file_inputs.count()):
                inp = file_inputs.nth(i)
                try:
                    await inp.set_input_files(self.resume_path)
                    resume_attached = True
                    mapped_fields.append({"field": "Resume File", "value": os.path.basename(self.resume_path)})
                    print(f"[Greenhouse] [ATTACHED] Resume -> {self.resume_path}")
                    break
                except Exception as e:
                    print(f"[Greenhouse] Upload error: {e}")

        await asyncio.sleep(1.2)

        # 3. UNIVERSAL JS INJECTOR FOR STANDARD FIELDS
        form_payload = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "linkedin": linkedin,
            "website": website,
            "github": github,
            "location": location_val
        }

        injected_fields = await self.page.evaluate("""
            (payload) => {
                const filled = [];
                const setNativeValue = (element, value) => {
                    const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set;
                    const prototype = Object.getPrototypeOf(element);
                    const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;

                    if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
                        prototypeValueSetter.call(element, value);
                    } else if (valueSetter) {
                        valueSetter.call(element, value);
                    } else {
                        element.value = value;
                    }
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true }));
                    element.dispatchEvent(new Event('blur', { bubbles: true }));
                };

                const getLabelText = (input) => {
                    let text = "";
                    if (input.id) {
                        const lbl = document.querySelector(`label[for="${input.id}"]`);
                        if (lbl) text += " " + lbl.innerText;
                    }
                    if (input.closest('label')) text += " " + input.closest('label').innerText;
                    if (input.closest('div')) {
                        const prev = input.closest('div').querySelector('label, span, p, h3, h4');
                        if (prev) text += " " + prev.innerText;
                    }
                    text += " " + (input.getAttribute('placeholder') || "");
                    text += " " + (input.getAttribute('name') || "");
                    text += " " + (input.getAttribute('aria-label') || "");
                    text += " " + (input.getAttribute('data-field') || "");
                    return text.toLowerCase();
                };

                // Fill Text Inputs
                const allInputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], input:not([type])');
                allInputs.forEach(input => {
                    if (input.type === 'file' || input.type === 'hidden' || input.type === 'checkbox' || input.type === 'radio') return;
                    const meta = getLabelText(input);

                    if (/first.*name|given.*name/.test(meta) && !/last.*name/.test(meta)) {
                        setNativeValue(input, payload.first_name);
                        filled.push({ field: "First Name", value: payload.first_name });
                    } else if (/last.*name|surname|family.*name/.test(meta)) {
                        setNativeValue(input, payload.last_name);
                        filled.push({ field: "Last Name", value: payload.last_name });
                    } else if (/^name$|full.*name/.test(meta)) {
                        setNativeValue(input, payload.full_name);
                        filled.push({ field: "Full Name", value: payload.full_name });
                    } else if (/email/.test(meta)) {
                        setNativeValue(input, payload.email);
                        filled.push({ field: "Email", value: payload.email });
                    } else if (/phone|mobile|tel/.test(meta) && !/country/i.test(meta)) {
                        setNativeValue(input, payload.phone);
                        filled.push({ field: "Phone", value: payload.phone });
                    } else if (/linkedin/.test(meta) && payload.linkedin) {
                        setNativeValue(input, payload.linkedin);
                        filled.push({ field: "LinkedIn", value: payload.linkedin });
                    } else if (/github/.test(meta) && payload.github) {
                        setNativeValue(input, payload.github);
                        filled.push({ field: "GitHub", value: payload.github });
                    } else if (/website|portfolio|blog/.test(meta) && payload.website) {
                        setNativeValue(input, payload.website);
                        filled.push({ field: "Website", value: payload.website });
                    }
                });

                // Standard Dropdowns
                const selects = document.querySelectorAll('select');
                selects.forEach(sel => {
                    const meta = getLabelText(sel);
                    const opts = Array.from(sel.options).map(o => o.text.trim());
                    const validOpts = opts.filter(o => o && !/select|choose/i.test(o));

                    if (validOpts.length === 0) return;

                    let targetOpt = null;
                    if (/authorized to work|legally authorized/i.test(meta)) {
                        targetOpt = validOpts.find(o => /yes|authorized|eligible/i.test(o)) || validOpts[0];
                    } else if (/sponsorship|require visa/i.test(meta)) {
                        targetOpt = validOpts.find(o => /no|not require/i.test(o)) || validOpts[validOpts.length - 1];
                    } else if (/relatives|family|conflict|outside business|employed by/i.test(meta)) {
                        targetOpt = validOpts.find(o => /no|none|n\/a/i.test(o)) || validOpts[0];
                    } else {
                        targetOpt = validOpts[0];
                    }

                    if (targetOpt) {
                        sel.value = Array.from(sel.options).find(o => o.text.trim() === targetOpt)?.value || sel.value;
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                        filled.push({ field: `Dropdown: ${meta.slice(0, 30)}...`, value: targetOpt });
                    }
                });

                // Checkboxes
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(cb => {
                    if (!cb.checked) {
                        cb.checked = true;
                        cb.dispatchEvent(new Event('change', { bubbles: true }));
                        filled.push({ field: "Consent Checkbox", value: "Checked" });
                    }
                });

                return filled;
            }
        """, form_payload)

        mapped_fields.extend(injected_fields)

        # 4. PHONE COUNTRY COMBOBOX INTERACTION
        country_triggers = self.page.locator(
            'button[aria-label*="country" i], div[class*="country-select" i], [data-field="country"] input, select[name*="country" i]'
        )
        if await country_triggers.count() > 0:
            target = country_triggers.first
            try:
                await target.scroll_into_view_if_needed()
                await target.click()
                await asyncio.sleep(0.3)
                await self.page.keyboard.type("India", delay=40)
                await asyncio.sleep(0.4)

                country_opt = self.page.locator(
                    'li:has-text("India"), div[role="option"]:has-text("India"), option:has-text("India")')
                if await country_opt.count() > 0 and await country_opt.first.is_visible():
                    await country_opt.first.click()
                else:
                    await self.page.keyboard.press("ArrowDown")
                    await self.page.keyboard.press("Enter")
                mapped_fields.append({"field": "Country Code", "value": "India (+91)"})
                print("[Greenhouse] [COMBOBOX] Set Country Code -> India (+91)")
            except Exception as e:
                print(f"[Greenhouse] Country selector interaction: {e}")

        # 5. LOCATION (CITY) AUTOCOMPLETE INTERACTION
        loc_inputs = self.page.locator(
            'input#job_application_location, input[name*="location" i], input[placeholder*="location" i], input[aria-label*="location" i], input[data-field="location"]'
        )
        if await loc_inputs.count() > 0:
            loc_el = loc_inputs.first
            try:
                await loc_el.scroll_into_view_if_needed()
                await loc_el.click()
                await loc_el.fill("")
                await loc_el.type(location_val, delay=40)
                await asyncio.sleep(0.8)

                suggestion = self.page.locator(
                    'div[role="option"], ul[class*="suggestions" i] li, li:has-text("Coimbatore")')
                if await suggestion.count() > 0 and await suggestion.first.is_visible():
                    await suggestion.first.click()
                else:
                    await self.page.keyboard.press("ArrowDown")
                    await asyncio.sleep(0.2)
                    await self.page.keyboard.press("Enter")
                mapped_fields.append({"field": "Location (City)", "value": location_val})
                print(f"[Greenhouse] [AUTOCOMPLETE] Set Location -> {location_val}")
            except Exception as e:
                print(f"[Greenhouse] Location field interaction: {e}")

        # 6. DYNAMIC CUSTOM TEXTAREAS (Ollama Form Q&A)
        textareas = self.page.locator('textarea, input[id*="job_application_answers_attributes"]')
        for i in range(await textareas.count()):
            ta = textareas.nth(i)
            try:
                await ta.scroll_into_view_if_needed(timeout=1000)
                if not await ta.is_visible():
                    continue

                curr_val = await ta.input_value()
                if curr_val:
                    continue

                ta_id = (await ta.get_attribute("id") or "").lower()
                q_text = ""
                if ta_id:
                    lbl = self.page.locator(f'label[for="{ta_id}"]')
                    if await lbl.count() > 0:
                        q_text = await lbl.first.inner_text()
                if not q_text:
                    parent_txt = await ta.locator('xpath=..').inner_text()
                    q_text = parent_txt if len(parent_txt) < 200 else (
                                await ta.get_attribute("placeholder") or "Application Question")

                ans = self.qa_agent.answer_question(q_text, profile, job)
                await ta.fill(ans)
                await ta.dispatch_event('input')
                await ta.dispatch_event('change')
                qa_records.append({"question": q_text.strip()[:100], "answer": ans})
                print(f"[Greenhouse] [AI Q&A] '{q_text[:35]}...' -> '{ans[:40]}...'")
            except Exception as e:
                print(f"[Greenhouse] Textarea error: {e}")

        # 7. CAPTCHA AUTO-CHECK
        await CaptchaHandler.detect_and_solve_captcha(self.page)

        return {
            "resume_attached": resume_attached,
            "mapped_fields": mapped_fields,
            "qa_records": qa_records
        }

    async def _click_submit_btn(self) -> bool:
        submit_selectors = [
            '#submit_app',
            'button[type="submit"]:has-text("Submit Application")',
            'button[type="submit"]:has-text("Submit")',
            'button:has-text("Submit Application")',
            'input[type="submit"][value*="Submit" i]',
            'input[type="submit"]',
            'button[type="submit"]'
        ]
        for sel in submit_selectors:
            buttons = self.page.locator(sel)
            for i in range(await buttons.count()):
                btn = buttons.nth(i)
                try:
                    await btn.scroll_into_view_if_needed(timeout=2000)
                    if await btn.is_visible():
                        print(f"[Greenhouse] Triggering submit button ({sel})...")
                        try:
                            await btn.click(force=True, timeout=3000)
                        except Exception:
                            await btn.dispatch_event('click')
                        return True
                except Exception:
                    continue
        return False

    async def submit(self) -> Dict[str, Any]:
        await self._dismiss_overlays()

        print("[Greenhouse] Performing submission trigger...")
        clicked = await self._click_submit_btn()
        if not clicked:
            return {"confirmed": False, "message": "Could not locate a clickable submit button."}

        print("[Greenhouse] ⏳ Monitoring submission confirmation (up to 40s)...")
        confirmation_patterns = ["confirmation", "thank-you", "thanks", "application_submitted", "submitted"]
        re_submitted_after_captcha = False

        for sec in range(40):
            curr_url = self.page.url.lower()
            if any(p in curr_url for p in confirmation_patterns):
                print(f"[Greenhouse] ✅ Confirmed via redirect: {curr_url}")
                return {"confirmed": True, "message": "Application confirmed by ATS redirect!"}

            try:
                body_text = (await self.page.inner_text('body', timeout=1000)).lower()
                if "thank you for applying" in body_text or "application submitted" in body_text or "received your application" in body_text:
                    print("[Greenhouse] ✅ Confirmed via success header!")
                    return {"confirmed": True, "message": "Application confirmed by success header!"}
            except Exception:
                pass

            # Detect unfulfilled validation errors
            validation_errors = await self.page.evaluate("""
                () => {
                    const invalidEls = document.querySelectorAll(':invalid, .field-error, .error-message');
                    return Array.from(invalidEls).map(el => el.getAttribute('name') || el.id || el.innerText).filter(Boolean);
                }
            """)
            if validation_errors and sec > 6:
                err_msg = f"Form validation failed on: {', '.join(validation_errors[:3])}"
                print(f"[Greenhouse] ❌ {err_msg}")
                return {"confirmed": False, "message": err_msg}

            # CAPTCHA Watch & Re-click
            captcha_token = await self.page.evaluate("""
                () => {
                    const el = document.querySelector('textarea[name="g-recaptcha-response"], [id*="recaptcha-token" i]');
                    return el ? el.value : "";
                }
            """)

            if captcha_token and not re_submitted_after_captcha:
                print(f"[Greenhouse] 🎯 Solved CAPTCHA token detected! Re-clicking submit button...")
                await asyncio.sleep(1)
                await self._click_submit_btn()
                re_submitted_after_captcha = True

            await asyncio.sleep(1)

        return {"confirmed": False, "message": "Submission timed out waiting for server confirmation."}