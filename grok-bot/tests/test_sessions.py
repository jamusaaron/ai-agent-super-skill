from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.sessions import SessionNotFound, SessionStore


def test_create_session_returns_uuid_and_empty_messages():
    store = SessionStore()
    session = store.create()
    assert session.id
    assert session.messages == []
    assert session.title == "New thread"
    fetched = store.get(session.id)
    assert fetched.id == session.id


def test_append_user_and_assistant_messages_keeps_order():
    store = SessionStore()
    session = store.create()
    store.append(session.id, "user", "hello grok")
    store.append(session.id, "assistant", "hey")
    messages = store.get(session.id).messages
    assert [m.role for m in messages] == ["user", "assistant"]
    assert [m.content for m in messages] == ["hello grok", "hey"]
    assert all(m.created_at.tzinfo is not None for m in messages)


def test_first_user_message_becomes_title():
    store = SessionStore()
    session = store.create()
    store.append(session.id, "user", "Explain black holes without the usual TED-talk voice")
    assert store.get(session.id).title.startswith("Explain black holes")


def test_title_only_set_from_first_user_message():
    store = SessionStore()
    session = store.create()
    store.append(session.id, "assistant", "greetings, human")
    assert store.get(session.id).title == "New thread"
    store.append(session.id, "user", "first question")
    store.append(session.id, "user", "second question")
    assert store.get(session.id).title == "first question"


def test_title_truncates_at_48_characters():
    store = SessionStore()
    session = store.create()
    store.append(session.id, "user", "x" * 80)
    title = store.get(session.id).title
    assert len(title) == 48
    assert title.endswith("…")


def test_unknown_session_raises():
    store = SessionStore()
    with pytest.raises(SessionNotFound):
        store.get("does-not-exist")


def test_append_to_unknown_session_raises():
    store = SessionStore()
    with pytest.raises(SessionNotFound):
        store.append("no-such-session", "user", "hello")


def test_delete_session_removes_it():
    store = SessionStore()
    session = store.create()
    store.delete(session.id)
    with pytest.raises(SessionNotFound):
        store.get(session.id)


def test_delete_unknown_session_raises():
    store = SessionStore()
    with pytest.raises(SessionNotFound):
        store.delete("no-such-session")


def test_list_sessions_newest_first():
    store = SessionStore()
    a = store.create()
    b = store.create()
    store.append(a.id, "user", "older")
    store.append(b.id, "user", "newer")
    listed = store.list()
    assert [s.id for s in listed] == [b.id, a.id]
    assert listed[0].preview == "newer"


def test_list_returns_sessions_most_recently_updated_first():
    store = SessionStore()
    older = store.create()
    newer = store.create()
    store.append(older.id, "user", "a")
    store.append(newer.id, "user", "b")
    store.append(older.id, "user", "c")
    assert [s.id for s in store.list()] == [older.id, newer.id]


def test_history_cap_drops_oldest_messages():
    store = SessionStore(max_messages=4)
    session = store.create()
    for i in range(6):
        role = "user" if i % 2 == 0 else "assistant"
        store.append(session.id, role, f"m{i}")
    contents = [m.content for m in store.get(session.id).messages]
    assert contents == ["m2", "m3", "m4", "m5"]


def test_created_at_is_timezone_aware():
    store = SessionStore()
    session = store.create()
    assert session.created_at.tzinfo == timezone.utc
    assert isinstance(session.created_at, datetime)


def test_append_updates_updated_at():
    store = SessionStore()
    session = store.create()
    before = session.updated_at
    store.append(session.id, "user", "hello")
    assert store.get(session.id).updated_at >= before
