from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from ib_read_model.config import get_settings


@contextmanager
def connect_hot() -> Iterator[Connection]:
    with psycopg.connect(get_settings().hot_database_url, row_factory=dict_row) as conn:
        yield conn


@contextmanager
def connect_warm() -> Iterator[Connection]:
    with psycopg.connect(get_settings().warm_database_url, row_factory=dict_row) as conn:
        yield conn


@contextmanager
def connect() -> Iterator[Connection]:
    with connect_hot() as conn:
        yield conn


@contextmanager
def connect_source() -> Iterator[Connection]:
    with connect_warm() as conn:
        yield conn
