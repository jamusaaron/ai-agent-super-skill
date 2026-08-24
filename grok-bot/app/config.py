from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    xai_api_key: str = ""
    grok_model: str = "grok-4.6"
    xai_base_url: str = "https://api.x.ai/v1"
    grokbot_db: str = ""
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def grok_configured(self) -> bool:
        return bool(self.xai_api_key.strip())
