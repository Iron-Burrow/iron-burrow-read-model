from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def source_texts() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): path.read_text(encoding="utf-8")
        for path in (ROOT / "src").rglob("*.py")
    }


def test_no_pandas_or_polars_dependency() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "pandas" not in pyproject
    assert "polars" not in pyproject


def test_repositories_only_write_to_read_model_schema() -> None:
    for path, text in source_texts().items():
        if "/repositories/" not in path:
            continue
        for match in re.finditer(
            r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|TRUNCATE)\s+([a-zA-Z0-9_.]+)",
            text,
            flags=re.IGNORECASE,
        ):
            target = match.group(1)
            if target.upper() == "SET":
                continue
            assert target.startswith("read_model."), f"{path} has non-read_model write: {match.group(0)}"


def test_price_source_uses_httpx_not_direct_price_indexer_sql() -> None:
    source = (ROOT / "src/ib_read_model/sources/price_indexer_ql.py").read_text(encoding="utf-8")
    assert "httpx" in source
    assert "price_indexer." not in source
    assert "price_ticks" not in source


def test_trend_repository_exposes_separate_history_and_latest_writes() -> None:
    source = (ROOT / "src/ib_read_model/repositories/price_trend_repo.py").read_text(encoding="utf-8")
    assert "def append_price_trend_history" in source
    assert "read_model.price_trend_history" in source
    assert "def upsert_price_trend_latest" in source
    assert "read_model.price_trend_latest" in source


def test_price_cli_uses_mother_api_asset_source() -> None:
    source = (ROOT / "src/ib_read_model/cli.py").read_text(encoding="utf-8")
    assert 'PRICE_ASSET_SOURCE = "mother_api.global_asset"' in source
    assert "source_tables_used=PRICE_SOURCE_TABLES" in source
    assert "--assets" not in source
