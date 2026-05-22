from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder values often copied from .env.example or Render UI
_INVALID_KEY_MARKERS = (
    "your_key",
    "your_openai_api_key",
    "your-api-key",
    "changeme",
    "replace_me",
    "xxx",
    "placeholder",
)


def is_valid_openai_api_key(key: str | None) -> bool:
    k = (key or "").strip()
    if not k or len(k) < 20:
        return False
    lower = k.lower()
    if any(marker in lower for marker in _INVALID_KEY_MARKERS):
        return False
    return k.startswith("sk-")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite+aiosqlite:///./data/appointments.db"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    mock_ai: bool = False
    session_ttl_seconds: int = 3600
    persistent_memory_ttl_seconds: int = 86400 * 30

    @property
    def use_mock(self) -> bool:
        if self.mock_ai:
            return True
        return not is_valid_openai_api_key(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
