"""
Event detection logic. Three detectors run on every newly stored
reading: temperature swing, heavy precipitation, and severe weather
code. Each writes to the events table via storage.insert_event.
"""

from datetime import datetime, timedelta

from app import storage

# WMO weather codes we treat as severe. Pulled from Open-Meteo's
# documented code table. We deliberately skip light rain, drizzle,
# light snow, etc., because firing on those would be constant noise
# in places like Vancouver in winter.
SEVERE_WEATHER_CODES = {
    65,  # heavy rain
    75,  # heavy snowfall
    82,  # violent rain showers
    86,  # heavy snow showers
    95,  # thunderstorm
    96,  # thunderstorm with slight hail
    99,  # thunderstorm with heavy hail
}

# How far back the "previous reading" can be and still count as
# adjacent. Open-Meteo updates hourly, so a normal gap is ~60 min;
# 90 gives us slack for a missed poll. Beyond that, the previous
# reading is too old to call this a rate-of-change.
TEMP_SWING_WINDOW = timedelta(minutes=90)

# Minimum absolute temperature change (in °C) to count as a swing.
TEMP_SWING_THRESHOLD = 5.0

# Minimum precipitation (mm in the past hour) to count as heavy rain.
# Sits at the boundary of the WMO "heavy rain" category.
PRECIPITATION_THRESHOLD = 7.0


def check_temperature_swing(reading):
    """
    Fire if temperature changed by more than TEMP_SWING_THRESHOLD
    compared to this city's previous reading, and that previous
    reading is recent enough to call this a rate-of-change.

    Returns an event dict if it fires, or None if it doesn't.
    """
    # Pull this city's recent readings, newest first. We ask for 2
    # because we want the current one (already stored) and the one
    # just before it. Asking for more would be wasted work.
    recent = storage.get_readings(city=reading["city"], limit=2)

    # Need at least two readings to compare. First reading for a
    # city has nothing to look back at, so we just don't fire.
    if len(recent) < 2:
        return None

    # recent[0] is the one we just stored (most recent). recent[1]
    # is the previous one.
    current = recent[0]
    previous = recent[1]

    # Reject if the previous reading is too old. A 5°C drift over
    # six hours is just normal daily warming/cooling, not a weather
    # event. We only care about sharp changes within ~1 hour.
    current_time = datetime.fromisoformat(current["timestamp"])
    previous_time = datetime.fromisoformat(previous["timestamp"])
    if current_time - previous_time > TEMP_SWING_WINDOW:
        return None

    change = current["temperature_2m"] - previous["temperature_2m"]
    if abs(change) < TEMP_SWING_THRESHOLD:
        return None

    direction = "rose" if change > 0 else "dropped"
    reason = (
        f"Temperature {direction} {abs(change):.1f}°C since previous reading "
        f"(was {previous['temperature_2m']}°C, now {current['temperature_2m']}°C)"
    )

    return {
        "city": current["city"],
        "timestamp": current["timestamp"],
        "event_type": "temperature_swing",
        "reason": reason,
    }


def check_heavy_precipitation(reading):
    """
    Fire if precipitation in the past hour exceeds the threshold.

    Single-reading detector — no history needed. Heavy rain is heavy
    rain regardless of what came before it.
    """
    mm = reading.get("precipitation")

    # Open-Meteo sometimes reports null when there's been no rain.
    # Treat None as zero rather than crashing.
    if mm is None or mm < PRECIPITATION_THRESHOLD:
        return None

    return {
        "city": reading["city"],
        "timestamp": reading["timestamp"],
        "event_type": "heavy_precipitation",
        "reason": f"{mm} mm of precipitation in the past hour",
    }


def check_severe_weather_code(reading):
    """
    Fire if the WMO weather code is in our severe set.
    """
    code = reading.get("weather_code")
    if code not in SEVERE_WEATHER_CODES:
        return None

    return {
        "city": reading["city"],
        "timestamp": reading["timestamp"],
        "event_type": "severe_weather_code",
        "reason": f"Severe weather reported (WMO code {code})",
    }


def detect_and_store(reading):
    """
    Run all three detectors on a freshly stored reading. Any that
    fire get written to the events table.

    Called from the poller, only on readings that were actually new
    (not duplicates), so the same event never gets stored twice.
    """
    detectors = [
        check_temperature_swing,
        check_heavy_precipitation,
        check_severe_weather_code,
    ]

    for detector in detectors:
        event = detector(reading)
        if event is not None:
            storage.insert_event(
                city=event["city"],
                timestamp=event["timestamp"],
                event_type=event["event_type"],
                reason=event["reason"],
            )