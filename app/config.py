"""
Central place for project constants.

If you ever need to add a city, change the poll interval, or update
the API URL, change it here. Poller, events, and tests all import
from this file so there's only ever one source of truth.
"""

# The three cities we monitor, with their coordinates.
# Stored as a list of dicts (not a dict-of-dicts) because the poller
# iterates over them and the order is meaningful for logs.
CITIES = [
    {"name": "Ottawa",    "latitude": 45.42, "longitude": -75.69},
    {"name": "Toronto",   "latitude": 43.70, "longitude": -79.42},
    {"name": "Vancouver", "latitude": 49.25, "longitude": -123.12},
]

# Open-Meteo's free forecast endpoint. No auth required.
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Which fields we ask Open-Meteo to include in the "current" payload.
# These are the five the challenge specifies.
CURRENT_FIELDS = "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,weather_code"

# How often the poller fetches new data, in seconds.
# Open-Meteo updates hourly, so polling faster than this just produces
# duplicates that get rejected by the UNIQUE constraint. 5 minutes is
# a good balance: catches new readings quickly without hammering the API.
POLL_INTERVAL_SECONDS = 300