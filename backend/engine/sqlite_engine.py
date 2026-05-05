import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from backend.engine.base import QueryEngine, QueryEngineFactory


class SQLiteQueryEngine(QueryEngine):
    def __init__(self, db_path: str | None = None):
        from backend.config import settings
        self._db_path = db_path or settings.db_path
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, sql: str) -> pd.DataFrame:
        validated = self.validate_sql(sql)
        with self._get_conn() as conn:
            df = pd.read_sql_query(validated, conn)
        return df

    def get_tables(self) -> list[str]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        return [row[0] for row in rows]

    def get_schema(self, table_name: str) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [
            {
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'dflt_value': row[4],
                'pk': bool(row[5]),
            }
            for row in rows
        ]

    def validate_sql(self, sql: str) -> str:
        from backend.services.security import validate_sql
        return validate_sql(sql)

    def get_connection_info(self) -> dict[str, Any]:
        return {'type': 'sqlite', 'path': self._db_path}


QueryEngineFactory.register('sqlite', SQLiteQueryEngine)
