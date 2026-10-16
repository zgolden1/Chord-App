"""Tiny database layer: SQLite for development and tests, PostgreSQL in production.
Queries use '?' placeholders everywhere; they are converted to '%s' for PostgreSQL."""
import os, sqlite3, threading
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


class DB:
    def __init__(self, url=None):
        self.url = url or os.environ.get("DATABASE_URL", "sqlite:///chordflow.db")
        self.pg = self.url.startswith("postgres")
        self.lock = threading.RLock()
        if self.pg:
            import psycopg                                  # pip install "psycopg[binary]"
            self.conn = psycopg.connect(self.url, autocommit=True, row_factory=psycopg.rows.dict_row, prepare_threshold=None)
        else:
            path = self.url.replace("sqlite:///", "", 1)
            self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self):
        sql = SCHEMA.read_text()
        if self.pg:                                         # SERIAL ids on PostgreSQL
            sql = sql.replace("id            INTEGER PRIMARY KEY", "id            SERIAL PRIMARY KEY")
        with self.lock:
            if self.pg:
                self.conn.execute(sql)
            else:
                self.conn.executescript(sql)

    def _q(self, sql):
        return sql.replace("?", "%s") if self.pg else sql

    def all(self, sql, params=()):
        with self.lock:
            cur = self.conn.execute(self._q(sql), params)
            return [dict(r) for r in cur.fetchall()]

    def one(self, sql, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def run(self, sql, params=()):
        """Execute a write. Returns the new row id for INSERTs when available."""
        with self.lock:
            low = sql.strip().lower()
            if self.pg and low.startswith("insert") and "returning" not in low and any(
                    low.startswith("insert into " + t) for t in ("analyses", "suggestions", "jobs", "eval_runs")):
                cur = self.conn.execute(self._q(sql) + " RETURNING id", params)
                r = cur.fetchone()
                return r["id"] if r else None
            cur = self.conn.execute(self._q(sql), params)
            return getattr(cur, "lastrowid", None)

    def tx(self):
        return _Tx(self)


class _Tx:
    """with db.tx(): ... runs several statements atomically."""
    def __init__(self, db): self.db = db
    def __enter__(self):
        self.db.lock.acquire()
        self.db.conn.execute("BEGIN")
    def __exit__(self, et, ev, tb):
        self.db.conn.execute("ROLLBACK" if et else "COMMIT")
        self.db.lock.release()
