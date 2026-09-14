"""Cookie extraction: log in ONCE in a real browser, dump auth cookies.

X retired twikit's login() flow (code 366). The only working auth route is to
reuse a logged-in browser session, so this opens a normal (non-headless)
Chromium window, lets the human log in, and saves the session cookies in the
twikit-compatible format that load_cookies understands.

Rules:
- Log in only once. Repeated login attempts put the account in "session
  concentrated" state and kill the token within minutes.
- If login fails 3 times in a row, stop and cool down for hours.
"""
from __future__ import annotations

from pathlib import Path

def extract_cookies(output: str | Path, headless: bool = False) -> dict[str, str]:
    """Open a real browser, wait for the human to log in, save auth cookies."""
    from playwright.sync_api import sync_playwright

    output = Path(output)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"))
        page = ctx.new_page()
        page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=60000)
        print("Open browser: log in on X in the visible window.")
        print("Then press Enter in this terminal to save cookies.")
        input("(waiting for Enter...) ")

        picked: dict[str, str] = {}
        for c in ctx.cookies(["https://x.com", "https://twitter.com"]):
            if c["name"] in ("auth_token", "ct0"):
                picked[c["name"]] = c["value"]
        if "auth_token" not in picked or "ct0" not in picked:
            raise RuntimeError(
                "auth_token/ct0 missing - did the login complete? "
                "Check the browser window and run again (once).")
        output.write_text(json.dumps(picked, ensure_ascii=False), encoding="utf-8")
        print(f"Saved {len(picked)} cookies to {output}")
        return picked