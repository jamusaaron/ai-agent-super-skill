from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


class SessionNotFound(KeyError):
    """Raised when a chat session id is unknown."""


@dataclass
class Message:
    role: str
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Session:
    id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    title: str = "New thread"
    messages: list[Message] = field(default_factory=list)

    @property
    def preview(self) -> str:
        for message in reversed(self.messages):
            if message.role == "user":
                return message.content
        return ""


MAX_MESSAGES = 40


class SessionStore:
    """In-memory conversation store. Sessions vanish when the process dies."""

    def __init__(self, max_messages: int = MAX_MESSAGES) -> None:
        self.max_messages = max_messages
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        session = Session(id=str(uuid4()))
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFound(session_id) from exc

    def list(self) -> list[Session]:
        return sorted(
            self._sessions.values(),
            key=lambda session: session.updated_at,
            reverse=True,
        )

    def delete(self, session_id: str) -> None:
        if session_id not in self._sessions:
            raise SessionNotFound(session_id)
        del self._sessions[session_id]

    def append(self, session_id: str, role: str, content: str) -> Message:
        session = self.get(session_id)
        message = Message(role=role, content=content)
        session.messages.append(message)
        if len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages :]
        if role == "user" and session.title == "New thread":
            session.title = _title_from(content)
        session.updated_at = message.created_at
        return message


def _title_from(content: str, limit: int = 48) -> str:
    text = " ".join(content.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
