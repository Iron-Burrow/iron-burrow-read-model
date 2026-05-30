from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IB_READ_MODEL_", env_file=".env", extra="ignore")

    hot_database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5436/ibdb_hot",
        validation_alias=AliasChoices("IB_READ_MODEL_HOT_DATABASE_URL", "IB_READ_MODEL_DATABASE_URL"),
    )
    warm_database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5437/ibdb",
        validation_alias=AliasChoices("IB_READ_MODEL_WARM_DATABASE_URL", "IB_READ_MODEL_SOURCE_DATABASE_URL"),
    )
    price_indexer_base_url: str = Field(default="http://localhost:3001")
    model_version: str = Field(default="price_read_model_v1")
    default_assets: str = Field(default="")
    http_timeout_seconds: float = Field(default=10.0)
    refresh_interval_seconds: int = Field(default=300)

    @property
    def database_url(self) -> str:
        return self.hot_database_url

    @property
    def source_database_url(self) -> str:
        return self.warm_database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
