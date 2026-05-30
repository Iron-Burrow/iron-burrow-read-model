from ib_read_model.sources.mother_api_db import ActiveGlobalAsset, list_active_assets


class FakeResult:
    def __init__(self, rows: list[dict[str, str | None]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, str | None]]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[dict[str, str | None]]) -> None:
        self.rows = rows
        self.sql: str | None = None

    def execute(self, sql: str) -> FakeResult:
        self.sql = sql
        return FakeResult(self.rows)


def test_list_active_assets_reads_mother_api_global_asset() -> None:
    conn = FakeConnection(
        [
            {"slug": " Ethereum ", "symbol": "ETH", "name": "Ethereum"},
            {"slug": "bitcoin", "symbol": "BTC", "name": "Bitcoin"},
            {"slug": " ", "symbol": "BAD", "name": "Blank"},
        ]
    )

    assets = list_active_assets(conn)  # type: ignore[arg-type]

    assert assets == [
        ActiveGlobalAsset(slug="ethereum", symbol="ETH", name="Ethereum"),
        ActiveGlobalAsset(slug="bitcoin", symbol="BTC", name="Bitcoin"),
    ]
    assert conn.sql is not None
    assert "FROM mother_api.global_asset" in conn.sql
    assert "WHERE status = 'active'" in conn.sql
    assert "ORDER BY sort_order ASC, lower(symbol) ASC" in conn.sql
