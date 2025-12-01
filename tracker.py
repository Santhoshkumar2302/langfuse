"""
tracker.py
- Sends events to Langfuse ingestion (POST JSON array)
- Stores events in PostgreSQL using PostgresDB
- Loads LANGFUSE + POSTGRES credentials from .env
"""

import os
import uuid
import time
import base64
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

from database import PostgresDB


# -------------------------------
# Load .env
# -------------------------------
load_dotenv("E:\Python\langfuse\API.env")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL")

POSTGRES_DSN = os.getenv("POSTGRES_DSN")


class LangfuseTracker:
    def __init__(self, public_key: str, secret_key: str, host: str, db: Optional[PostgresDB] = None):
        """
        host example:
            https://us.cloud.langfuse.com
        """
        self.url = host.rstrip("/") + "/api/public/ingestion"

        # Basic Auth Base64
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

        self.db = db

    # Timestamp in RFC3339 Zulu format
    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Post a batch of events to Langfuse ingestion API
    def _post_batch(self, events: List[Dict[str, Any]], timeout=5.0, retries=2):
        if not events:
            return None

        last_exc = None
        for attempt in range(retries + 1):
            try:
                resp = requests.post(
                    self.url,
                    json=events,
                    headers=self.headers,
                    timeout=timeout,
                )
                print("Langfuse STATUS:", resp.status_code)
                print("Langfuse RESPONSE:", resp.text)
                return resp
            except Exception as e:
                last_exc = e
                print(f"[Retry {attempt+1}] Failed posting to Langfuse:", e)
                time.sleep(0.2 * (attempt + 1))

        print("❌ All retries failed:", last_exc)
        return None

    # Insert into local Postgres
    def _persist(self, row: Dict[str, Any]):
        if self.db:
            try:
                self.db.insert_event(row)
            except Exception as e:
                print("DB Insert Error:", e)

    # Build trace-create & generation-create events
    def _make_generation_events(self, trace_id, gen_id, model, prompt, tokens_used, completion_tokens, cost_usd, output):
        now = self._ts()

        return [
            {
                "type": "trace-create",
                "id": trace_id,
                "timestamp": now,
                "body": {"id": trace_id, "name": "llm-call"},
            },
            {
                "type": "generation-create",
                "id": gen_id,
                "timestamp": now,
                "body": {
                    "id": gen_id,
                    "traceId": trace_id,
                    "model": model,
                    "input": {"text": prompt},
                    "output": {"text": output},
                    "usage": {
                        "prompt_tokens": tokens_used,
                        "completion_tokens": completion_tokens,
                        "total_tokens": tokens_used + completion_tokens,
                    },
                    "cost": {"total": cost_usd, "unit": "USD"},
                },
            },
        ]

    # MAIN LLM tracking method
    def track_llm(self, user_id: str, prompt: str, model="gpt-4", tokens_used=0,
                  completion_tokens=0, cost_usd=0.0, output=None):

        trace_id = str(uuid.uuid4())
        gen_id = str(uuid.uuid4())

        events = self._make_generation_events(
            trace_id, gen_id, model, prompt,
            tokens_used, completion_tokens,
            cost_usd, output
        )

        # Save to Postgres
        row = {
            "id": gen_id,
            "type": "llm-generation",
            "user_id": user_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc),
            "model": model,
            "prompt": prompt,
            "output": output,
            "tokens_used": tokens_used + completion_tokens,
            "cost_usd": cost_usd,
            "url": None,
            "method": None,
            "status_code": None,
            "duration_sec": None,
            "raw": {"events": events},
        }

        self._persist(row)
        return self._post_batch(events)

    # Build HTTP span events
    def _make_span_events(self, trace_id, span_id, method, url, status_code, duration_sec):
        now = self._ts()
        return [
            {
                "type": "trace-create",
                "id": trace_id,
                "timestamp": now,
                "body": {"id": trace_id, "name": "api-call"},
            },
            {
                "type": "span-create",
                "id": span_id,
                "timestamp": now,
                "body": {
                    "id": span_id,
                    "traceId": trace_id,
                    "name": f"HTTP {method}",
                    "startTime": now,
                    "endTime": now,
                    "metadata": {
                        "url": url,
                        "status_code": status_code,
                        "duration_sec": duration_sec,
                    },
                },
            },
        ]

    # MAIN API tracking
    def track_api(self, user_id: str, url: str, method="GET",
                  status_code=200, duration_sec: float = 0.0):

        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        events = self._make_span_events(
            trace_id, span_id, method, url, status_code, duration_sec
        )

        row = {
            "id": span_id,
            "type": "api-span",
            "user_id": user_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc),
            "model": None,
            "prompt": None,
            "output": None,
            "tokens_used": None,
            "cost_usd": None,
            "url": url,
            "method": method,
            "status_code": status_code,
            "duration_sec": duration_sec,
            "raw": {"events": events},
        }

        self._persist(row)
        return self._post_batch(events)


# -------------------------------
# Standalone test usage
# -------------------------------
if __name__ == "__main__":
    if not POSTGRES_DSN:
        raise RuntimeError("POSTGRES_DSN missing in .env")

    db = PostgresDB(POSTGRES_DSN)

    tracker = LangfuseTracker(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_BASE_URL,
        db=db,
    )

    tracker.track_llm(
        user_id="demo",
        prompt="Say hello!",
        tokens_used=10,
        completion_tokens=2,
        cost_usd=0.0004,
        output="Hello world!"
    )

    tracker.track_api(
        user_id="demo",
        url="https://api.example.com/test",
        method="GET",
        status_code=200,
        duration_sec=0.123
    )
