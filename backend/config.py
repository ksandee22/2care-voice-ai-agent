from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
        return self.mock_ai or not self.openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
