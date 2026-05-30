from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IB_READ_MODEL_", env_file=".env", extra="ignore")

    hot_database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5436/ibdb_hot",
        validation_alias=AliasChoices(
            "HOT_DATABASE_URL",
            "IB_READ_MODEL_HOT_DATABASE_URL",
            "IB_READ_MODEL_DATABASE_URL",
        ),
    )
    warm_database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5437/ibdb",
        validation_alias=AliasChoices(
            "WARM_DATABASE_URL",
            "IB_READ_MODEL_WARM_DATABASE_URL",
            "IB_READ_MODEL_SOURCE_DATABASE_URL",
        ),
    )
    price_indexer_ql_base_url: str = Field(
        default="http://iron-burrow-price-indexer:3010",
        validation_alias=AliasChoices(
            "PRICE_INDEXER_QL_BASE_URL",
            "IB_READ_MODEL_PRICE_INDEXER_QL_BASE_URL",
            "IB_READ_MODEL_PRICE_INDEXER_BASE_URL",
        ),
    )
    price_indexer_ql_bearer_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "PRICE_INDEXER_QL_BEARER_TOKEN",
            "IB_READ_MODEL_PRICE_INDEXER_QL_BEARER_TOKEN",
            "PRICE_QL_INTERNAL_TOKEN",
            "IB_READ_MODEL_PRICE_QL_INTERNAL_TOKEN",
        ),
    )
    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "IB_READ_MODEL_APP_ENV"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL", "IB_READ_MODEL_LOG_LEVEL"),
    )
    model_version: str = Field(default="price_read_model_v1")
    http_timeout_seconds: float = Field(default=10.0)
    run_interval_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices(
            "RUN_INTERVAL_SECONDS",
            "IB_READ_MODEL_RUN_INTERVAL_SECONDS",
            "IB_READ_MODEL_REFRESH_INTERVAL_SECONDS",
        ),
    )
    db_pool_min_size: int = Field(
        default=1,
        validation_alias=AliasChoices("DB_POOL_MIN_SIZE", "IB_READ_MODEL_DB_POOL_MIN_SIZE"),
    )
    db_pool_max_size: int = Field(
        default=10,
        validation_alias=AliasChoices("DB_POOL_MAX_SIZE", "IB_READ_MODEL_DB_POOL_MAX_SIZE"),
    )

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        """Ensure production environments have non-localhost database URLs."""
        if self.app_env.lower() == "production":
            if "localhost" in self.hot_database_url or "127.0.0.1" in self.hot_database_url:
                raise ValueError(
                    "Production environment requires non-localhost HOT_DATABASE_URL. "
                    "Set HOT_DATABASE_URL or IB_READ_MODEL_HOT_DATABASE_URL."
                )
            if "localhost" in self.warm_database_url or "127.0.0.1" in self.warm_database_url:
                raise ValueError(
                    "Production environment requires non-localhost WARM_DATABASE_URL. "
                    "Set WARM_DATABASE_URL or IB_READ_MODEL_WARM_DATABASE_URL."
                )
        return self

    def sanitized_summary(self) -> dict[str, str]:
        """Return a sanitized config summary safe for logging (no credentials)."""
        def sanitize_url(url: str) -> str:
            """Extract host and database name from URL, omitting credentials."""
            try:
                parsed = urlparse(url)
                db_name = parsed.path.lstrip("/").split("?")[0] if parsed.path else "unknown"
                return f"{parsed.hostname or 'unknown'}:{parsed.port or 'default'}/{db_name}"
            except Exception:
                return "invalid_url"

        return {
            "app_env": self.app_env,
            "log_level": self.log_level,
            "hot_database": sanitize_url(self.hot_database_url),
            "warm_database": sanitize_url(self.warm_database_url),
            "price_indexer_ql_url": self.price_indexer_ql_base_url,
            "bearer_token_configured": "yes" if self.price_indexer_ql_bearer_token else "no",
            "model_version": self.model_version,
            "http_timeout_seconds": str(self.http_timeout_seconds),
            "run_interval_seconds": str(self.run_interval_seconds),
        }

    @property
    def database_url(self) -> str:
        """Backward compatibility alias for hot_database_url."""
        return self.hot_database_url

    @property
    def source_database_url(self) -> str:
        """Backward compatibility alias for warm_database_url."""
        return self.warm_database_url

    @property
    def price_indexer_base_url(self) -> str:
        """Backward compatibility alias for price_indexer_ql_base_url."""
        return self.price_indexer_ql_base_url

    @property
    def price_ql_internal_token(self) -> str | None:
        """Backward compatibility alias for price_indexer_ql_bearer_token."""
        return self.price_indexer_ql_bearer_token

    @property
    def refresh_interval_seconds(self) -> int:
        """Backward compatibility alias for run_interval_seconds."""
        return self.run_interval_seconds


@lru_cache
def get_settings() -> Settings:
    return Settings()
