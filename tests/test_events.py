"""
Tests for the three event detectors in app/events.py.

Each test feeds a controlled sequence of readings into storage,
runs the relevant detector directly, and asserts what the
detector returned. We test both positive cases (event fires when
it should) and negative cases (event doesn't fire when it
shouldn't), since both matter for selective detection.
"""

from app import storage, events


# ---------- Temperature swing tests ----------


def test_temperature_swing_fires_on_big_change_within_window(temp_db):
    """
    18°C jumps to 25°C an hour later. That's a 7°C swing inside
    the 90-minute window, so the detector should fire.
    """
    # Previous reading
    storage.insert_reading(
        city="Ottawa",
        timestamp="2026-05-31T12:00",
        temperature_2m=18.0,
        apparent_temperature=17.0,
        precipitation=0.0,
        wind_speed_10m=10.0,
        weather_code=0,
    )
    # Current reading — 1 hour later, +7°C
    current = {
        "city": "Ottawa",
        "timestamp": "2026-05-31T13:00",
        "temperature_2m": 25.0,
        "apparent_temperature": 24.0,
        "precipitation": 0.0,
        "wind_speed_10m": 10.0,
        "weather_code": 0,
    }
    storage.insert_reading(**current)

    event = events.check_temperature_swing(current)

    assert event is not None
    assert event["event_type"] == "temperature_swing"
    assert event["city"] == "Ottawa"
    assert "rose" in event["reason"]


def test_temperature_swing_does_not_fire_on_small_change(temp_db):
    """
    A 2°C change is normal hour-to-hour drift, not a weather event.
    """
    storage.insert_reading(
        city="Ottawa",
        timestamp="2026-05-31T12:00",
        temperature_2m=18.0,
        apparent_temperature=17.0,
        precipitation=0.0,
        wind_speed_10m=10.0,
        weather_code=0,
    )
    current = {
        "city": "Ottawa",
        "timestamp": "2026-05-31T13:00",
        "temperature_2m": 20.0,  # only +2°C
        "apparent_temperature": 19.0,
        "precipitation": 0.0,
        "wind_speed_10m": 10.0,
        "weather_code": 0,
    }
    storage.insert_reading(**current)

    event = events.check_temperature_swing(current)

    assert event is None


def test_temperature_swing_does_not_fire_when_previous_too_old(temp_db):
    """
    A 7°C swing over six hours is just normal daily warming,
    not a rate-of-change event. The 90-minute window guards
    against this.
    """
    storage.insert_reading(
        city="Ottawa",
        timestamp="2026-05-31T06:00",  # six hours earlier
        temperature_2m=15.0,
        apparent_temperature=14.0,
        precipitation=0.0,
        wind_speed_10m=10.0,
        weather_code=0,
    )
    current = {
        "city": "Ottawa",
        "timestamp": "2026-05-31T12:00",
        "temperature_2m": 22.0,
        "apparent_temperature": 21.0,
        "precipitation": 0.0,
        "wind_speed_10m": 10.0,
        "weather_code": 0,
    }
    storage.insert_reading(**current)

    event = events.check_temperature_swing(current)

    assert event is None


def test_temperature_swing_does_not_fire_on_first_reading(temp_db):
    """
    A city's very first reading has no history to compare against,
    so the detector should silently return None.
    """
    current = {
        "city": "Ottawa",
        "timestamp": "2026-05-31T12:00",
        "temperature_2m": 25.0,
        "apparent_temperature": 24.0,
        "precipitation": 0.0,
        "wind_speed_10m": 10.0,
        "weather_code": 0,
    }
    storage.insert_reading(**current)

    event = events.check_temperature_swing(current)

    assert event is None



# ---------- Heavy precipitation tests ----------


def test_heavy_precipitation_fires_above_threshold(temp_db):
    """
    10 mm of rain in an hour is heavy by WMO standards — fire.
    """
    reading = {
        "city": "Vancouver",
        "timestamp": "2026-05-31T12:00",
        "temperature_2m": 14.0,
        "apparent_temperature": 13.0,
        "precipitation": 10.0,
        "wind_speed_10m": 15.0,
        "weather_code": 65,
    }
    event = events.check_heavy_precipitation(reading)

    assert event is not None
    assert event["event_type"] == "heavy_precipitation"
    assert event["city"] == "Vancouver"


def test_heavy_precipitation_does_not_fire_below_threshold(temp_db):
    """
    Light rain (3 mm) is moderate at most. Shouldn't fire.
    """
    reading = {
        "city": "Vancouver",
        "timestamp": "2026-05-31T12:00",
        "temperature_2m": 14.0,
        "apparent_temperature": 13.0,
        "precipitation": 3.0,
        "wind_speed_10m": 15.0,
        "weather_code": 61,
    }
    event = events.check_heavy_precipitation(reading)

    assert event is None


def test_heavy_precipitation_handles_none(temp_db):
    """
    Open-Meteo sometimes reports None for precipitation when it
    isn't raining. The detector should treat that as no rain, not crash.
    """
    reading = {
        "city": "Ottawa",
        "timestamp": "2026-05-31T12:00",
        "temperature_2m": 22.0,
        "apparent_temperature": 21.0,
        "precipitation": None,
        "wind_speed_10m": 10.0,
        "weather_code": 0,
    }
    event = events.check_heavy_precipitation(reading)

    assert event is None


# ---------- Severe weather code tests ----------


def test_severe_weather_code_fires_on_thunderstorm(temp_db):
    """
    Code 95 is a thunderstorm in the WMO classification — fire.
    """
    reading = {
        "city": "Toronto",
        "timestamp": "2026-05-31T12:00",
        "temperature_2m": 24.0,
        "apparent_temperature": 23.0,
        "precipitation": 5.0,
        "wind_speed_10m": 30.0,
        "weather_code": 95,
    }
    event = events.check_severe_weather_code(reading)

    assert event is not None
    assert event["event_type"] == "severe_weather_code"
    assert "95" in event["reason"]


def test_severe_weather_code_does_not_fire_on_clear_sky(temp_db):
    """
    Code 0 means clear sky. Definitely not an event.
    """
    reading = {
        "city": "Toronto",
        "timestamp": "2026-05-31T12:00",
        "temperature_2m": 24.0,
        "apparent_temperature": 23.0,
        "precipitation": 0.0,
        "wind_speed_10m": 10.0,
        "weather_code": 0,
    }
    event = events.check_severe_weather_code(reading)

    assert event is None