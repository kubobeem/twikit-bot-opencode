"""xbot CLI: operate an X account with persona-friendly tooling.

Try twikit first for every write. On automation blocks (226 / 403) the same
action is retried through a real browser. That is automatic unless
--no-fallback is given.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .client import BotAuthError, XBot


def _load_dotenv(path: str = ".env"):
    """Minimal KEY=VALUE parser; never overrides an existing env var."""
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

DEFAULT_COOKIES = os.environ.get("XBOT_COOKIES", "cookies.json")
DEFAULT_ME = os.environ.get("XBOT_SCREEN_NAME", "")
DEFAULT_WATCH = os.environ.get("XBOT_WATCH", "qa_a_aa")


def _enc():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def fmt(t) -> str:
    by = t.user.screen_name if getattr(t, "user", None) else "?"
    ids = f"[fav={t.favorite_count} rt={t.retweet_count}]"
    return f"{t.id} @{by} {ids} {repr((t.text or '')[:110])}"


def _bot(args) -> XBot:
    if not args.me:
        raise SystemExit("set XBOT_SCREEN_NAME or pass --me SCREEN_NAME (your account)")
    return XBot(args.cookies, args.me, headless=args.headless,
                browser_fallback=not args.no_fallback)


def cmd_login(args):
    from .login import extract_cookies
    extract_cookies(args.cookies, headless=args.headless)


async def cmd_check(args):
    with _bot(args) as b:
        me = await b.check()
        print("AUTH_OK", me)
        print("=== HOME ===")
        for t in await b.t.timeline(count=args.count):
            if hasattr(t, "text"):
                print(fmt(t))


async def cmd_tl(args):
    with _bot(args) as b:
        for t in await b.t.timeline(count=args.count):
            if hasattr(t, "text"):
                print(fmt(t))


async def cmd_tweet(args):
    with _bot(args) as b:
        rows = await b.t.thread(args.id) if args.thread else [await b.t.tweet(args.id)]
        for t in rows:
            print(fmt(t) + (f"  <-- viewed: {args.id}" if t.id == args.id else ""))


async def cmd_mentions(args):
    with _bot(args) as b:
        for t in await b.t.mentions(args.me, count=args.count):
            print(fmt(t))


async def cmd_user(args):
    with _bot(args) as b:
        screen = args.screen
        for t in await b.t.user_tweets(screen, tab=args.tab, count=args.count):
            print(fmt(t))


async def cmd_post(args):
    with _bot(args) as b:
        tid = await b.post(args.text, reply_to=args.reply_to)
        tag = "REPLY" if args.reply_to else "POST"
        print(f"{tag}_OK", tid, "to", args.reply_to or "-")


async def cmd_like(args):
    with _bot(args) as b:
        for tid in args.id:
            await b.like(tid)
            print("LIKE_OK", tid)


async def cmd_rt(args):
    with _bot(args) as b:
        for tid in args.id:
            await b.rt(tid)
            print("RT_OK", tid)


async def cmd_follow(args):
    with _bot(args) as b:
        await b.follow(args.screen)
        print("FOLLOW_OK", args.screen)


async def cmd_act(args):
    actions = json.loads(Path(args.file).read_text(encoding="utf-8"))
    with _bot(args) as b:
        for a in actions:
            op = a.get("op")
            label = op.upper()
            try:
                if op == "post":
                    r = await b.post(a["text"])
                    print(f"{label}_OK", r)
                elif op == "reply":
                    r = await b.post(a["text"], reply_to=a["id"])
                    print(f"{label}_OK", r, "to", a["id"])
                elif op == "like":
                    await b.like(a["id"])
                    print(f"{label}_OK", a["id"])
                elif op == "rt":
                    await b.rt(a["id"])
                    print(f"{label}_OK", a["id"])
                elif op == "sleep":
                    await asyncio.sleep(int(a.get("sec", 30)))
                else:
                    print(f"{op}_SKIP unknown op")
            except BotAuthError as e:
                print(f"AUTH_ERR {label} {type(e).__name__}: {e}")
                raise SystemExit(2)
            except Exception as e:
                print(f"{label}_ERR {a.get('id', a.get('text', ''))}: {type(e).__name__} {str(e)[:180]}")
            await asyncio.sleep(int(a.get("sleep", args.gap)))


def main() -> None:
    _enc()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    p = argparse.ArgumentParser(prog="xbot",
                                description="X chat-bot CLI (twikit + Playwright fallback)")
    g = p.add_argument_group("global")
    g.add_argument("--cookies", default=DEFAULT_COOKIES,
                   help="path to twikit-format cookies.json [env XBOT_COOKIES]")
    g.add_argument("--me", default=DEFAULT_ME,
                   help="your X screen_name [env XBOT_SCREEN_NAME]")
    g.add_argument("--no-fallback", action="store_true",
                   help="never open the real browser on 226/403")
    g.add_argument("--headless", action="store_true", help="headless browser (default: headed)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="log in once in a real browser and save cookies")
    pk = sub.add_parser("check", help="auth probe + home timeline"); pk.add_argument("--count", type=int, default=30)
    pt = sub.add_parser("tl", help="home timeline"); pt.add_argument("--count", type=int, default=30)
    pv = sub.add_parser("tweet", help="show one tweet or its thread")
    pv.add_argument("id"); pv.add_argument("--thread", action="store_true")
    pm = sub.add_parser("mentions", help="recent mentions"); pm.add_argument("--count", type=int, default=20)
    pu = sub.add_parser("user", help="tweets/replies of a user")
    pu.add_argument("screen"); pu.add_argument("--tab", default="Tweets", choices=["Tweets", "Replies"]); pu.add_argument("--count", type=int, default=20)
    pp = sub.add_parser("post", help="create a tweet (or reply with --reply-to)")
    pp.add_argument("text"); pp.add_argument("--reply-to")
    pl = sub.add_parser("like", help="like tweets"); pl.add_argument("id", nargs="+")
    pr = sub.add_parser("rt", help="retweet"); pr.add_argument("id", nargs="+")
    pf = sub.add_parser("follow", help="follow a user"); pf.add_argument("screen")
    pa = sub.add_parser("act", help="run an actions JSON file")
    pa.add_argument("file"); pa.add_argument("--gap", type=int, default=30)

    args = p.parse_args()
    if args.cmd == "login":
        cmd_login(args)
        return
    try:
        asyncio.run(globals()["cmd_" + args.cmd](args))
    except BotAuthError as e:
        print(f"AUTH_ERR {e}")
        print("Refresh cookies via: xbot login  (then retry once)")
        sys.exit(2)


if __name__ == "__main__":
    main()