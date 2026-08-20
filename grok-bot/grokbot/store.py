"""In-memory conversation session store.

Sessions live for the lifetime of the process. History is capped so a single
session cannot grow without bound; the oldest messages are dropped first.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

DEFAULT_HISTORY_LIMIT = 60
TITLE_MAX_CHARS = 60


class UnknownSession(KeyError):
    """Raised when a session id does not exist in the store."""


@dataclass
class Message:
    role: str
    content: str
    created_at: float


@dataclass
class ChatSession:
    id: str
    created_at: float
    updated_at: float
    title: str | None = None
    messages: list[Message] = field(default_factory=list)


class SessionStore:
    def __init__(self, history_limit: int = DEFAULT_HISTORY_LIMIT) -> None:
        self._history_limit = history_limit
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def create(self) -> ChatSession:
        now = time.time()
        session = ChatSession(id=str(uuid.uuid4()), created_at=now, updated_at=now)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> ChatSession:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError:
                raise UnknownSession(session_id) from None

    def list(self) -> list[ChatSession]:
        with self._lock:
            return sorted(
                self._sessions.values(), key=lambda s: s.updated_at, reverse=True
            )

    def append(self, session_id: str, role: str, content: str) -> Message:
        message = Message(role=role, content=content, created_at=time.time())
        with self._lock:
            try:
                session = self._sessions[session_id]
            except KeyError:
                raise UnknownSession(session_id) from None
            session.messages.append(message)
            if len(session.messages) > self._history_limit:
                del session.messages[: len(session.messages) - self._history_limit]
            if session.title is None and role == "user":
                session.title = content[:TITLE_MAX_CHARS]
            session.updated_at = message.created_at
        return message

    def delete(self, session_id: str) -> None:
        with self._lock:
            try:
                del self._sessions[session_id]
            except KeyError:
                raise UnknownSession(session_id) from None
