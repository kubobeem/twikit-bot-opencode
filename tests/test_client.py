import json
import tempfile
import unittest
from pathlib import Path

from xbot.client import BotAuthError, XBot, classify_error, load_cookie_dict


class TestClassify(unittest.TestCase):
    def test_auth(self):
        self.assertEqual(classify_error(ValueError("Unauthorized")), "auth")
        self.assertEqual(classify_error(RuntimeError("Forbidden")), "auth")

    def test_automation(self):
        self.assertEqual(classify_error(ValueError("looks automated")), "automation")
        self.assertEqual(classify_error(ValueError("code 226")), "automation")

    def test_other(self):
        self.assertEqual(classify_error(ValueError("401")), "other")

    def test_exception_class_name(self):
        Forbidden = type("Forbidden", (Exception,), {})
        Unauthorized = type("Unauthorized", (Exception,), {})
        self.assertEqual(classify_error(Forbidden("nope")), "auth")
        self.assertEqual(classify_error(Unauthorized("nope")), "auth")


class StubT:
    async def like(self, tweet_id, **kw):
        raise ValueError("Unauthorized")

    async def follow(self, screen_name, **kw):
        raise ValueError("looks automated")


class TestCookies(unittest.TestCase):
    def test_dict_and_list(self):
        d = {"auth_token": "a", "ct0": "b"}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.json"
            p.write_text(json.dumps(d))
            self.assertEqual(load_cookie_dict(p), d)
            p.write_text(json.dumps([{"name": "auth_token", "value": "a"},
                                     {"name": "ct0", "value": "b"}]))
            self.assertEqual(load_cookie_dict(p), d)

    def test_xbot_auth_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.json"
            p.write_text(json.dumps({"auth_token": "a"}))
            bot = XBot(p, "me")
            bot._t = StubT()
            with self.assertRaises(BotAuthError):
                import asyncio
                asyncio.run(bot.like("1"))

    def test_xbot_follow_no_browser_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.json"
            p.write_text(json.dumps({"auth_token": "a"}))
            bot = XBot(p, "me")
            bot._t = StubT()
            import asyncio
            with self.assertRaises(ValueError):
                asyncio.run(bot.follow("x"))


if __name__ == "__main__":
    unittest.main()