from pathlib import Path

from ib_read_model.config import Settings


ROOT = Path(__file__).resolve().parents[1]


def test_hot_warm_settings_have_explicit_defaults() -> None:
    settings = Settings()
    assert settings.hot_database_url.endswith("/ibdb_hot")
    assert settings.warm_database_url.endswith("/ibdb")
    assert settings.database_url == settings.hot_database_url
    assert settings.source_database_url == settings.warm_database_url


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


def test_compose_local_defines_two_databases() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "db_hot:" in compose
    assert "POSTGRES_DB: ibdb_hot" in compose
    assert "db_warm:" in compose
    assert "POSTGRES_DB: ibdb" in compose
    assert "IB_READ_MODEL_HOT_DATABASE_URL" in compose
    assert "IB_READ_MODEL_WARM_DATABASE_URL" in compose


def test_compose_prod_uses_external_env_databases() -> None:
    compose = (ROOT / "compose.prod.yaml").read_text(encoding="utf-8")
    assert "db_hot:" not in compose
    assert "db_warm:" not in compose
    assert ".env.production" in compose
