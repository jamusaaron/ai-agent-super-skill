"""API tests. The Grok gateway is always faked; no network calls happen here."""

import json

from grokbot.exceptions import (
    GrokKeyRejected,
    GrokNotConfigured,
    GrokThrottled,
    GrokUpstreamError,
)
from grokbot.persona import SYSTEM_PROMPT

from .conftest import FakeGateway, client_for


def sse_events(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: ") :])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


# --- health & UI -----------------------------------------------------------


def test_health_reports_ok_model_and_key_state(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model": "grok-test",
        "api_key_configured": True,
    }


def test_health_is_200_even_without_api_key():
    response = client_for(FakeGateway(configured=False)).get("/api/health")

    assert response.status_code == 200
    assert response.json()["api_key_configured"] is False


def test_root_serves_the_chat_ui(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


# --- session CRUD ----------------------------------------------------------


def test_create_session_returns_empty_session(client):
    response = client.post("/api/sessions")

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["title"] is None
    assert body["messages"] == []


def test_list_sessions_most_recent_first_with_counts(client):
    first = client.post("/api/sessions").json()["id"]
    second = client.post("/api/sessions").json()["id"]
    client.post(f"/api/sessions/{second}/messages", json={"content": "hi"})
    client.post(f"/api/sessions/{first}/messages", json={"content": "yo"})

    body = client.get("/api/sessions").json()

    assert [s["id"] for s in body["sessions"]] == [first, second]
    assert body["sessions"][0]["message_count"] == 2  # user + assistant
    assert body["sessions"][0]["title"] == "yo"


def test_get_session_returns_ordered_messages(client):
    session_id = client.post("/api/sessions").json()["id"]
    client.post(f"/api/sessions/{session_id}/messages", json={"content": "hello"})

    body = client.get(f"/api/sessions/{session_id}").json()

    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["content"] == "hello"
    assert body["messages"][1]["content"] == "canned reply"


def test_get_unknown_session_is_404(client):
    assert client.get("/api/sessions/nope").status_code == 404


def test_delete_session(client):
    session_id = client.post("/api/sessions").json()["id"]

    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert client.get(f"/api/sessions/{session_id}").status_code == 404


def test_delete_unknown_session_is_404(client):
    assert client.delete("/api/sessions/nope").status_code == 404


# --- chat (non-streaming) --------------------------------------------------


def test_chat_sends_persona_history_and_message_to_grok(client, gateway):
    session_id = client.post("/api/sessions").json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "hello grok"}
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "canned reply"
    (sent,) = gateway.calls
    assert sent[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert sent[-1] == {"role": "user", "content": "hello grok"}


def test_chat_second_turn_includes_prior_history(client, gateway):
    session_id = client.post("/api/sessions").json()["id"]
    client.post(f"/api/sessions/{session_id}/messages", json={"content": "first"})

    client.post(f"/api/sessions/{session_id}/messages", json={"content": "second"})

    second_call = gateway.calls[1]
    roles_and_content = [(m["role"], m["content"]) for m in second_call]
    assert roles_and_content == [
        ("system", SYSTEM_PROMPT),
        ("user", "first"),
        ("assistant", "canned reply"),
        ("user", "second"),
    ]


def test_chat_response_includes_updated_session(client):
    session_id = client.post("/api/sessions").json()["id"]

    body = client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "name this thread"}
    ).json()

    assert body["session"]["title"] == "name this thread"
    assert len(body["session"]["messages"]) == 2


def test_empty_message_is_422(client):
    session_id = client.post("/api/sessions").json()["id"]

    assert (
        client.post(f"/api/sessions/{session_id}/messages", json={"content": ""})
    ).status_code == 422
    assert (
        client.post(f"/api/sessions/{session_id}/messages", json={"content": "  \t "})
    ).status_code == 422


def test_chat_to_unknown_session_is_404(client):
    response = client.post("/api/sessions/nope/messages", json={"content": "hi"})

    assert response.status_code == 404


def test_missing_key_is_503_and_message_not_stored():
    gateway = FakeGateway(error=GrokNotConfigured(), configured=False)
    client = client_for(gateway)
    session_id = client.post("/api/sessions").json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "hi"}
    )

    assert response.status_code == 503
    assert "XAI_API_KEY" in response.json()["detail"]
    assert client.get(f"/api/sessions/{session_id}").json()["messages"] == []


def test_rejected_key_is_503():
    client = client_for(FakeGateway(error=GrokKeyRejected()))
    session_id = client.post("/api/sessions").json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "hi"}
    )

    assert response.status_code == 503
    assert "key" in response.json()["detail"].lower()


def test_rate_limit_is_429():
    client = client_for(FakeGateway(error=GrokThrottled()))
    session_id = client.post("/api/sessions").json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "hi"}
    )

    assert response.status_code == 429


def test_upstream_failure_is_502_with_safe_message():
    client = client_for(FakeGateway(error=GrokUpstreamError("secret-internal-detail")))
    session_id = client.post("/api/sessions").json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "hi"}
    )

    assert response.status_code == 502
    assert "secret-internal-detail" not in response.json()["detail"]


# --- chat (streaming) ------------------------------------------------------


def test_stream_emits_deltas_then_done_and_stores_reply(client):
    session_id = client.post("/api/sessions").json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages/stream", json={"content": "hi"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse_events(response.text)
    assert events[:-1] == [
        {"type": "delta", "text": "canned "},
        {"type": "delta", "text": "reply"},
    ]
    assert events[-1]["type"] == "done"

    messages = client.get(f"/api/sessions/{session_id}").json()["messages"]
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "hi"),
        ("assistant", "canned reply"),
    ]


def test_stream_without_key_is_503_before_streaming():
    client = client_for(FakeGateway(configured=False))
    session_id = client.post("/api/sessions").json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages/stream", json={"content": "hi"}
    )

    assert response.status_code == 503


def test_stream_error_midway_emits_error_event_and_stores_nothing():
    client = client_for(FakeGateway(error=GrokThrottled()))
    session_id = client.post("/api/sessions").json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages/stream", json={"content": "hi"}
    )

    assert response.status_code == 200
    events = sse_events(response.text)
    assert events[-1]["type"] == "error"
    assert "rate" in events[-1]["message"].lower()
    assert client.get(f"/api/sessions/{session_id}").json()["messages"] == []


def test_stream_to_unknown_session_is_404(client):
    response = client.post("/api/sessions/nope/messages/stream", json={"content": "x"})

    assert response.status_code == 404
