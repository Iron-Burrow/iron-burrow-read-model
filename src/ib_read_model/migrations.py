from pathlib import Path

from psycopg import Connection


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def migration_files(target: str) -> list[Path]:
    if target not in {"hot", "warm"}:
        raise ValueError("Migration target must be 'hot' or 'warm'")
    return sorted((MIGRATIONS_DIR / target).glob("*.sql"))


def run_migrations(conn: Connection, *, target: str) -> int:
    count = 0
    with conn.transaction():
        for path in migration_files(target):
            conn.execute(path.read_text(encoding="utf-8"))
            count += 1
    return count
