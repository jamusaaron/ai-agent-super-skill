# Grok Bot Design

Date: 2026-08-20
Status: Approved for autonomous implementation (cloud agent; no user Q&A)

## Intent

Build a shippable **Grok Bot**: a one-experience chat product powered by xAI's Grok API. The repository currently contains only an AI-agent skill (`SKILL.md`). This adds a working reference app without replacing the skill.

## Product decisions (assumptions)

These were locked without user input because this is a background/cloud agent run.

| Decision | Choice | Why |
|----------|--------|-----|
| Surface | Web chat app + Python backend | Repo is not Discord/Telegram oriented; user default is a polished web chat |
| Stack | FastAPI + vanilla HTML/CSS/JS | Matches skill's FastAPI serving pattern; no Node build; easy tests |
| Model | `grok-4.6` via `GROK_MODEL` | Current documented xAI chat model (Aug 2026). `grok-4` still aliases. |
| API style | OpenAI-compatible Chat Completions | User spec; streaming is well documented; easy to mock |
| Base URL | `https://api.x.ai/v1` | Official xAI OpenAI-compatible endpoint |
| Auth | `XAI_API_KEY` env var | Official xAI env name; never commit secrets |
| Sessions | In-memory per process | Shippable scope; no DB; sessions lost on restart (documented) |
| Streaming | SSE from `/api/chat/stream` | Feasible with Chat Completions `stream=True` |
| Personality | Witty, direct, maximally helpful Grok | System prompt, not a jailbreak; still refuses harmful requests as Grok would |
| Brand | **Grok Bot** — "observatory terminal" | Distinct from ChatGPT clones: warm black, copper, acid chartreuse, Fraunces + Chivo Mono |

## Approaches considered

1. **FastAPI + static frontend (chosen).** Smallest production path, TDD-friendly, one process to run.
2. **Next.js full-stack.** Better for a large product; extra toolchain and no existing JS app in this repo.
3. **Discord/Telegram bot.** Wrong default unless the repo is chat-platform oriented (it is not).

## Architecture

```
Browser (frontend/)  --JSON/SSE-->  FastAPI (app/)  --OpenAI SDK-->  api.x.ai
                                      |
                                      +-- SessionStore (in-memory)
                                      +-- personality system prompt
                                      +-- static files for UI
```

### Components

- `app/config.py` — env-backed settings (`XAI_API_KEY`, `GROK_MODEL`, `XAI_BASE_URL`, host/port).
- `app/sessions.py` — `SessionStore`: create/get/append/clear; cap history length.
- `app/grok.py` — thin xAI client wrapper (complete + stream); maps HTTP errors to typed errors.
- `app/personality.py` — Grok system prompt.
- `app/main.py` — FastAPI: health, sessions, chat, stream, static UI.
- `frontend/` — distinctive single-page chat console.

### HTTP API

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/health` | `{status, model, grok_configured}` — 200 even if key missing |
| GET | `/` | Chat UI |
| POST | `/api/sessions` | Create session `{id, created_at, title}` |
| GET | `/api/sessions` | List sessions (id, title, updated_at, preview) |
| GET | `/api/sessions/{id}` | Session + messages (user/assistant only) |
| DELETE | `/api/sessions/{id}` | Delete session |
| POST | `/api/chat` | `{session_id, message}` → `{session_id, reply}` (non-stream) |
| POST | `/api/chat/stream` | Same body; SSE `data: {"delta": "..."}` then `data: [DONE]` |

Empty message → 422. Unknown session → 404. Missing/invalid key on chat → 503. xAI 429 → 429. Other xAI errors → 502 with a safe message (no secret leakage).

### Session rules

- UUID session ids.
- Store ordered `{role, content, created_at}` messages.
- Prepend system prompt only at the xAI call, not in stored history.
- Cap at 40 stored messages (drop oldest user/assistant pairs).
- Title = first user message truncated to 48 chars.

### Grok client

```
OpenAI(api_key=XAI_API_KEY, base_url=XAI_BASE_URL)
chat.completions.create(model=GROK_MODEL, messages=[system, ...history, user], stream=?)
```

Errors mapped: missing key → `GrokConfigError`; 401 → `GrokAuthError`; 429 → `GrokRateLimitError`; other API/network → `GrokAPIError`.

### Frontend

Name on screen: **GROK BOT**. Tagline: *maximally helpful, mildly feral*.

Visual direction: desert observatory at night — not a purple-gradient chat clone.

- Warm near-black ground, copper rails, acid-chartreuse signal color
- Display: Fraunces. UI/meta: Chivo Mono
- Left spine with stacked wordmark; thread list; live transcript; terminal-style composer
- Streaming token cursor; error banner for missing key / rate limit
- New thread, switch threads, persist last session id in `localStorage`

### Testing

Pytest with httpx `TestClient`. Mock the OpenAI client (never hit xAI in tests). Cover session store, error mapping, health, chat, streaming SSE, validation.

### Out of scope

Auth/login, persistence, tools/web search, image gen, Discord/Telegram, multi-user accounts, billing.

## Error handling (user-visible copy)

- Missing key: "Grok Bot needs an XAI_API_KEY. Add it to `.env` — see README."
- Rate limit: "xAI is rate-limiting this key. Wait a moment and try again."
- Auth: "xAI rejected the API key. Check XAI_API_KEY."
- Upstream: "Grok didn't answer. The model or API returned an error."
