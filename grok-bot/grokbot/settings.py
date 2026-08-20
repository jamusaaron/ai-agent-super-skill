"""Environment-backed configuration.

Values come from environment variables (or a local `.env` file):
  XAI_API_KEY        xAI API key — get one at https://console.x.ai
  GROK_MODEL         chat model id (default: grok-4.6)
  XAI_BASE_URL       OpenAI-compatible endpoint (default: https://api.x.ai/v1)
  GROK_HISTORY_LIMIT max stored messages per session (default: 60)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    xai_api_key: str = ""
    grok_model: str = "grok-4.6"
    xai_base_url: str = "https://api.x.ai/v1"
    grok_history_limit: int = 60
