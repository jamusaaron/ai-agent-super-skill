"""Thin wrapper around the OpenAI-compatible xAI endpoint.

Owns two things: building the client from settings, and translating SDK
exceptions into the typed errors in `grokbot.exceptions`. Nothing here knows
about HTTP routes or sessions.
"""

from __future__ import annotations

from collections.abc import Iterator

import openai

from .exceptions import (
    GrokKeyRejected,
    GrokNotConfigured,
    GrokThrottled,
    GrokUpstreamError,
)
from .settings import Settings


def _map_sdk_error(exc: Exception) -> Exception:
    if isinstance(exc, openai.AuthenticationError):
        return GrokKeyRejected(str(exc))
    if isinstance(exc, openai.RateLimitError):
        return GrokThrottled(str(exc))
    return GrokUpstreamError(str(exc))


class GrokGateway:
    def __init__(self, settings: Settings, client: openai.OpenAI | None = None) -> None:
        self._settings = settings
        self._client = client

    @property
    def model(self) -> str:
        return self._settings.grok_model

    @property
    def configured(self) -> bool:
        return self._client is not None or bool(self._settings.xai_api_key)

    def _require_client(self) -> openai.OpenAI:
        if self._client is None:
            if not self._settings.xai_api_key:
                raise GrokNotConfigured("XAI_API_KEY is not set")
            self._client = openai.OpenAI(
                api_key=self._settings.xai_api_key,
                base_url=self._settings.xai_base_url,
            )
        return self._client

    def reply(self, messages: list[dict]) -> str:
        client = self._require_client()
        try:
            response = client.chat.completions.create(
                model=self._settings.grok_model, messages=messages
            )
        except openai.OpenAIError as exc:
            raise _map_sdk_error(exc) from exc
        return response.choices[0].message.content or ""

    def stream_reply(self, messages: list[dict]) -> Iterator[str]:
        client = self._require_client()
        try:
            stream = client.chat.completions.create(
                model=self._settings.grok_model, messages=messages, stream=True
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except openai.OpenAIError as exc:
            raise _map_sdk_error(exc) from exc
