from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
import pytest

from app.errors import GrokAPIError, GrokAuthError, GrokConfigError, GrokRateLimitError
from app.main import create_app, stream_events
from app.sessions import Message, SessionStore, SQLiteSessionStore


class FakeGrok:
    def __init__(self, replies: list[str] | None = None, error: Exception | None = None) -> None:
        self.replies = list(replies or ["ok from grok"])
        self.error = error
        self.calls: list[list[Message]] = []

    def complete(self, history: list[Message]) -> str:
        self.calls.append(history)
        if self.error:
            raise self.error
        return self.replies.pop(0)

    def stream(self, history: list[Message]) -> Iterator[str]:
        self.calls.append(history)
        if self.error:
            raise self.error
        text = self.replies.pop(0)
        yield text[:2]
        yield text[2:]


@pytest.fixture
def store() -> SessionStore:
    return SessionStore()


@pytest.fixture
def grok() -> FakeGrok:
    return FakeGrok()


@pytest.fixture
def client(store: SessionStore, grok: FakeGrok) -> TestClient:
    app = create_app(store=store, grok=grok, settings_overrides={"xai_api_key": "test-key"})
    return TestClient(app)


def test_health_reports_model_and_configured_flag(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"] == "grok-4.6"
    assert body["grok_configured"] is True


def test_health_without_key_still_ok():
    app = create_app(store=SessionStore(), grok=FakeGrok(), settings_overrides={"xai_api_key": ""})
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["grok_configured"] is False


def test_create_and_fetch_session(client: TestClient):
    created = client.post("/api/sessions")
    assert created.status_code == 200
    session_id = created.json()["id"]
    fetched = client.get(f"/api/sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["messages"] == []
    assert fetched.json()["title"] == "New thread"


def test_list_sessions_includes_new_session(client: TestClient):
    session_id = client.post("/api/sessions").json()["id"]
    listed = client.get("/api/sessions")
    assert listed.status_code == 200
    ids = [s["id"] for s in listed.json()["sessions"]]
    assert session_id in ids


def test_unknown_session_is_404(client: TestClient):
    response = client.get("/api/sessions/missing")
    assert response.status_code == 404


def test_delete_session(client: TestClient):
    session_id = client.post("/api/sessions").json()["id"]
    deleted = client.delete(f"/api/sessions/{session_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/sessions/{session_id}").status_code == 404


def test_chat_appends_history_and_returns_reply(client: TestClient, grok: FakeGrok):
    session_id = client.post("/api/sessions").json()["id"]
    response = client.post("/api/chat", json={"session_id": session_id, "message": "hello grok"})
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "ok from grok"
    assert body["session_id"] == session_id
    history = client.get(f"/api/sessions/{session_id}").json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[0]["content"] == "hello grok"
    assert grok.calls[0][-1].content == "hello grok"


def test_empty_message_is_422(client: TestClient):
    session_id = client.post("/api/sessions").json()["id"]
    response = client.post("/api/chat", json={"session_id": session_id, "message": "   "})
    assert response.status_code == 422


def test_chat_unknown_session_is_404(client: TestClient):
    response = client.post("/api/chat", json={"session_id": "nope", "message": "hello"})
    assert response.status_code == 404


def test_missing_key_on_chat_is_503():
    store = SessionStore()
    grok = FakeGrok(error=GrokConfigError())
    app = create_app(store=store, grok=grok, settings_overrides={"xai_api_key": ""})
    test_client = TestClient(app)
    session_id = test_client.post("/api/sessions").json()["id"]
    response = test_client.post("/api/chat", json={"session_id": session_id, "message": "hello"})
    assert response.status_code == 503
    assert "XAI_API_KEY" in response.json()["detail"]


def test_rate_limit_on_chat_is_429(client: TestClient, grok: FakeGrok):
    grok.error = GrokRateLimitError()
    session_id = client.post("/api/sessions").json()["id"]
    response = client.post("/api/chat", json={"session_id": session_id, "message": "hello"})
    assert response.status_code == 429


def test_auth_error_on_chat_is_503(client: TestClient, grok: FakeGrok):
    grok.error = GrokAuthError()
    session_id = client.post("/api/sessions").json()["id"]
    response = client.post("/api/chat", json={"session_id": session_id, "message": "hello"})
    assert response.status_code == 503


def test_upstream_error_on_chat_is_502(client: TestClient, grok: FakeGrok):
    grok.error = GrokAPIError()
    session_id = client.post("/api/sessions").json()["id"]
    response = client.post("/api/chat", json={"session_id": session_id, "message": "hello"})
    assert response.status_code == 502


def test_failed_chat_does_not_store_assistant_reply(client: TestClient, grok: FakeGrok, store: SessionStore):
    grok.error = GrokAPIError()
    session_id = client.post("/api/sessions").json()["id"]
    client.post("/api/chat", json={"session_id": session_id, "message": "hello"})
    roles = [m.role for m in store.get(session_id).messages]
    assert roles == ["user"]


def test_stream_sends_sse_deltas_and_done(client: TestClient, grok: FakeGrok):
    grok.replies = ["Hello"]
    session_id = client.post("/api/sessions").json()["id"]
    with client.stream("POST", "/api/chat/stream", json={"session_id": session_id, "message": "hi"}) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = "".join(response.iter_text())
    assert "data:" in body
    assert "[DONE]" in body
    history = client.get(f"/api/sessions/{session_id}").json()["messages"]
    assert history[-1]["role"] == "assistant"
    assert history[-1]["content"] == "Hello"


def test_ui_is_served(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_health_reports_memory_store(client: TestClient):
    assert client.get("/health").json()["store"] == "memory"


def test_health_reports_sqlite_store(tmp_path, grok: FakeGrok):
    app = create_app(
        store=SQLiteSessionStore(tmp_path / "api.db"),
        grok=grok,
        settings_overrides={"xai_api_key": "test-key"},
    )
    assert TestClient(app).get("/health").json()["store"] == "sqlite"


def test_rename_session(client: TestClient):
    session_id = client.post("/api/sessions").json()["id"]
    response = client.patch(f"/api/sessions/{session_id}", json={"title": "  Slick new name  "})
    assert response.status_code == 200
    assert response.json()["title"] == "Slick new name"
    assert client.get(f"/api/sessions/{session_id}").json()["title"] == "Slick new name"


def test_rename_unknown_session_is_404(client: TestClient):
    response = client.patch("/api/sessions/missing", json={"title": "anything"})
    assert response.status_code == 404


def test_rename_blank_title_is_422(client: TestClient):
    session_id = client.post("/api/sessions").json()["id"]
    response = client.patch(f"/api/sessions/{session_id}", json={"title": "   "})
    assert response.status_code == 422


def test_retry_replaces_last_assistant_reply(client: TestClient, grok: FakeGrok, store: SessionStore):
    grok.replies = ["first answer", "second answer"]
    session_id = client.post("/api/sessions").json()["id"]
    client.post("/api/chat", json={"session_id": session_id, "message": "question"})

    with client.stream("POST", "/api/chat/retry", json={"session_id": session_id}) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = "".join(response.iter_text())
    assert "[DONE]" in body

    history = client.get(f"/api/sessions/{session_id}").json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[-1]["content"] == "second answer"
    # The retried call must not include the dropped reply in its prompt history.
    assert [m.content for m in grok.calls[-1]] == ["question"]


def test_retry_unknown_session_is_404(client: TestClient):
    response = client.post("/api/chat/retry", json={"session_id": "nope"})
    assert response.status_code == 404


def test_retry_with_no_user_message_is_409(client: TestClient):
    session_id = client.post("/api/sessions").json()["id"]
    response = client.post("/api/chat/retry", json={"session_id": session_id})
    assert response.status_code == 409


class DrippingGrok:
    """Streams a fixed list of tokens; used to observe partial consumption."""

    def __init__(self, tokens: list[str], error_after: int | None = None) -> None:
        self.tokens = tokens
        self.error_after = error_after

    def stream(self, history: list[Message]) -> Iterator[str]:
        for index, token in enumerate(self.tokens):
            if self.error_after is not None and index == self.error_after:
                raise GrokAPIError()
            yield token


def test_client_disconnect_persists_partial_reply(store: SessionStore):
    session = store.create()
    store.append(session.id, "user", "stream me something long")
    history = list(store.get(session.id).messages)
    grok = DrippingGrok(["alpha ", "beta ", "gamma"])

    events = stream_events(store, grok, session.id, history)
    assert "alpha" in next(events)
    assert "beta" in next(events)
    events.close()  # simulates the client disconnecting mid-stream

    messages = store.get(session.id).messages
    assert messages[-1].role == "assistant"
    assert messages[-1].content == "alpha beta "


def test_mid_stream_error_persists_partial_and_reports(store: SessionStore):
    session = store.create()
    store.append(session.id, "user", "go")
    history = list(store.get(session.id).messages)
    grok = DrippingGrok(["partial ", "never-sent"], error_after=1)

    frames = list(stream_events(store, grok, session.id, history))
    assert any("partial" in frame for frame in frames)
    assert any("error" in frame for frame in frames)

    messages = store.get(session.id).messages
    assert messages[-1].role == "assistant"
    assert messages[-1].content == "partial "


def test_completed_stream_persists_reply_exactly_once(store: SessionStore):
    session = store.create()
    store.append(session.id, "user", "hi")
    history = list(store.get(session.id).messages)
    grok = DrippingGrok(["Hel", "lo"])

    frames = list(stream_events(store, grok, session.id, history))
    assert frames[-1] == "data: [DONE]\n\n"

    messages = store.get(session.id).messages
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[-1].content == "Hello"
