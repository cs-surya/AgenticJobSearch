import asyncio
from typing import Dict, Any
from playwright.async_api import Page, FrameLocator

class CaptchaHandler:
    @staticmethod
    async def detect_and_solve_captcha(page: Page, timeout_sec: int = 6) -> Dict[str, Any]:
        """
        Detects common ATS CAPTCHAs (Cloudflare Turnstile, reCAPTCHA, hCaptcha, FriendlyCaptcha)
        and attempts to click the verification checkbox.
        """
        result = {"detected": False, "type": None, "solved": False, "interactive_required": False}

        # ---------------- 1. CLOUDFLARE TURNSTILE ----------------
        turnstile_frames = page.locator('iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]')
        if await turnstile_frames.count() > 0:
            result["detected"] = True
            result["type"] = "Cloudflare Turnstile"
            print("[CAPTCHA] Cloudflare Turnstile detected. Attempting auto-click...")
            try:
                frame_loc = page.frame_locator('iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]').first
                checkbox = frame_loc.locator('input[type="checkbox"], span.mark, div#challenge-stage, .ctp-checkbox-label')
                if await checkbox.count() > 0:
                    await checkbox.first.click(timeout=3000)
                    await asyncio.sleep(2)
                    result["solved"] = True
                    print("[CAPTCHA] ✅ Cloudflare Turnstile checkbox clicked.")
                    return result
            except Exception as e:
                print(f"[CAPTCHA] Turnstile click attempt: {e}")

        # ---------------- 2. GOOGLE reCAPTCHA v2 ----------------
        recaptcha_frames = page.locator('iframe[src*="google.com/recaptcha/api2/anchor"], iframe[src*="recaptcha"]')
        if await recaptcha_frames.count() > 0:
            result["detected"] = True
            result["type"] = "Google reCAPTCHA"
            print("[CAPTCHA] Google reCAPTCHA detected. Attempting anchor checkbox click...")
            try:
                recaptcha_frame = page.frame_locator('iframe[src*="google.com/recaptcha/api2/anchor"]').first
                anchor = recaptcha_frame.locator('#recaptcha-anchor, .recaptcha-checkbox-border')
                if await anchor.count() > 0:
                    await anchor.first.click(timeout=3000)
                    await asyncio.sleep(2.5)

                    # Check if an interactive image challenge opened
                    bframe = page.locator('iframe[src*="google.com/recaptcha/api2/bframe"]')
                    if await bframe.count() > 0 and await bframe.first.is_visible():
                        result["interactive_required"] = True
                        print("[CAPTCHA] ⚠️ reCAPTCHA image puzzle appeared (interactive solve needed).")
                    else:
                        result["solved"] = True
                        print("[CAPTCHA] ✅ reCAPTCHA checkbox passed.")
                    return result
            except Exception as e:
                print(f"[CAPTCHA] reCAPTCHA click attempt: {e}")

        # ---------------- 3. hCaptcha ----------------
        hcaptcha_frames = page.locator('iframe[src*="hcaptcha.com/captcha"]')
        if await hcaptcha_frames.count() > 0:
            result["detected"] = True
            result["type"] = "hCaptcha"
            print("[CAPTCHA] hCaptcha detected. Attempting checkbox click...")
            try:
                h_frame = page.frame_locator('iframe[src*="hcaptcha.com/captcha"]').first
                h_box = h_frame.locator('#checkbox, div[aria-label="checkbox"]')
                if await h_box.count() > 0:
                    await h_box.first.click(timeout=3000)
                    await asyncio.sleep(2.5)
                    result["solved"] = True
                    print("[CAPTCHA] ✅ hCaptcha checkbox clicked.")
                    return result
            except Exception as e:
                print(f"[CAPTCHA] hCaptcha click attempt: {e}")

        # ---------------- 4. GENERIC "I am not a robot" / VERIFY BUTTONS ----------------
        generic_captcha = page.locator('button:has-text("Verify"), div:has-text("I am not a robot"), [id*="captcha" i] input[type="checkbox"]')
        if await generic_captcha.count() > 0 and await generic_captcha.first.is_visible():
            result["detected"] = True
            result["type"] = "Generic Verification"
            try:
                await generic_captcha.first.click(timeout=2000)
                await asyncio.sleep(1.5)
                result["solved"] = True
                print("[CAPTCHA] ✅ Generic verification button clicked.")
                return result
            except Exception as e:
                print(f"[CAPTCHA] Generic verification click attempt: {e}")

        return result