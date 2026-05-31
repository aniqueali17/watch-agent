"""
FastAPI app: three endpoints (/health, /readings, /events) plus the
startup hook that initializes the database and launches the poller
in a background thread.
"""

import logging
import threading
from typing import Optional

from fastapi import FastAPI, Query

from app import storage, poller


# Basic logging setup so logger.info(...) calls from poller and elsewhere
# actually show up. Done once at the app level rather than per-module.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(title="WatchAgent", description="Weather monitor and event API")


@app.on_event("startup")
def on_startup():
    """
    Runs once when uvicorn boots the app.

    Creates tables (safe to call repeatedly) and starts the poller
    in a daemon thread so it runs alongside the API without blocking
    requests. Daemon=True means the thread dies when the main process
    exits, which is what we want — no orphan loops on shutdown.
    """
    storage.init_db()

    poller_thread = threading.Thread(target=poller.run_forever, daemon=True)
    poller_thread.start()
    logger.info("startup complete, poller thread running")

@app.get("/")
def root():
    """
    Friendly landing page. Not part of the spec — just here so
    visitors hitting the root URL aren't greeted with a 404.
    """
    return {
        "service": "WatchAgent",
        "endpoints": ["/health", "/readings", "/events", "/docs"],
    }


@app.get("/health")
def health():
    """
    Liveness probe. Also reports how much data the system has collected,
    which is handy for quickly seeing if the poller is doing its job.
    """
    return {
        "status": "ok",
        "readings_stored": storage.count_readings(),
        "events_stored": storage.count_events(),
    }


@app.get("/readings")
def readings(
    city: Optional[str] = Query(default=None, description="Filter by city name"),
    limit: int = Query(default=50, ge=1, le=1000, description="Max rows to return"),
):
    """
    Return stored readings, most recent first. Both filters are optional.
    """
    return {"readings": storage.get_readings(city=city, limit=limit)}


@app.get("/events")
def events_endpoint(
    city: Optional[str] = Query(default=None, description="Filter by city name"),
    limit: int = Query(default=50, ge=1, le=1000, description="Max rows to return"),
):
    """
    Return stored events, most recent first. Both filters are optional.
    """
    return {"events": storage.get_events(city=city, limit=limit)}