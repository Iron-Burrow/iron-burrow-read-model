from pathlib import Path

import pytest
from pydantic import ValidationError

from ib_read_model.config import Settings


ROOT = Path(__file__).resolve().parents[1]


def test_hot_warm_settings_have_explicit_defaults() -> None:
    settings = Settings()
    assert settings.hot_database_url.endswith("/ibdb_hot")
    assert settings.warm_database_url.endswith("/ibdb")
    assert settings.price_indexer_ql_base_url == "http://iron-burrow-price-indexer:3010"
    assert settings.database_url == settings.hot_database_url
    assert settings.source_database_url == settings.warm_database_url


def test_default_assets_env_is_not_used() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "IB_READ_MODEL_DEFAULT_ASSETS" not in env_example
    assert not hasattr(Settings(), "default_assets")


def test_legacy_database_aliases_still_work(monkeypatch) -> None:
    monkeypatch.setenv("IB_READ_MODEL_DATABASE_URL", "postgresql://legacy-hot")
    monkeypatch.setenv("IB_READ_MODEL_SOURCE_DATABASE_URL", "postgresql://legacy-warm")
    settings = Settings()
    assert settings.hot_database_url == "postgresql://legacy-hot"
    assert settings.warm_database_url == "postgresql://legacy-warm"


def test_explicit_hot_warm_database_env_vars_work(monkeypatch) -> None:
    monkeypatch.setenv("IB_READ_MODEL_HOT_DATABASE_URL", "postgresql://neon-hot")
    monkeypatch.setenv("IB_READ_MODEL_WARM_DATABASE_URL", "postgresql://vps-warm")
    settings = Settings()
    assert settings.hot_database_url == "postgresql://neon-hot"
    assert settings.warm_database_url == "postgresql://vps-warm"


def test_unprefixed_database_env_vars_work(monkeypatch) -> None:
    """New unprefixed env vars should work (primary in production)."""
    monkeypatch.setenv("HOT_DATABASE_URL", "postgresql://neon-hot-unprefixed")
    monkeypatch.setenv("WARM_DATABASE_URL", "postgresql://vps-warm-unprefixed")
    settings = Settings()
    assert settings.hot_database_url == "postgresql://neon-hot-unprefixed"
    assert settings.warm_database_url == "postgresql://vps-warm-unprefixed"


def test_unprefixed_ql_config_works(monkeypatch) -> None:
    """New unprefixed QL env vars should work."""
    monkeypatch.setenv("PRICE_INDEXER_QL_BASE_URL", "http://ql.internal")
    monkeypatch.setenv("PRICE_INDEXER_QL_BEARER_TOKEN", "test-token")
    settings = Settings()
    assert settings.price_indexer_ql_base_url == "http://ql.internal"
    assert settings.price_indexer_ql_bearer_token == "test-token"


def test_production_env_requires_non_localhost_hot_url(monkeypatch) -> None:
    """Production environment must have non-localhost HOT_DATABASE_URL."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "HOT_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ibdb_hot"
    )
    monkeypatch.setenv("WARM_DATABASE_URL", "postgresql://real-host:5432/ibdb")

    with pytest.raises(ValidationError, match="non-localhost HOT_DATABASE_URL"):
        Settings()


def test_production_env_requires_non_localhost_warm_url(monkeypatch) -> None:
    """Production environment must have non-localhost WARM_DATABASE_URL."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("HOT_DATABASE_URL", "postgresql://real-host:5432/ibdb_hot")
    monkeypatch.setenv(
        "WARM_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/ibdb"
    )

    with pytest.raises(ValidationError, match="non-localhost WARM_DATABASE_URL"):
        Settings()


def test_production_env_accepts_real_database_urls(monkeypatch) -> None:
    """Production environment should accept real database URLs."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "HOT_DATABASE_URL",
        "postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/ibdb_hot?sslmode=require",
    )
    monkeypatch.setenv(
        "WARM_DATABASE_URL",
        "postgresql://user:pass@vps.example.com:5432/ibdb?sslmode=require",
    )

    settings = Settings()
    assert settings.app_env == "production"
    assert "neon.tech" in settings.hot_database_url
    assert "vps.example.com" in settings.warm_database_url


def test_neon_urls_preserve_query_params(monkeypatch) -> None:
    """Neon URLs with sslmode and other query params should be preserved."""
    url_with_params = "postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/ibdb_hot?sslmode=require&connect_timeout=10"
    monkeypatch.setenv("HOT_DATABASE_URL", url_with_params)
    settings = Settings()
    assert settings.hot_database_url == url_with_params
    assert "sslmode=require" in settings.hot_database_url
    assert "connect_timeout=10" in settings.hot_database_url


def test_sanitized_summary_removes_credentials(monkeypatch) -> None:
    """Sanitized config summary should not contain passwords or tokens."""
    monkeypatch.setenv(
        "HOT_DATABASE_URL",
        "postgresql://user:secret_password@neon.tech:5432/ibdb_hot?sslmode=require",
    )
    monkeypatch.setenv(
        "WARM_DATABASE_URL", "postgresql://admin:another_secret@vps.com:5432/ibdb"
    )
    monkeypatch.setenv("PRICE_INDEXER_QL_BEARER_TOKEN", "super-secret-token-12345")

    settings = Settings()
    summary = settings.sanitized_summary()

    # Should contain host/db info
    assert "neon.tech" in summary["hot_database"]
    assert "ibdb_hot" in summary["hot_database"]
    assert "vps.com" in summary["warm_database"]
    assert "ibdb" in summary["warm_database"]

    # Should NOT contain passwords or tokens
    assert "secret_password" not in str(summary)
    assert "another_secret" not in str(summary)
    assert "super-secret-token" not in str(summary)
    assert "user" not in str(summary)
    assert "admin" not in str(summary)

    # Should indicate bearer token is configured without showing value
    assert summary["bearer_token_configured"] == "yes"


def test_price_ql_internal_token_aliases_work(monkeypatch) -> None:
    monkeypatch.setenv("PRICE_QL_INTERNAL_TOKEN", "shared-token")
    settings = Settings()
    assert settings.price_ql_internal_token == "shared-token"
    monkeypatch.delenv("PRICE_QL_INTERNAL_TOKEN")
    monkeypatch.setenv("IB_READ_MODEL_PRICE_QL_INTERNAL_TOKEN", "prefixed-token")
    settings = Settings()
    assert settings.price_ql_internal_token == "prefixed-token"


def test_backward_compatible_property_aliases(monkeypatch) -> None:
    """Old property names should still work for backward compatibility."""
    monkeypatch.setenv("HOT_DATABASE_URL", "postgresql://hot-db")
    monkeypatch.setenv("PRICE_INDEXER_QL_BASE_URL", "http://ql-url")
    monkeypatch.setenv("RUN_INTERVAL_SECONDS", "600")

    settings = Settings()

    # Old property names should map to new values
    assert settings.database_url == "postgresql://hot-db"
    assert settings.price_indexer_base_url == "http://ql-url"
    assert settings.refresh_interval_seconds == 600


def test_compose_local_defines_two_databases() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "db_hot:" in compose
    assert "POSTGRES_DB: ibdb_hot" in compose
    assert "db_warm:" in compose
    assert "POSTGRES_DB: ibdb" in compose
    assert "IB_READ_MODEL_HOT_DATABASE_URL" in compose
    assert "IB_READ_MODEL_WARM_DATABASE_URL" in compose
    assert "http://iron-burrow-price-indexer:3010" in compose
    assert "PRICE_QL_INTERNAL_TOKEN" in compose


def test_compose_prod_structure() -> None:
    """Production compose should use external network and no local DBs."""
    compose = (ROOT / "compose.prod.yaml").read_text(encoding="utf-8")

    # No local database services
    assert "db_hot:" not in compose
    assert "db_warm:" not in compose
    assert "POSTGRES_DB:" not in compose

    # Uses external iron-burrow-net
    assert "iron-burrow-net:" in compose
    assert "external: true" in compose

    # Service is named iron-burrow-read-model
    assert "iron-burrow-read-model:" in compose

    # Uses unprefixed env var names
    assert "HOT_DATABASE_URL" in compose
    assert "WARM_DATABASE_URL" in compose
    assert "PRICE_INDEXER_QL_BASE_URL" in compose
    assert "PRICE_INDEXER_QL_BEARER_TOKEN" in compose

    # Has restart policy
    assert "restart: unless-stopped" in compose

    # Has healthcheck
    assert "healthcheck:" in compose
    assert "ib-read-model" in compose
    assert "healthcheck" in compose

    # Uses run-worker command
    assert "run-worker" in compose
