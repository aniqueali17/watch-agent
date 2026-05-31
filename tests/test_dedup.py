"""
Test that storage.insert_reading actually deduplicates on
(city, timestamp) — the core requirement from the spec.
"""

from app import storage


def test_duplicate_reading_is_not_stored_twice(temp_db):
    """
    Given the same (city, timestamp) twice, only one row ends up
    in the database. The UNIQUE constraint plus INSERT OR IGNORE
    in storage.py is what makes this work.
    """
    city = "Ottawa"
    timestamp = "2026-05-31T12:00"

    first = storage.insert_reading(
        city=city,
        timestamp=timestamp,
        temperature_2m=20.0,
        apparent_temperature=19.0,
        precipitation=0.0,
        wind_speed_10m=10.0,
        weather_code=0,
    )

    second = storage.insert_reading(
        city=city,
        timestamp=timestamp,
        temperature_2m=20.0,
        apparent_temperature=19.0,
        precipitation=0.0,
        wind_speed_10m=10.0,
        weather_code=0,
    )

    assert first is True
    assert second is False
    assert storage.count_readings() == 1