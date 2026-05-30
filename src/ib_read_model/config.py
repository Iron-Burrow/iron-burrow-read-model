from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IB_READ_MODEL_", env_file=".env", extra="ignore")

    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/ibdb")
    source_database_url: str | None = Field(default=None)
    price_indexer_base_url: str = Field(default="http://localhost:3001")
    model_version: str = Field(default="price_read_model_v1")
    default_assets: str = Field(default="")
    http_timeout_seconds: float = Field(default=10.0)
    refresh_interval_seconds: int = Field(default=300)


@lru_cache
def get_settings() -> Settings:
    return Settings()
