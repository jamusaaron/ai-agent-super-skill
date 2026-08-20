"""Tests for the Grok gateway: request shape, streaming, and error mapping.

The real OpenAI client is never used; a fake stands in so no network traffic
ever happens. SDK exception types are real so the mapping is honest.
"""

from types import SimpleNamespace

import httpx
import openai
import pytest

from grokbot.exceptions import (
    GrokKeyRejected,
    GrokNotConfigured,
    GrokThrottled,
    GrokUpstreamError,
)
from grokbot.gateway import GrokGateway
from grokbot.settings import Settings


def make_settings(**overrides) -> Settings:
    values = {"xai_api_key": "xai-test-key", "grok_model": "grok-test"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def sdk_error(cls, status_code: int):
    request = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return cls("boom", response=response, body=None)


class FakeCompletions:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class FakeClient:
    def __init__(self, result=None, error=None):
        self.completions = FakeCompletions(result=result, error=error)
        self.chat = SimpleNamespace(completions=self.completions)


def reply_response(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


def stream_chunk(delta_content):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=delta_content))]
    )


MESSAGES = [{"role": "user", "content": "hello"}]


def test_reply_returns_content_and_sends_model_and_messages():
    client = FakeClient(result=reply_response("hi, human"))
    gateway = GrokGateway(make_settings(), client=client)

    reply = gateway.reply(MESSAGES)

    assert reply == "hi, human"
    (call,) = client.completions.calls
    assert call["model"] == "grok-test"
    assert call["messages"] == MESSAGES
    assert "stream" not in call or call["stream"] is False


def test_stream_reply_yields_deltas_skipping_empty_ones():
    chunks = [
        stream_chunk("wire"),
        stream_chunk(None),
        SimpleNamespace(choices=[]),
        stream_chunk(" service"),
        stream_chunk(""),
    ]
    client = FakeClient(result=iter(chunks))
    gateway = GrokGateway(make_settings(), client=client)

    parts = list(gateway.stream_reply(MESSAGES))

    assert parts == ["wire", " service"]
    (call,) = client.completions.calls
    assert call["stream"] is True


def test_missing_api_key_raises_not_configured():
    gateway = GrokGateway(make_settings(xai_api_key=""))

    with pytest.raises(GrokNotConfigured):
        gateway.reply(MESSAGES)


def test_missing_api_key_raises_not_configured_for_stream():
    gateway = GrokGateway(make_settings(xai_api_key=""))

    with pytest.raises(GrokNotConfigured):
        list(gateway.stream_reply(MESSAGES))


def test_auth_error_maps_to_key_rejected():
    client = FakeClient(error=sdk_error(openai.AuthenticationError, 401))
    gateway = GrokGateway(make_settings(), client=client)

    with pytest.raises(GrokKeyRejected):
        gateway.reply(MESSAGES)


def test_rate_limit_maps_to_throttled():
    client = FakeClient(error=sdk_error(openai.RateLimitError, 429))
    gateway = GrokGateway(make_settings(), client=client)

    with pytest.raises(GrokThrottled):
        gateway.reply(MESSAGES)


def test_other_api_status_maps_to_upstream_error():
    client = FakeClient(error=sdk_error(openai.APIStatusError, 500))
    gateway = GrokGateway(make_settings(), client=client)

    with pytest.raises(GrokUpstreamError):
        gateway.reply(MESSAGES)


def test_connection_error_maps_to_upstream_error():
    request = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
    client = FakeClient(error=openai.APIConnectionError(request=request))
    gateway = GrokGateway(make_settings(), client=client)

    with pytest.raises(GrokUpstreamError):
        gateway.reply(MESSAGES)


def test_stream_errors_are_mapped_too():
    client = FakeClient(error=sdk_error(openai.RateLimitError, 429))
    gateway = GrokGateway(make_settings(), client=client)

    with pytest.raises(GrokThrottled):
        list(gateway.stream_reply(MESSAGES))


def test_settings_defaults():
    settings = Settings(_env_file=None, xai_api_key="k")

    assert settings.grok_model == "grok-4.6"
    assert settings.xai_base_url == "https://api.x.ai/v1"
    assert settings.grok_history_limit == 60


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "env-key")
    monkeypatch.setenv("GROK_MODEL", "grok-next")

    settings = Settings(_env_file=None)

    assert settings.xai_api_key == "env-key"
    assert settings.grok_model == "grok-next"
