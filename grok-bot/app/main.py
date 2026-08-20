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
from app.sessions import Session, SessionNotFound, SessionStore

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


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


def create_app(
    store: SessionStore | None = None,
    grok: GrokClient | None = None,
    settings_overrides: dict | None = None,
) -> FastAPI:
    settings = Settings()
    if settings_overrides:
        settings = settings.model_copy(update=settings_overrides)
    store = store or SessionStore()
    grok = grok or GrokClient(
        api_key=settings.xai_api_key,
        model=settings.grok_model,
        base_url=settings.xai_base_url,
    )

    app = FastAPI(title="Grok Bot", version="1.0.0")
    app.state.settings = settings
    app.state.store = store
    app.state.grok = grok

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "model": settings.grok_model,
            "grok_configured": settings.grok_configured,
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

        def events():
            pieces: list[str] = []
            try:
                for token in grok.stream(history):
                    pieces.append(token)
                    yield f"data: {json.dumps({'delta': token})}\n\n"
                store.append(session.id, "assistant", "".join(pieces))
                yield "data: [DONE]\n\n"
            except GrokError as exc:
                yield f"data: {json.dumps({'error': exc.message, 'status': exc.status_code})}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

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
