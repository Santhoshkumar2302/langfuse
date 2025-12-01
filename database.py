"""
database.py
PostgreSQL helper with .env DSN loading
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from typing import Optional, List, Dict

# Load .env
load_dotenv("E:\Python\langfuse\API.env")

POSTGRES_DSN = os.getenv("POSTGRES_DSN")


class PostgresDB:
    def __init__(self, dsn: Optional[str] = None, connect_timeout: int = 5):
        self.dsn = dsn or POSTGRES_DSN
        if not self.dsn:
            raise RuntimeError("POSTGRES_DSN missing in .env")

        self.conn = psycopg2.connect(self.dsn, connect_timeout=connect_timeout)
        self.conn.autocommit = True
        self._create_tables()

    def _create_tables(self):
        query = """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            type TEXT,
            user_id TEXT,
            trace_id TEXT,
            timestamp TIMESTAMPTZ,
            model TEXT,
            prompt TEXT,
            output TEXT,
            tokens_used DOUBLE PRECISION,
            cost_usd DOUBLE PRECISION,
            url TEXT,
            method TEXT,
            status_code INTEGER,
            duration_sec DOUBLE PRECISION,
            raw JSONB
        );
        CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
        CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp);
        """
        with self.conn.cursor() as cur:
            cur.execute(query)

    def insert_event(self, row: Dict):
        query = """
        INSERT INTO events (
            id, type, user_id, trace_id, timestamp, model, prompt, output,
            tokens_used, cost_usd, url, method, status_code, duration_sec, raw
        ) VALUES (
            %(id)s, %(type)s, %(user_id)s, %(trace_id)s, %(timestamp)s,
            %(model)s, %(prompt)s, %(output)s, %(tokens_used)s, %(cost_usd)s,
            %(url)s, %(method)s, %(status_code)s, %(duration_sec)s, %(raw)s
        )
        ON CONFLICT (id) DO NOTHING;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, row)

    def fetch_events(self, user: Optional[str], last_n_days: int, limit: int) -> List[Dict]:
        where = []
        params = []

        if user:
            where.append("user_id = %s")
            params.append(user)

        if last_n_days:
            where.append("timestamp >= NOW() - INTERVAL %s")
            params.append(f"{last_n_days} days")

        where_clause = "WHERE " + " AND ".join(where) if where else ""

        query = f"""
            SELECT *
            FROM events
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s
        """
        params.append(limit)

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, tuple(params))
            return cur.fetchall()
