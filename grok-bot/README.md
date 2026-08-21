# Grok Bot

A local chat console for [xAI's Grok](https://docs.x.ai/). Witty, direct, maximally helpful — served as a FastAPI app with a distinctive observatory-terminal UI.

This is the working chat product in the `ai-agent-super-skill` repo. The root `SKILL.md` remains the agent-builder reference.

## Features

- Streaming chat with Grok over SSE, with a **stop** button — partial replies are kept
- **Persistent threads** in SQLite (`data/grokbot.db` by default); survive restarts
- **Markdown rendering** of Grok replies: code blocks with language label + copy button, lists, headings, links, blockquotes
- **Retry** the last reply, **copy** any reply, **rename** (click the title) and **delete** threads
- Suggested prompts on empty threads, smart autoscroll with a jump-to-latest pill
- Grok personality via a system prompt
- Health check that reports model, store type, and whether `XAI_API_KEY` is set
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
| `GROKBOT_DB` | `data/grokbot.db` | SQLite path for persistent threads. `:memory:` = non-persistent store. |
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
| `GET` | `/health` | `{status, model, grok_configured, store}` |
| `GET` | `/` | Chat UI |
| `POST` | `/api/sessions` | Create a thread |
| `GET` | `/api/sessions` | List threads |
| `GET` | `/api/sessions/{id}` | Thread + messages |
| `PATCH` | `/api/sessions/{id}` | Rename: JSON `{title}` |
| `DELETE` | `/api/sessions/{id}` | Drop a thread |
| `POST` | `/api/chat` | JSON `{session_id, message}` → `{reply}` |
| `POST` | `/api/chat/stream` | Same body; SSE `data: {"delta": "..."}` then `[DONE]` |
| `POST` | `/api/chat/retry` | JSON `{session_id}`; drops the last reply and re-streams |

Stopping a stream mid-flight keeps the partial reply: the server persists
whatever was streamed when the client disconnects.

## Personality

Grok Bot talks like Grok: sharp, useful, lightly sarcastic. The prompt lives in `app/personality.py`.
