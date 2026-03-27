"""
Shared test configuration.

Fixes PostgreSQL ↔ SQLite incompatibilities so that in-memory SQLite tests
work with models designed for PostgreSQL.
"""
from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(type_, compiler, **kw):
    """
    Render BigInteger as INTEGER in SQLite.

    PostgreSQL models use BigInteger + Identity() for auto-incrementing PKs.
    In SQLite, auto-increment only works when the column is declared as exactly
    ``INTEGER PRIMARY KEY`` — not ``BIGINT PRIMARY KEY``. This hook makes
    BigInteger compile to INTEGER for the SQLite dialect, fixing that.
    """
    return "INTEGER"
