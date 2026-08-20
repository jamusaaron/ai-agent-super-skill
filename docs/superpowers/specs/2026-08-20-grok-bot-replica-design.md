# Grok Bot — Design (independent replication attempt)

Date: 2026-08-20
Status: Decided autonomously (cloud agent — no user Q&A possible). Decisions below are documented assumptions.

## Intent

Ship one complete, production-quality chat bot experience powered by xAI's Grok API: a
distinctive web chat UI plus a small backend that talks to `https://api.x.ai/v1`. The
repository is otherwise a documentation repo (an AI-agent `SKILL.md`), so this is a
greenfield app that lives in its own `grok-bot/` directory and leaves the skill intact.

## Product decisions (assumptions, locked without user input)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Surface | Web chat app + Python backend | Repo has no JS toolchain; task default is a polished web chat |
| Backend | FastAPI + Uvicorn, Python 3.12 | Small, testable, one process serves API + static UI |
| Frontend | Vanilla HTML/CSS/JS, no build step | Shippable scope; nothing to compile |
| Grok access | OpenAI Python SDK, `base_url=https://api.x.ai/v1` | Officially supported OpenAI-compatible endpoint |
| Model | `grok-4.6` default, `GROK_MODEL` env override | Current flagship chat model per docs.x.ai (verified 2026-08-20) |
| Auth | `XAI_API_KEY` env var (also read from `.env`) | Official env name; secrets never committed |
| Sessions | In-memory, per process | No DB in scope; loss on restart documented in README |
| Streaming | Server-Sent Events, JSON events | Chat Completions `stream=True` maps cleanly onto SSE |
| Personality | Witty, direct, maximally helpful | System prompt only — no jailbreak; normal refusal behavior kept |
| Visual identity | "The Wire" — teletype/newsroom dispatch | Paper cream, ink black, vermilion accent; serif + mono type. Deliberately not a dark neon dashboard |

## Approaches considered

1. **FastAPI + static frontend (chosen).** One process, no build step, easy to test with
   `TestClient`, matches the repo's Python orientation.
2. **Node/Express + React.** Better for a big product surface; adds a toolchain this repo
   doesn't have and slows a shippable single-bot scope.
3. **Platform bot (Discord/Telegram).** Requires a third-party account and long-running
   socket infra; the repo gives no signal that this is wanted.

## Architecture

```
browser (grok-bot/web)  --JSON + SSE-->  FastAPI (grok-bot/grokbot)  --OpenAI SDK-->  api.x.ai
                                            |-- SessionStore (in-memory, thread-safe)
                                            |-- GrokGateway (client wrapper + error mapping)
                                            |-- persona system prompt
```

### Modules (each independently testable)

- `grokbot/settings.py` — pydantic-settings; env + `.env`: `XAI_API_KEY`, `GROK_MODEL`,
  `XAI_BASE_URL`, `GROK_HISTORY_LIMIT`.
- `grokbot/store.py` — `SessionStore`: `create / get / list / append / delete`,
  thread-safe, history capped, `UnknownSession` error.
- `grokbot/exceptions.py` — `GrokNotConfigured`, `GrokKeyRejected`, `GrokThrottled`,
  `GrokUpstreamError`.
- `grokbot/gateway.py` — `GrokGateway.reply(messages) -> str` and
  `.stream_reply(messages) -> Iterator[str]`; maps SDK errors to the typed errors above.
- `grokbot/persona.py` — the Grok system prompt.
- `grokbot/api.py` — `create_app(store, gateway)` app factory (dependency injection for
  tests); serves the static UI.
- `grokbot/__main__.py` — `python -m grokbot` runs Uvicorn.

### HTTP API

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/health` | 200 always: `{status, model, api_key_configured}` |
| GET | `/` | Chat UI (static) |
| POST | `/api/sessions` | Create session → `{id, title, created_at, updated_at, messages: []}` |
| GET | `/api/sessions` | List sessions, most recently updated first (id, title, updated_at, message_count) |
| GET | `/api/sessions/{id}` | Session detail incl. ordered messages |
| DELETE | `/api/sessions/{id}` | Remove session → 204 |
| POST | `/api/sessions/{id}/messages` | `{content}` → stores user msg, calls Grok, stores + returns `{reply}` |
| POST | `/api/sessions/{id}/messages/stream` | Same input; SSE: `{"type":"delta","text":...}`* then `{"type":"done"}`; assistant msg stored at stream end |

### Error contract

| Condition | Status | Notes |
|-----------|--------|-------|
| Empty / whitespace-only message | 422 | request validation |
| Unknown session id | 404 | |
| `XAI_API_KEY` unset | 503 | "Grok Bot has no XAI_API_KEY configured…" |
| xAI rejects the key (401) | 503 | server misconfiguration, not a client fault |
| xAI rate limit (429) | 429 | passthrough with friendly message |
| Other upstream/API/network error | 502 | safe generic message; no secrets/stack traces leaked |
| Error mid-stream | SSE `{"type":"error","message":...}` | HTTP status already sent; error event instead |

### Session rules

- UUID4 ids; messages stored as `{role, content, created_at}` (user/assistant only —
  the system prompt is prepended at call time, never stored).
- Title = first user message, truncated to 60 chars.
- History cap: 60 stored messages; oldest dropped first. The full (capped) history is
  sent to Grok on each call so the bot has conversation memory.

### Frontend — "The Wire"

Masthead: **GROK BOT** with tagline "maximally helpful · wire service to the galaxy".
Newsprint aesthetic: warm paper background, ink-black text, vermilion accent, hairline
column rules. Type: Newsreader (display serif) + IBM Plex Mono (UI/meta). User messages
appear as outgoing TELEX blocks; Grok replies typeset as column text with a blinking
block caret while streaming. Left rail lists dispatches (sessions) with new/delete.
Errors render as a red wire-service bulletin. Last session id kept in `localStorage`.

### Testing

- `tests/test_store.py` — session semantics (pure unit tests, no mocks).
- `tests/test_gateway.py` — error mapping with a fake OpenAI client (constructed SDK
  exceptions); streaming chunk extraction.
- `tests/test_api.py` — endpoint behavior via `TestClient` with an injected fake
  gateway; never touches the network.

### Out of scope

Login/auth, persistence/DB, tool use, image generation, multi-user tenancy, deployment
manifests, Discord/Telegram surfaces.
