# Grok Bot

A local chat console for [xAI's Grok](https://docs.x.ai/). Witty, direct, maximally helpful — served as a FastAPI app with a distinctive observatory-terminal UI.

This is the working chat product in the `ai-agent-super-skill` repo. The root `SKILL.md` remains the agent-builder reference.

## Features

- Streaming chat with Grok over SSE
- Per-session conversation history (in memory; resets when the process stops)
- Grok personality via a system prompt
- Health check that reports model + whether `XAI_API_KEY` is set
- Typed errors for missing key, auth failure, rate limits, and upstream API issues

## Get an xAI API key

1. Create an account at [console.x.ai](https://console.x.ai/)
2. Add credits
3. Generate a key on the [API Keys](https://console.x.ai/team/default/api-keys) page
4. Export it as `XAI_API_KEY`

Docs: [xAI quickstart](https://docs.x.ai/docs/tutorial)

## Setup

```bash
cd grok-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# put your real key in .env — never commit it
```

## Run

```bash
cd grok-bot
python -m app
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Or with uvicorn:

```bash
cd grok-bot
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `XAI_API_KEY` | _(empty)_ | Required for chat. Health still works without it. |
| `GROK_MODEL` | `grok-4.6` | Current documented xAI chat model. `grok-4` still aliases. |
| `XAI_BASE_URL` | `https://api.x.ai/v1` | OpenAI-compatible xAI endpoint |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Bind port |

## Tests

Tests mock the xAI API. They never spend credits.

```bash
cd grok-bot
python -m pytest -v
```

## API

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/health` | `{status, model, grok_configured}` |
| `GET` | `/` | Chat UI |
| `POST` | `/api/sessions` | Create a thread |
| `GET` | `/api/sessions` | List threads |
| `GET` | `/api/sessions/{id}` | Thread + messages |
| `DELETE` | `/api/sessions/{id}` | Drop a thread |
| `POST` | `/api/chat` | JSON `{session_id, message}` → `{reply}` |
| `POST` | `/api/chat/stream` | Same body; SSE `data: {"delta": "..."}` then `[DONE]` |

## Personality

Grok Bot talks like Grok: sharp, useful, lightly sarcastic. The prompt lives in `app/personality.py`.
