from __future__ import annotations

from collections.abc import Iterator

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from app.errors import GrokAPIError, GrokAuthError, GrokConfigError, GrokRateLimitError
from app.personality import GROK_SYSTEM_PROMPT
from app.sessions import Message


class GrokClient:
    def __init__(
        self,
        api_key: str,
        model: str = "grok-4.6",
        base_url: str = "https://api.x.ai/v1",
        openai_client: OpenAI | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._openai = openai_client

    @property
    def openai(self) -> OpenAI:
        if self._openai is None:
            self._openai = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._openai

    def complete(self, history: list[Message]) -> str:
        response = self._create(history, stream=False)
        try:
            text = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise GrokAPIError() from exc
        if not text:
            raise GrokAPIError()
        return text

    def stream(self, history: list[Message]) -> Iterator[str]:
        response = self._create(history, stream=True)
        for chunk in response:
            try:
                delta = chunk.choices[0].delta.content
            except (AttributeError, IndexError):
                continue
            if delta:
                yield delta

    def _create(self, history: list[Message], stream: bool):
        if not self.api_key.strip():
            raise GrokConfigError()
        messages = [{"role": "system", "content": GROK_SYSTEM_PROMPT}]
        messages.extend({"role": m.role, "content": m.content} for m in history)
        try:
            return self.openai.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
            )
        except RateLimitError as exc:
            raise GrokRateLimitError() from exc
        except AuthenticationError as exc:
            raise GrokAuthError() from exc
        except (APIStatusError, APIConnectionError) as exc:
            raise GrokAPIError() from exc
