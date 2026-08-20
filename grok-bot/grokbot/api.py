"""HTTP layer: FastAPI app factory wiring the store, gateway, and static UI."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from .exceptions import (
    GrokError,
    GrokKeyRejected,
    GrokNotConfigured,
    GrokThrottled,
    GrokUpstreamError,
)
from .gateway import GrokGateway
from .persona import SYSTEM_PROMPT
from .settings import Settings
from .store import ChatSession, Message, SessionStore, UnknownSession

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

_ERROR_RESPONSES: list[tuple[type[GrokError], int, str]] = [
    (
        GrokNotConfigured,
        503,
        "Grok Bot has no XAI_API_KEY configured. Add it to .env — see the README.",
    ),
    (GrokKeyRejected, 503, "xAI rejected the configured API key. Check XAI_API_KEY."),
    (GrokThrottled, 429, "xAI is rate-limiting this key. Wait a moment and try again."),
    (
        GrokUpstreamError,
        502,
        "Grok didn't answer — the xAI API returned an error. Try again.",
    ),
]


def _status_and_message(exc: GrokError) -> tuple[int, str]:
    for cls, status, message in _ERROR_RESPONSES:
        if isinstance(exc, cls):
            return status, message
    return 502, "Grok didn't answer — the xAI API returned an error. Try again."


class MessageIn(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


def _message_json(message: Message) -> dict:
    return {
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
    }


def _session_json(session: ChatSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": [_message_json(m) for m in session.messages],
    }


def _session_summary(session: ChatSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(session.messages),
    }


def create_app(
    settings: Settings | None = None,
    store: SessionStore | None = None,
    gateway: GrokGateway | None = None,
) -> FastAPI:
    settings = settings or Settings()
    store = store or SessionStore(history_limit=settings.grok_history_limit)
    gateway = gateway or GrokGateway(settings)

    app = FastAPI(title="Grok Bot", docs_url=None, redoc_url=None)

    def get_or_404(session_id: str) -> ChatSession:
        try:
            return store.get(session_id)
        except UnknownSession:
            raise HTTPException(status_code=404, detail="No such session.") from None

    def grok_payload(session: ChatSession, new_content: str) -> list[dict]:
        return (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + [{"role": m.role, "content": m.content} for m in session.messages]
            + [{"role": "user", "content": new_content}]
        )

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "model": gateway.model,
            "api_key_configured": gateway.configured,
        }

    @app.post("/api/sessions", status_code=201)
    def create_session() -> dict:
        return _session_json(store.create())

    @app.get("/api/sessions")
    def list_sessions() -> dict:
        return {"sessions": [_session_summary(s) for s in store.list()]}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        return _session_json(get_or_404(session_id))

    @app.delete("/api/sessions/{session_id}", status_code=204)
    def delete_session(session_id: str) -> Response:
        get_or_404(session_id)
        store.delete(session_id)
        return Response(status_code=204)

    @app.post("/api/sessions/{session_id}/messages")
    def send_message(session_id: str, body: MessageIn) -> dict:
        session = get_or_404(session_id)
        try:
            reply = gateway.reply(grok_payload(session, body.content))
        except GrokError as exc:
            status, message = _status_and_message(exc)
            raise HTTPException(status_code=status, detail=message) from exc
        # Stored only after Grok answered, so a failed call never pollutes history.
        store.append(session_id, "user", body.content)
        store.append(session_id, "assistant", reply)
        return {"reply": reply, "session": _session_json(store.get(session_id))}

    @app.post("/api/sessions/{session_id}/messages/stream")
    def stream_message(session_id: str, body: MessageIn) -> StreamingResponse:
        session = get_or_404(session_id)
        if not gateway.configured:
            status, message = _status_and_message(GrokNotConfigured())
            raise HTTPException(status_code=status, detail=message)
        payload = grok_payload(session, body.content)

        def event_source():
            parts: list[str] = []
            try:
                for delta in gateway.stream_reply(payload):
                    parts.append(delta)
                    yield f"data: {json.dumps({'type': 'delta', 'text': delta})}\n\n"
            except GrokError as exc:
                _, message = _status_and_message(exc)
                yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
                return
            try:
                store.append(session_id, "user", body.content)
                store.append(session_id, "assistant", "".join(parts))
            except UnknownSession:
                pass  # session deleted while the reply was streaming
            yield 'data: {"type": "done"}\n\n'

        return StreamingResponse(event_source(), media_type="text/event-stream")

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

    return app
