import pytest
from fastapi.testclient import TestClient

from grokbot.api import create_app
from grokbot.store import SessionStore


class FakeGateway:
    """Stands in for GrokGateway in API tests. Never touches the network."""

    def __init__(
        self,
        reply_text: str = "canned reply",
        chunks: list[str] | None = None,
        error: Exception | None = None,
        configured: bool = True,
        model: str = "grok-test",
    ):
        self.reply_text = reply_text
        self.chunks = chunks if chunks is not None else ["canned ", "reply"]
        self.error = error
        self.configured = configured
        self.model = model
        self.calls: list[list[dict]] = []

    def reply(self, messages: list[dict]) -> str:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return self.reply_text

    def stream_reply(self, messages: list[dict]):
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        yield from self.chunks


@pytest.fixture()
def store() -> SessionStore:
    return SessionStore()


@pytest.fixture()
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture()
def client(store: SessionStore, gateway: FakeGateway) -> TestClient:
    return TestClient(create_app(store=store, gateway=gateway))


def client_for(gateway: FakeGateway, store: SessionStore | None = None) -> TestClient:
    return TestClient(create_app(store=store or SessionStore(), gateway=gateway))
