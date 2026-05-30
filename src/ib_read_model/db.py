from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from ib_read_model.config import get_settings


@contextmanager
def connect() -> Iterator[Connection]:
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        yield conn


@contextmanager
def connect_source() -> Iterator[Connection]:
    settings = get_settings()
    with psycopg.connect(settings.source_database_url or settings.database_url, row_factory=dict_row) as conn:
        yield conn
