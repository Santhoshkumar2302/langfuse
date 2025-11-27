import requests
import uuid
from datetime import datetime, timezone
import base64
import time

class LangfuseTracker:
    def __init__(self, public_key: str, secret_key: str, host: str):
        self.url = host.rstrip("/") + "/api/public/ingestion"
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json"
        }

    def _ts(self) -> str:
        # ISO 8601 / RFC‑3339 timestamp with 'Z' suffix
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _post_batch(self, events: list) -> requests.Response:
        payload = {"batch": events}
        resp = requests.post(self.url, json=payload, headers=self.headers)
        print("STATUS:", resp.status_code)
        print("RESPONSE:", resp.text)
        return resp

    def track_llm(self, prompt: str, model: str = "gpt-4", tokens_used: int = 0, cost_usd: float = 0.0):
        trace_id = str(uuid.uuid4())
        gen_id = str(uuid.uuid4())

        events = [
            {
                "type": "trace-create",
                "id": trace_id,
                "timestamp": self._ts(),
                "body": {
                    "id": trace_id,
                    "name": "llm-call"
                }
            },
            {
                "type": "generation-create",
                "id": gen_id,
                "timestamp": self._ts(),
                "body": {
                    "id": gen_id,
                    "traceId": trace_id,
                    "model": model,
                    "input": {"text": prompt},
                    "output": {"text": None},  # You can fill output later if you like
                    "usage": {
                        "prompt_tokens": tokens_used,
                        "completion_tokens": 0,
                        "total_tokens": tokens_used
                    },
                    "cost": {
                        "total": cost_usd,
                        "unit": "USD"
                    }
                }
            }
        ]

        return self._post_batch(events)

    def track_api(self, url: str, method: str = "GET", status_code: int = 200, duration_sec: float = 0.0):
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        events = [
            {
                "type": "trace-create",
                "id": trace_id,
                "timestamp": self._ts(),
                "body": {
                    "id": trace_id,
                    "name": "api-call"
                }
            },
            {
                "type": "span-create",
                "id": span_id,
                "timestamp": self._ts(),
                "body": {
                    "id": span_id,
                    "traceId": trace_id,
                    "name": f"HTTP {method}",
                    "startTime": self._ts(),
                    "endTime": self._ts(),
                    "metadata": {
                        "url": url,
                        "status_code": status_code,
                        "duration_sec": duration_sec
                    }
                }
            }
        ]

        return self._post_batch(events)


if __name__ == "__main__":
    tracker = LangfuseTracker(
        public_key="pk-lf-ffec1d13-a69d-43bb-bed9-4876fd4386cc",
        secret_key="sk-lf-bf3f930c-405c-4465-81b8-bcff06734944",
        host="https://us.cloud.langfuse.com"
    )

    # Example LLM call
    tracker.track_llm("Summarize this text.", tokens_used=75, cost_usd=0.003)

    # Example API call
    start = time.time()
    time.sleep(0.2)
    tracker.track_api(
        url="https://api.example.com/data",
        method="POST",
        status_code=201,
        duration_sec=time.time() - start
    )
