from dataclasses import dataclass

from psycopg import Connection


@dataclass(frozen=True)
class ActiveGlobalAsset:
    slug: str
    symbol: str | None
    name: str | None


def list_active_assets(conn: Connection) -> list[ActiveGlobalAsset]:
    rows = conn.execute(
        """
        SELECT slug, symbol, name
        FROM mother_api.global_asset
        WHERE status = 'active'
        ORDER BY sort_order ASC, lower(symbol) ASC
        """
    ).fetchall()
    return [
        ActiveGlobalAsset(
            slug=str(row["slug"]).strip().lower(),
            symbol=row["symbol"],
            name=row["name"],
        )
        for row in rows
        if str(row["slug"]).strip()
    ]
