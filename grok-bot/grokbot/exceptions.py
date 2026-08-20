"""Typed errors raised by the Grok gateway.

The API layer maps each of these to a specific HTTP status and a safe,
user-facing message. Nothing from the upstream response body is exposed.
"""


class GrokError(Exception):
    """Base class for all Grok gateway errors."""


class GrokNotConfigured(GrokError):
    """No XAI_API_KEY is configured."""


class GrokKeyRejected(GrokError):
    """xAI rejected the configured API key (HTTP 401)."""


class GrokThrottled(GrokError):
    """xAI is rate-limiting this key (HTTP 429)."""


class GrokUpstreamError(GrokError):
    """Any other xAI API or network failure."""
