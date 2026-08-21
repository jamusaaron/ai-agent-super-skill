from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
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
DEFAULT_TITLE = "New thread"


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
        if role == "user" and session.title == DEFAULT_TITLE:
            session.title = _title_from(content)
        session.updated_at = message.created_at
        return message

    def rename(self, session_id: str, title: str) -> None:
        self.get(session_id).title = title

    def drop_last_assistant(self, session_id: str) -> bool:
        session = self.get(session_id)
        if session.messages and session.messages[-1].role == "assistant":
            session.messages.pop()
            return True
        return False


_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, seq);
"""


class SQLiteSessionStore:
    """SQLite-backed conversation store. Sessions survive server restarts.

    Same interface as SessionStore. The connection is opened lazily so that
    importing the app never touches the filesystem; a single connection is
    shared across threads behind a lock (FastAPI runs sync endpoints in a
    threadpool).
    """

    def __init__(self, db_path: str | Path, max_messages: int = MAX_MESSAGES) -> None:
        self.db_path = str(db_path)
        self.max_messages = max_messages
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    @property
    def _conn(self) -> sqlite3.Connection:
        if self._connection is None:
            parent = Path(self.db_path).parent
            if str(parent):
                parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.db_path, check_same_thread=False)
            connection.executescript(_SQLITE_SCHEMA)
            connection.commit()
            self._connection = connection
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def create(self) -> Session:
        session = Session(id=str(uuid4()))
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (
                    session.id,
                    session.title,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
            self._conn.commit()
        return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            return self._get_unlocked(session_id)

    def _get_unlocked(self, session_id: str) -> Session:
        row = self._conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise SessionNotFound(session_id)
        messages = [
            Message(role=role, content=content, created_at=datetime.fromisoformat(created_at))
            for role, content, created_at in self._conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY seq",
                (session_id,),
            )
        ]
        return Session(
            id=row[0],
            title=row[1],
            created_at=datetime.fromisoformat(row[2]),
            updated_at=datetime.fromisoformat(row[3]),
            messages=messages,
        )

    def list(self) -> list[Session]:
        with self._lock:
            ids = [row[0] for row in self._conn.execute("SELECT id FROM sessions")]
            sessions = [self._get_unlocked(session_id) for session_id in ids]
        return sorted(sessions, key=lambda session: session.updated_at, reverse=True)

    def delete(self, session_id: str) -> None:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            if cursor.rowcount == 0:
                raise SessionNotFound(session_id)
            self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self._conn.commit()

    def append(self, session_id: str, role: str, content: str) -> Message:
        message = Message(role=role, content=content)
        with self._lock:
            row = self._conn.execute(
                "SELECT title FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                raise SessionNotFound(session_id)
            self._conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, message.created_at.isoformat()),
            )
            self._conn.execute(
                """
                DELETE FROM messages
                WHERE session_id = ?
                  AND seq NOT IN (
                    SELECT seq FROM messages WHERE session_id = ?
                    ORDER BY seq DESC LIMIT ?
                  )
                """,
                (session_id, session_id, self.max_messages),
            )
            title = row[0]
            if role == "user" and title == DEFAULT_TITLE:
                self._conn.execute(
                    "UPDATE sessions SET title = ? WHERE id = ?",
                    (_title_from(content), session_id),
                )
            self._conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (message.created_at.isoformat(), session_id),
            )
            self._conn.commit()
        return message

    def rename(self, session_id: str, title: str) -> None:
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
            )
            if cursor.rowcount == 0:
                raise SessionNotFound(session_id)
            self._conn.commit()

    def drop_last_assistant(self, session_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                raise SessionNotFound(session_id)
            last = self._conn.execute(
                "SELECT seq, role FROM messages WHERE session_id = ? ORDER BY seq DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if last is None or last[1] != "assistant":
                return False
            self._conn.execute("DELETE FROM messages WHERE seq = ?", (last[0],))
            self._conn.commit()
            return True


def _title_from(content: str, limit: int = 48) -> str:
    text = " ".join(content.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
