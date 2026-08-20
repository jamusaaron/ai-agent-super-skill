# Grok Bot — Implementation Plan (replication attempt)

Execute inline, TDD throughout (failing test → minimal code → green → commit).
No PR — push branch `cursor/grok-bot-replica-a954` only.

**Layout:** app in `grok-bot/` — package `grokbot/`, static UI `web/`, tests `tests/`.

## Task 1 — SessionStore (TDD)
- `tests/test_store.py`: create/get/list/append/delete, unknown-session error,
  title from first user message (60 chars), 60-message cap, updated ordering.
- Implement `grokbot/store.py`. Scaffold `pytest.ini`, `requirements*.txt`.
- Commit.

## Task 2 — Settings, persona, GrokGateway (TDD)
- `tests/test_gateway.py`: fake OpenAI client; reply extraction; stream chunk
  extraction; mapping missing key → GrokNotConfigured, 401 → GrokKeyRejected,
  429 → GrokThrottled, other/API/connection → GrokUpstreamError.
- Implement `grokbot/{settings,exceptions,persona,gateway}.py`.
- Commit.

## Task 3 — FastAPI app (TDD)
- `tests/test_api.py`: health; session CRUD; chat happy path (fake gateway sees
  system prompt + history); SSE stream event protocol; 422/404/503/429/502 mapping.
- Implement `grokbot/api.py` (+ `__main__.py`).
- Commit.

## Task 4 — Frontend + docs
- Read frontend-design skill first. Build `web/{index.html,styles.css,app.js}`
  per "The Wire" design. `.env.example`, `grok-bot/README.md`, root README pointer.
- Commit.

## Task 5 — Verification (no claims without evidence)
- Fresh venv install from requirements-dev; full pytest run; uvicorn smoke test:
  server boots, `/api/health` 200, `/` serves UI.
- Fix anything found, commit, push with retries.
