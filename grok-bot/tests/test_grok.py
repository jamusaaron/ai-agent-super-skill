from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

from app.errors import GrokAPIError, GrokAuthError, GrokConfigError, GrokRateLimitError
from app.grok import GrokClient
from app.personality import GROK_SYSTEM_PROMPT
from app.sessions import Message


def _client(api_key: str = "xai-test", openai_client=None) -> GrokClient:
    return GrokClient(api_key=api_key, model="grok-4.6", openai_client=openai_client)


def _completion(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


def test_missing_api_key_raises_config_error():
    client = _client(api_key="")
    with pytest.raises(GrokConfigError):
        client.complete([Message(role="user", content="hi")])


def test_complete_sends_system_prompt_then_history():
    openai_client = MagicMock()
    openai_client.chat.completions.create.return_value = _completion("hello from grok")
    client = _client(openai_client=openai_client)

    reply = client.complete(
        [
            Message(role="user", content="ping"),
            Message(role="assistant", content="pong"),
            Message(role="user", content="again"),
        ]
    )

    assert reply == "hello from grok"
    kwargs = openai_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "grok-4.6"
    assert kwargs["stream"] is False
    messages = kwargs["messages"]
    assert messages[0] == {"role": "system", "content": GROK_SYSTEM_PROMPT}
    assert messages[1:] == [
        {"role": "user", "content": "ping"},
        {"role": "assistant", "content": "pong"},
        {"role": "user", "content": "again"},
    ]


def test_rate_limit_maps_to_typed_error():
    openai_client = MagicMock()
    openai_client.chat.completions.create.side_effect = RateLimitError(
        "slow down",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )
    client = _client(openai_client=openai_client)
    with pytest.raises(GrokRateLimitError):
        client.complete([Message(role="user", content="hi")])


def test_auth_error_maps_to_typed_error():
    openai_client = MagicMock()
    openai_client.chat.completions.create.side_effect = AuthenticationError(
        "nope",
        response=MagicMock(status_code=401, headers={}),
        body=None,
    )
    client = _client(openai_client=openai_client)
    with pytest.raises(GrokAuthError):
        client.complete([Message(role="user", content="hi")])


def test_generic_api_status_maps_to_api_error():
    openai_client = MagicMock()
    response = MagicMock(status_code=500, headers={}, request=MagicMock())
    openai_client.chat.completions.create.side_effect = APIStatusError(
        "boom",
        response=response,
        body=None,
    )
    client = _client(openai_client=openai_client)
    with pytest.raises(GrokAPIError):
        client.complete([Message(role="user", content="hi")])


def test_connection_error_maps_to_api_error():
    openai_client = MagicMock()
    openai_client.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())
    client = _client(openai_client=openai_client)
    with pytest.raises(GrokAPIError):
        client.complete([Message(role="user", content="hi")])


def test_empty_model_content_becomes_api_error():
    openai_client = MagicMock()
    openai_client.chat.completions.create.return_value = _completion(None)
    client = _client(openai_client=openai_client)
    with pytest.raises(GrokAPIError):
        client.complete([Message(role="user", content="hi")])


def test_stream_yields_delta_tokens_then_full_text():
    openai_client = MagicMock()
    chunks = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hel"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="lo"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
    ]
    openai_client.chat.completions.create.return_value = iter(chunks)
    client = _client(openai_client=openai_client)

    tokens = list(client.stream([Message(role="user", content="hi")]))
    assert tokens == ["Hel", "lo"]
    kwargs = openai_client.chat.completions.create.call_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["messages"][0]["role"] == "system"
