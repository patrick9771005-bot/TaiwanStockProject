# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false
import os
import sqlite3
from typing import Any, Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class HybridRow(dict[str, Any]):
    """Mapping row that supports both key access and integer index access."""

    def __init__(self, data: dict[str, Any], columns: Optional[list[str]] = None) -> None:
        super().__init__(data)
        self._columns = columns or list(data.keys())

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return super().__getitem__(self._columns[key])
        return super().__getitem__(key)


class CompatCursor:
    def __init__(self, inner_cursor: Any, is_postgres: bool) -> None:
        self._cur = inner_cursor
        self._is_postgres = is_postgres
        self._columns: list[str] = []

    def execute(self, query: str, params: Optional[Iterable[Any]] = None) -> "CompatCursor":
        sql = query
        if self._is_postgres:
            sql = _convert_sql_placeholders(sql)
        if params is None:
            self._cur.execute(sql)
        else:
            self._cur.execute(sql, tuple(params))

        self._columns = [col[0] for col in (self._cur.description or [])]
        return self

    def fetchone(self) -> Optional[HybridRow]:
        row = self._cur.fetchone()
        if row is None:
            return None
        return _to_hybrid_row(row, self._columns)

    def fetchall(self) -> list[HybridRow]:
        rows = self._cur.fetchall()
        return [_to_hybrid_row(r, self._columns) for r in rows]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cur, name)


class CompatConnection:
    def __init__(self, inner_conn: Any, is_postgres: bool) -> None:
        self._conn = inner_conn
        self._is_postgres = is_postgres

    def cursor(self) -> CompatCursor:
        return CompatCursor(self._conn.cursor(), self._is_postgres)

    def execute(self, query: str, params: Optional[Iterable[Any]] = None) -> CompatCursor:
        cur = self.cursor()
        return cur.execute(query, params)

    def commit(self) -> Any:
        return self._conn.commit()

    def rollback(self) -> Any:
        return self._conn.rollback()

    def close(self) -> Any:
        return self._conn.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def is_postgres_enabled() -> bool:
    db_url = os.environ.get("DATABASE_URL", "").strip()
    return bool(db_url.startswith("postgres://") or db_url.startswith("postgresql://"))


def get_connection(default_sqlite_path: str) -> CompatConnection:
    if is_postgres_enabled():
        try:
            import psycopg
            from psycopg.rows import dict_row
        except Exception as exc:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed") from exc

        db_url = os.environ["DATABASE_URL"]
        db_url = _normalize_postgres_url(db_url)
        conn = psycopg.connect(db_url, row_factory=dict_row)
        return CompatConnection(conn, is_postgres=True)

    db_dir = os.path.dirname(default_sqlite_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(default_sqlite_path)
    conn.row_factory = sqlite3.Row
    return CompatConnection(conn, is_postgres=False)


def _convert_sql_placeholders(sql: str) -> str:
    # Project SQL does not use literal '?' in strings; simple replacement is sufficient.
    return sql.replace("?", "%s")


def _to_hybrid_row(row: Any, columns: list[str]) -> HybridRow:
    if isinstance(row, HybridRow):
        return row

    if isinstance(row, dict):
        return HybridRow(row, columns)

    if isinstance(row, sqlite3.Row):
        data = {k: row[k] for k in row.keys()}
        return HybridRow(data, list(row.keys()))

    # tuple/list fallback
    data = {}
    if columns and len(columns) == len(row):
        for i, col in enumerate(columns):
            data[col] = row[i]
        return HybridRow(data, columns)

    for i, value in enumerate(row):
        key = str(i)
        data[key] = value
    return HybridRow(data)


def _normalize_postgres_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        if host.endswith('supabase.co'):
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if 'sslmode' not in query:
                query['sslmode'] = 'require'
                return urlunsplit((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    urlencode(query),
                    parsed.fragment
                ))
        return url
    except Exception:
        return url
