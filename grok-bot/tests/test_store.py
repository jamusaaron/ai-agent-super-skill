"""Unit tests for the in-memory session store."""

import uuid

import pytest

from grokbot.store import DEFAULT_HISTORY_LIMIT, SessionStore, UnknownSession


@pytest.fixture()
def store() -> SessionStore:
    return SessionStore()


def test_create_returns_empty_session_with_uuid(store: SessionStore):
    session = store.create()

    uuid.UUID(session.id)  # invalid UUID would raise ValueError
    assert session.messages == []
    assert session.title is None
    assert session.created_at > 0
    assert session.updated_at == session.created_at


def test_get_returns_the_created_session(store: SessionStore):
    session = store.create()

    assert store.get(session.id) is session


def test_get_unknown_id_raises(store: SessionStore):
    with pytest.raises(UnknownSession):
        store.get("not-a-session")


def test_append_stores_message_in_order(store: SessionStore):
    session = store.create()

    first = store.append(session.id, "user", "hello")
    second = store.append(session.id, "assistant", "hi there")

    assert [m.content for m in session.messages] == ["hello", "hi there"]
    assert first.role == "user"
    assert second.role == "assistant"
    assert first.created_at > 0


def test_append_to_unknown_session_raises(store: SessionStore):
    with pytest.raises(UnknownSession):
        store.append("not-a-session", "user", "hello")


def test_title_comes_from_first_user_message_truncated_to_60_chars(store: SessionStore):
    session = store.create()

    store.append(session.id, "assistant", "unsolicited greeting")
    assert session.title is None

    store.append(session.id, "user", "a" * 100)
    store.append(session.id, "user", "later message")

    assert session.title == "a" * 60


def test_history_capped_dropping_oldest_messages(store: SessionStore):
    session = store.create()

    total = DEFAULT_HISTORY_LIMIT + 7
    for i in range(total):
        store.append(session.id, "user", f"m{i}")

    assert len(session.messages) == DEFAULT_HISTORY_LIMIT
    assert session.messages[0].content == "m7"
    assert session.messages[-1].content == f"m{total - 1}"


def test_custom_history_limit(store: SessionStore):
    small = SessionStore(history_limit=4)
    session = small.create()

    for i in range(6):
        small.append(session.id, "user", f"m{i}")

    assert [m.content for m in session.messages] == ["m2", "m3", "m4", "m5"]


def test_list_orders_by_most_recently_updated(store: SessionStore):
    first = store.create()
    second = store.create()

    store.append(second.id, "user", "b")
    store.append(first.id, "user", "a")  # first is now the most recent

    assert [s.id for s in store.list()] == [first.id, second.id]


def test_append_advances_updated_at(store: SessionStore):
    session = store.create()
    before = session.updated_at

    store.append(session.id, "user", "hello")

    assert session.updated_at >= before


def test_delete_removes_session(store: SessionStore):
    session = store.create()

    store.delete(session.id)

    with pytest.raises(UnknownSession):
        store.get(session.id)


def test_delete_unknown_session_raises(store: SessionStore):
    with pytest.raises(UnknownSession):
        store.delete("not-a-session")
