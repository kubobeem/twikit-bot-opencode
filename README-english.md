# x-bot

One-personality chat bot CLI for X (Twitter). Writes go through **twikit (twifork, curl_cffi impersonation)** and **automatically fall back to a real Playwright browser UI when X responds 226 / 403 (automation flags)**.

Built from what actually works against X in 2026:
- X retired twikit's `login()` flow (code 366) → **no new password logins**. Auth is a logged-in browser's cookies (`auth_token` + `ct0`).
- upstream `twikit` 2.3.3 is broken in 2026 (create_tweet 226 "looks automated" / ClientTransaction KEY_BYTE corruption / Cloudflare 403). The maintained `twifork` (still imported as `twikit`) works.
- POSTs can still get 226 even on the fork, depending on account/IP → a real browser is the reliable fallback.

## Table of contents

- [Setup](#setup)
- [Usage](#usage)
- [Fallback behavior](#fallback-behavior)
- [Persona / autonomous operation](#persona--autonomous-operation)
- [Landmines (do not do these)](#landmines-do-not-do-these)
- [Development](#development)
- [License](#license)

## Setup

[⬆ back to top](#table-of-contents)

```
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e .
python -m playwright install chromium
```

Cookies are the critical step:

```
xbot login --cookies cookies.json
```

A non-headless Chromium opens on X's login screen. **Log in manually, then** press Enter in the terminal → `auth_token` / `ct0` are saved. Cookies are as sensitive as an SSH key. **Never commit them to git.**

Reference formats: `cookies.example.json` (twikit cookies), `secrets.example.json` (handle/password). The real `cookies.json` / `secrets.json` are both optional here (auth is cookie-only). Both are gitignored.

Environment variables:
- `XBOT_COOKIES` — cookies.json location (default `cookies.json`)
- `XBOT_SCREEN_NAME` — your screen_name (used by `check` / `mentions`. e.g. `Japanese_gguf`)
- `XBOT_WATCH` — account whose posts you always like (default `qa_a_aa`)

A `.env` file (KEY=VALUE) in the repo root is auto-loaded. Replace the sample values with your own.

## Usage

[⬆ back to top](#table-of-contents)

```
xbot check --me Japanese_gguf          # auth probe + home timeline
xbot tl --count 30                     # timeline
xbot user qa_a_aa --tab Tweets         # tweets/replies of a user
xbot tweet 1234567890 --thread         # single tweet or thread
xbot mentions                          # recent mentions
xbot post "sometimes my code is a monolog I show to my future self"   # post
xbot post "did someone call?" --reply-to 1234567890   # reply
xbot like 1234567890 2345678901        # like
xbot rt 1234567890                     # retweet
xbot follow some_user                  # follow
xbot act actions.json --gap 30         # batch actions from JSON
```

`act` JSON format (`actions.example.json`):

```json
[
  { "op": "like", "id": "1234567890" },
  { "op": "rt",   "id": "2345678901", "sleep": 5 },
  { "op": "reply","id": "3456789012", "text": "literally this", "sleep": 8 },
  { "op": "post", "text": "finally went outside" }
]
```

## Fallback behavior

[⬆ back to top](#table-of-contents)

Every write tries twikit first.
- `Unauthorized` / `Forbidden` → **credentials expired**. Do not re-login on your own. Run `xbot login` to refresh the cookies, then retry once.
- Message containing `automated / 226 / Cloudflare / KEY_BYTE` → **the same action is re-run through a real browser**.
- `--no-fallback` disables the browser fallback. `--headless` runs it headless.

## Persona / autonomous operation

[⬆ back to top](#table-of-contents)

- `PERSONA.md` — the bot's persona and writing style. Make an LLM agent read it before driving the account.
- `prompts/AGENT.md` — the bootstrap prompt for an LLM agent (e.g. `opencode run --auto`). Example scheduled run:

  ```
  opencode run --auto --dir . -- "read prompts/AGENT.md and run the bot"
  ```

  Tip: a Windows Task Scheduler every 5–90 minutes gives you a fully autonomous bot.

## Landmines (do not do these)

[⬆ back to top](#table-of-contents)

- **Log in only once. No hammering.** Repeated logins trigger "session concentrated" state and kill a fresh token within minutes. If login fails 3× in a row, cool down for hours to a day.
- Don't use cookies from another IP. X destroys the session the moment the IP range changes. **Residential IP only.** VPS / DC IPs / free proxies all get 401.
- Never commit `secrets.json` / `cookies.json` (already gitignored).
- Stay within common sense when automating: no DMs, no doxxing, no going deep on politics/religion.

## Development

[⬆ back to top](#table-of-contents)

```
pip install -e .[dev]   # nothing extra; plain pytest is enough
```

Tests target layers that don't depend on twikit (classify_error / cookie formats). Because the library API shifts often, the `twikit` import stays inside functions (client.py).

## License

[⬆ back to top](#table-of-contents)

MIT