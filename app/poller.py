"""
Polls Open-Meteo for current weather across the three cities and
saves new readings to storage. Runs in a loop in the background.
"""

import logging
import time
import httpx

from app import storage
from app.config import (
    CITIES,
    OPEN_METEO_URL,
    CURRENT_FIELDS,
    POLL_INTERVAL_SECONDS,
)
from app import events

logger = logging.getLogger(__name__)


def fetch_city(city):
    """
    Call Open-Meteo for one city and return the parsed JSON.

    Returns None on failure (network error, bad status code) so the
    caller can keep going with the other cities instead of crashing
    the whole poll cycle on one bad request.
    """
    params = {
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "current": CURRENT_FIELDS,
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    }

    try:
        # 10 second timeout so a slow API doesn't stall the whole loop.
        response = httpx.get(OPEN_METEO_URL, params=params, timeout=10.0)
        response.raise_for_status()  # raise 4xx or 5xx status code as an exception
        return response.json()
    except httpx.HTTPError as exc:
        # Log and move on. One failed city shouldn't kill the poller.
        logger.warning("fetch failed for %s: %s", city["name"], exc)
        return None


def poll_once():
    """
    Run one polling cycle: fetch all three cities, store any new readings.
    """
    for city in CITIES:
        data = fetch_city(city)
        if data is None:
            continue  # already logged inside fetch_city

        # Use .get() rather than data["current"] so an unexpected response
        # shape (200 OK but missing field) doesn't raise, we check below
        # and log instead.
        current = data.get("current")
        if current is None:
            logger.warning("no 'current' field in response for %s", city["name"])
            continue

        # Pass each field by name. If Open-Meteo ever adds or renames a
        # field, this fails here instead of silently storing junk.
        stored = storage.insert_reading(
            city=city["name"],
            timestamp=current["time"],
            temperature_2m=current["temperature_2m"],
            apparent_temperature=current["apparent_temperature"],
            precipitation=current["precipitation"],
            wind_speed_10m=current["wind_speed_10m"],
            weather_code=current["weather_code"],
        )

        if stored:
            logger.info("stored reading: %s @ %s", city["name"], current["time"])
            # Reading is new — run detectors. We do this here (rather
            # than as a separate pass) because storage.insert_reading
            # already told us this reading is fresh, so no extra DB
            # check is needed to avoid duplicate events.
            #
            # We build a dict that matches what storage.get_readings
            # would return for this row, so events.py can treat it the
            # same as anything it fetches from history.
            reading_dict = {
                "city": city["name"],
                "timestamp": current["time"],
                "temperature_2m": current["temperature_2m"],
                "apparent_temperature": current["apparent_temperature"],
                "precipitation": current["precipitation"],
                "wind_speed_10m": current["wind_speed_10m"],
                "weather_code": current["weather_code"],
            }
            events.detect_and_store(reading_dict)
        else:
            logger.debug("duplicate skipped: %s @ %s", city["name"], current["time"])


def run_forever():
    """
    Poll on a schedule until the process is stopped. The API server
    runs this in a background thread on startup.
    """
    logger.info("poller starting, interval=%ss", POLL_INTERVAL_SECONDS)
    while True:
        poll_once()
        time.sleep(POLL_INTERVAL_SECONDS)