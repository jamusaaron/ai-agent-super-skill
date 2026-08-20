from __future__ import annotations


class GrokError(Exception):
    """Base error for Grok Bot."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GrokConfigError(GrokError):
    def __init__(self, message: str = "Grok Bot needs an XAI_API_KEY. Add it to `.env` — see README.") -> None:
        super().__init__(message, status_code=503)


class GrokAuthError(GrokError):
    def __init__(self, message: str = "xAI rejected the API key. Check XAI_API_KEY.") -> None:
        super().__init__(message, status_code=503)


class GrokRateLimitError(GrokError):
    def __init__(self, message: str = "xAI is rate-limiting this key. Wait a moment and try again.") -> None:
        super().__init__(message, status_code=429)


class GrokAPIError(GrokError):
    def __init__(self, message: str = "Grok didn't answer. The model or API returned an error.") -> None:
        super().__init__(message, status_code=502)
