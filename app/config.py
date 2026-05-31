

"""
All the constants the project uses, kept in one place.

If a city changes, the API URL moves, or you want to poll faster,
edit this file. Poller, events, and tests all read from here so
nothing drifts out of sync.
"""

# The three cities we monitor. Coordinates come straight from the
# challenge spec, so we don't accidentally fetch the wrong location.
# Using a list (not a dict keyed by name) because the poller loops
# through them in order and that order shows up in the logs.
CITIES = [
    {"name": "Ottawa",    "latitude": 45.42, "longitude": -75.69},
    {"name": "Toronto",   "latitude": 43.70, "longitude": -79.42},
    {"name": "Vancouver", "latitude": 49.25, "longitude": -123.12},
]

# Open-Meteo's free forecast endpoint. No key, no auth.
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# The five fields the challenge asks for, comma-separated as Open-Meteo
# expects them in the query string.
CURRENT_FIELDS = "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,weather_code"

# Poll every 5 minutes. Open-Meteo only refreshes data hourly, so
# anything faster is just extra requests that get deduped anyway.
# Anything slower means new readings take longer to show up.
POLL_INTERVAL_SECONDS = 300