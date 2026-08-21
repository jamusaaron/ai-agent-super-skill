from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.config import Settings
from app.errors import GrokError
from app.grok import GrokClient
from app.sessions import Session, SessionNotFound, SessionStore, SQLiteSessionStore

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "grokbot.db"


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message cannot be empty")
        return cleaned


class RetryRequest(BaseModel):
    session_id: str


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be empty")
        return cleaned


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    preview: str = ""
    messages: list[MessageOut] = []


def _session_out(session: Session, include_messages: bool = False) -> SessionOut:
    return SessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        preview=session.preview,
        messages=[
            MessageOut(role=m.role, content=m.content, created_at=m.created_at)
            for m in session.messages
        ]
        if include_messages
        else [],
    )


def _default_store(settings: Settings) -> SessionStore | SQLiteSessionStore:
    if settings.grokbot_db == ":memory:":
        return SessionStore()
    return SQLiteSessionStore(settings.grokbot_db or DEFAULT_DB_PATH)


def stream_events(store, grok, session_id: str, history: list) :
    """SSE generator for a chat reply.

    Persists the full reply on completion, and whatever tokens were streamed
    if the client disconnects (GeneratorExit) or the upstream errors mid-way —
    so stopping generation keeps the partial answer.
    """
    pieces: list[str] = []
    saved = False

    def persist() -> None:
        nonlocal saved
        if pieces and not saved:
            store.append(session_id, "assistant", "".join(pieces))
            saved = True

    try:
        for token in grok.stream(history):
            pieces.append(token)
            yield f"data: {json.dumps({'delta': token})}\n\n"
        persist()
        yield "data: [DONE]\n\n"
    except GeneratorExit:
        persist()
        raise
    except GrokError as exc:
        persist()
        yield f"data: {json.dumps({'error': exc.message, 'status': exc.status_code})}\n\n"


def create_app(
    store: SessionStore | None = None,
    grok: GrokClient | None = None,
    settings_overrides: dict | None = None,
) -> FastAPI:
    settings = Settings()
    if settings_overrides:
        settings = settings.model_copy(update=settings_overrides)
    store = store or _default_store(settings)
    grok = grok or GrokClient(
        api_key=settings.xai_api_key,
        model=settings.grok_model,
        base_url=settings.xai_base_url,
    )

    app = FastAPI(title="Grok Bot", version="1.0.0")
    app.state.settings = settings
    app.state.store = store
    app.state.grok = grok

    store_kind = "sqlite" if isinstance(store, SQLiteSessionStore) else "memory"

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "model": settings.grok_model,
            "grok_configured": settings.grok_configured,
            "store": store_kind,
        }

    @app.post("/api/sessions")
    def create_session() -> SessionOut:
        return _session_out(store.create())

    @app.get("/api/sessions")
    def list_sessions() -> dict:
        return {"sessions": [_session_out(s) for s in store.list()]}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> SessionOut:
        return _session_out(_require_session(store, session_id), include_messages=True)

    @app.delete("/api/sessions/{session_id}", status_code=204)
    def delete_session(session_id: str) -> None:
        try:
            store.delete(session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="Unknown session.") from exc

    @app.patch("/api/sessions/{session_id}")
    def rename_session(session_id: str, request: RenameRequest) -> SessionOut:
        try:
            store.rename(session_id, request.title)
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="Unknown session.") from exc
        return _session_out(store.get(session_id))

    @app.post("/api/chat")
    def chat(request: ChatRequest) -> dict:
        session = _require_session(store, request.session_id)
        store.append(session.id, "user", request.message)
        history = list(store.get(session.id).messages)
        try:
            reply = grok.complete(history)
        except GrokError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        store.append(session.id, "assistant", reply)
        return {"session_id": session.id, "reply": reply}

    @app.post("/api/chat/stream")
    def chat_stream(request: ChatRequest) -> StreamingResponse:
        session = _require_session(store, request.session_id)
        store.append(session.id, "user", request.message)
        history = list(store.get(session.id).messages)
        return StreamingResponse(
            stream_events(store, grok, session.id, history),
            media_type="text/event-stream",
        )

    @app.post("/api/chat/retry")
    def chat_retry(request: RetryRequest) -> StreamingResponse:
        session = _require_session(store, request.session_id)
        store.drop_last_assistant(session.id)
        history = list(store.get(session.id).messages)
        if not history or history[-1].role != "user":
            raise HTTPException(status_code=409, detail="Nothing to retry yet.")
        return StreamingResponse(
            stream_events(store, grok, session.id, history),
            media_type="text/event-stream",
        )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    if FRONTEND_DIR.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

    return app


def _require_session(store: SessionStore, session_id: str) -> Session:
    try:
        return store.get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Unknown session.") from exc


app = create_app()
