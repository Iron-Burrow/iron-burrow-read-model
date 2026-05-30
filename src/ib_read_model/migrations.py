from pathlib import Path

from psycopg import Connection


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run_migrations(conn: Connection) -> int:
    count = 0
    with conn.transaction():
        for path in migration_files():
            conn.execute(path.read_text(encoding="utf-8"))
            count += 1
    return count
