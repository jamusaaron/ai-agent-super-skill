# GROK BOT — The Wire

A chat bot powered by [xAI's Grok API](https://docs.x.ai), wrapped in a
teletype-newsroom web UI. One FastAPI process serves both the JSON/SSE API and
the static frontend. Replies stream token by token; conversations ("dispatches")
keep their history for the life of the process.

## Get an xAI API key

1. Create an account at [console.x.ai](https://console.x.ai).
2. Open **API Keys** and create a key.
3. Put it in `.env` (see below). Keys start with `xai-`.

## Setup

Requires Python 3.11+.

```bash
cd grok-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set XAI_API_KEY=xai-...
```

## Run

```bash
python -m grokbot
```

Open http://127.0.0.1:8000 — the UI loads, `/api/health` reports the model and
whether a key is configured. `HOST` and `PORT` env vars override the defaults
(`127.0.0.1:8000`).

## Configuration

| Env var | Default | Meaning |
|---------|---------|---------|
| `XAI_API_KEY` | — (required to chat) | xAI API key |
| `GROK_MODEL` | `grok-4.6` | chat model id |
| `XAI_BASE_URL` | `https://api.x.ai/v1` | OpenAI-compatible endpoint |
| `GROK_HISTORY_LIMIT` | `60` | max stored messages per session |

## API

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/health` | `{status, model, api_key_configured}` — always 200 |
| POST | `/api/sessions` | create a session (201) |
| GET | `/api/sessions` | list sessions, most recently updated first |
| GET | `/api/sessions/{id}` | session detail with messages |
| DELETE | `/api/sessions/{id}` | delete (204) |
| POST | `/api/sessions/{id}/messages` | `{content}` → `{reply, session}` |
| POST | `/api/sessions/{id}/messages/stream` | same input; SSE `{"type":"delta"}`… then `{"type":"done"}` |

Errors: empty message → 422 · unknown session → 404 · no/rejected key → 503 ·
xAI rate limit → 429 · other upstream failure → 502. Upstream error details are
never leaked to the client.

## Tests

The suite never calls xAI — the gateway is faked and SDK errors are constructed
locally.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Notes

- Sessions are **in-memory**: restarting the server clears all conversations.
- The Grok personality (witty, direct, maximally helpful) lives in
  `grokbot/persona.py` — it's a system prompt, not a safety override.
