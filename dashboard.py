"""
dashboard.py
FastAPI server powering the realtime Langfuse-like dashboard
"""

import os
import json
import asyncio
import httpx
import base64
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from auth import get_current_user
from fastapi import Depends


from database import PostgresDB

# Load .env
load_dotenv("E:\Python\langfuse\API.env")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL")
app = FastAPI()

# Serve static/
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database
db = PostgresDB()

# Allow frontend fetch()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)


# ---------------------------
# HTML Dashboard Page
# ---------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------
# API: Fetch all events
# ---------------------------
@app.get("/api/events")
async def api_events(user: str = "", last_n_days: int = 30, limit: int = 1000):
    rows = db.fetch_events(
        user=user if user.strip() else None,
        last_n_days=last_n_days,
        limit=limit,
    )
    return rows


# ---------------------------
# SSE STREAM (Realtime events)
# ---------------------------
@app.get("/events/stream")
async def events_stream(request: Request):

    async def stream():
        # Langfuse SSE endpoint
        url = LANGFUSE_BASE_URL.rstrip("/") + "/api/public/events-stream"

        # Basic auth header
        auth = base64.b64encode(
            f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth}",
            "Accept": "text/event-stream",
        }

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=headers) as r:
                async for line in r.aiter_lines():

                    # Client disconnected
                    if await request.is_disconnected():
                        print("Client disconnected from SSE")
                        break

                    # SSE empty line = event boundary
                    if line.startswith("data:"):
                        payload = line.replace("data:", "").strip()

                        # Forward raw event to frontend
                        yield f"data: {payload}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
