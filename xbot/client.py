"""X client: twikit(twifork) first, Playwright real browser as fallback.

Why this split:
- X retired the twikit login() flow (code 366). Auth = browser cookies
  (auth_token + ct0) extracted from a real logged-in session.
- twikit create_tweet can still return 226 "looks automated" or 403 for
  automation-prone accounts/IPs. When that happens we retry the same action
  through a real (headed) browser UI instead.

Cookies JSON format is twikit-save_cookies compatible:
  [{"name": ..., "value": ...}, ...]
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import urllib3

urllib3.disable_warnings()


class BotAuthError(RuntimeError):
    """Credentials expired / rejected. Refresh cookies, do not retry."""


def classify_error(exc: Exception) -> str:
    """Return one of: auth | automation | other."""
    name = type(exc).__name__
    msg = str(exc)
    if name in ("Unauthorized", "Forbidden") or any(
            s in msg for s in ("Unauthorized", "Forbidden")):
        return "auth"
    if any(s in msg for s in ("looks automated", "automated", "226",
                              "Couldn't get KEY_BYTE indices", "Cloudflare",
                              "challenge", "cf_chl")):
        return "automation"
    return "other"


class TwikitClient:
    def __init__(self, cookies_path: str | Path, impersonate: str = "chrome"):
        from twikit import Client
        self._c = Client(impersonate=impersonate, verify=False)
        self._c.load_cookies(str(cookies_path))

    async def user_id(self, screen_name: str) -> str:
        u = await self._c.get_user_by_screen_name(screen_name)
        return u.id

    async def own_id(self, screen_name: str) -> str:
        return await self.user_id(screen_name)

    async def timeline(self, count: int = 30):
        return await self._c.get_timeline(count=count)

    async def mentions(self, screen_name: str, count: int = 20):
        return await self._c.get_user_mentions(screen_name, count=count)

    async def user_tweets(self, screen_name: str, tab: str = "Tweets", count: int = 20):
        uid = await self.user_id(screen_name)
        return await self._c.get_user_tweets(uid, tab, count=count)

    async def tweet(self, tweet_id: str):
        return await self._c.get_tweet_by_id(tweet_id)

    async def thread(self, tweet_id: str):
        return await self._c.get_thread(tweet_id)

    async def post(self, text: str, reply_to: Optional[str] = None):
        r = await self._c.create_tweet(text, reply_to=reply_to)
        return r.id

    async def like(self, tweet_id: str):
        await self._c.favorite_tweet(tweet_id)

    async def rt(self, tweet_id: str):
        await self._c.retweet(tweet_id)

    async def follow(self, screen_name: str):
        uid = await self.user_id(screen_name)
        await self._c.follow_user(uid)


class BrowserClient:
    """Headless-or-headed Playwright Chromium sharing the same cookies."""
    SELECTORS = {
        "textarea": 'div[data-testid="tweetTextarea_0"]',
        "tweet_btn": 'div[data-testid="tweetButton"]',
        "reply_btn": 'div[data-testid="reply"]',
        "like_btn": 'div[data-testid="like"]',
        "rt_btn": 'div[data-testid="retweet"]',
        "rt_confirm": 'div[data-testid="retweetConfirm"]',
    }

    def __init__(self, cookies: dict[str, str], headless: bool = False):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        browser = self._pw.chromium.launch(headless=headless)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        ctx.add_cookies([
            {"name": n, "value": v, "domain": ".x.com", "path": "/",
             "secure": True, "httpOnly": n in ("auth_token", "twid"),
             "sameSite": "Lax"}
            for n, v in cookies.items()
        ])
        self._ctx = ctx
        self._page = ctx.new_page()

    def _goto(self, url: str):
        self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
        self._page.wait_for_timeout(2000)

    def post(self, text: str, reply_to: Optional[str] = None):
        if reply_to:
            self._goto(f"https://x.com/i/status/{reply_to}")
            self._page.click(self.SELECTORS["reply_btn"])
            self._page.wait_for_timeout(800)
        else:
            self._goto("https://x.com/compose/post")
        self._page.fill(self.SELECTORS["textarea"], text)
        self._page.click(self.SELECTORS["tweet_btn"])
        self._page.wait_for_timeout(1500)
        return self._page.url

    def like(self, tweet_id: str):
        self._goto(f"https://x.com/i/status/{tweet_id}")
        if self._page.get_by_test_id("unlike").first.is_visible():
            return
        self._page.click(self.SELECTORS["like_btn"])

    def rt(self, tweet_id: str):
        self._goto(f"https://x.com/i/status/{tweet_id}")
        if self._page.get_by_test_id("unretweet").first.is_visible():
            return
        self._page.click(self.SELECTORS["rt_btn"])
        self._page.click(self.SELECTORS["rt_confirm"])

    def close(self):
        self._ctx.close()
        self._pw.stop()


def load_cookie_dict(path: str | Path) -> dict[str, str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return {k: str(v) for k, v in raw.items()}
    return {c["name"]: str(c["value"]) for c in raw}


class XBot:
    """High-level facade: twikit first, browser fallback on automation blocks."""

    def __init__(self, cookies_path: str | Path, me: str,
                 headless: bool = False, browser_fallback: bool = True):
        self.cookies_path = Path(cookies_path)
        self.me = me
        self.headless = headless
        self.browser_fallback = browser_fallback
        self._t: Optional[TwikitClient] = None
        self._b: Optional[BrowserClient] = None

    @property
    def t(self) -> TwikitClient:
        if self._t is None:
            self._t = TwikitClient(self.cookies_path)
        return self._t

    @property
    def b(self) -> BrowserClient:
        if self._b is None:
            self._b = BrowserClient(load_cookie_dict(self.cookies_path), headless=self.headless)
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self._b:
            self._b.close()

    async def _act(self, kind: str, **kw):
        """Run one write op via twikit; fall back to browser on automation blocks."""
        t = self.t
        try:
            return await getattr(t, kind)(**kw)
        except Exception as e:
            cls = classify_error(e)
            if cls == "auth":
                raise BotAuthError(f"{kind}: {type(e).__name__}: {str(e)[:200]}") from e
            if cls == "automation" and self.browser_fallback and hasattr(self.b, kind):
                kwb = {k: v for k, v in kw.items() if k in ("text", "reply_to", "tweet_id")}
                return await asyncio.to_thread(getattr(self.b, kind), **kwb)
            raise

    async def check(self):
        """Auth probe: resolves own id; raises BotAuthError when invalid."""
        try:
            return await self.t.own_id(self.me)
        except Exception as e:
            if classify_error(e) == "auth":
                raise BotAuthError(f"{type(e).__name__}: {str(e)[:200]}") from e
            raise

    async def post(self, text: str, reply_to: Optional[str] = None):
        return await self._act("post", text=text, reply_to=reply_to)

    async def like(self, tweet_id: str):
        await self._act("like", tweet_id=tweet_id)

    async def rt(self, tweet_id: str):
        await self._act("rt", tweet_id=tweet_id)

    async def follow(self, screen_name: str):
        """Follow via twikit only (no browser UI for follows)."""
        try:
            await self.t.follow(screen_name)
        except Exception as e:
            if classify_error(e) == "auth":
                raise BotAuthError(f"follow: {type(e).__name__}: {str(e)[:200]}") from e
            raise