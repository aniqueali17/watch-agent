"""
Tests for the three required endpoints. We verify the response
shape (keys and types), not detailed business logic — that's
already covered by the dedup and event tests.

Uses FastAPI's TestClient, which exercises the real app without
starting an actual server.
"""

from fastapi.testclient import TestClient

from app import storage
from app.main import app


client = TestClient(app)


def test_health_returns_correct_shape(temp_db):
    """
    /health must return status, readings_stored, events_stored.
    Spec is strict about this exact shape.
    """
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["readings_stored"], int)
    assert isinstance(data["events_stored"], int)


def test_readings_returns_correct_shape(temp_db):
    """
    /readings must return {"readings": [ ... ]}, even when empty.
    """
    response = client.get("/readings")

    assert response.status_code == 200
    data = response.json()
    assert "readings" in data
    assert isinstance(data["readings"], list)


def test_events_returns_correct_shape(temp_db):
    """
    /events must return {"events": [ ... ]}, even when empty.
    """
    response = client.get("/events")

    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert isinstance(data["events"], list)


def test_readings_with_seeded_data(temp_db):
    """
    Seed two readings and confirm both come back through the API
    with all the expected fields.
    """
    storage.insert_reading(
        city="Ottawa",
        timestamp="2026-05-31T12:00",
        temperature_2m=20.0,
        apparent_temperature=19.0,
        precipitation=0.0,
        wind_speed_10m=10.0,
        weather_code=0,
    )
    storage.insert_reading(
        city="Toronto",
        timestamp="2026-05-31T12:00",
        temperature_2m=24.0,
        apparent_temperature=23.0,
        precipitation=0.0,
        wind_speed_10m=15.0,
        weather_code=1,
    )

    response = client.get("/readings")
    data = response.json()

    assert len(data["readings"]) == 2
    # Every reading should include all the stored fields.
    for reading in data["readings"]:
        assert "city" in reading
        assert "timestamp" in reading
        assert "temperature_2m" in reading
        assert "precipitation" in reading


def test_readings_filtered_by_city(temp_db):
    """
    ?city=Ottawa should return only Ottawa rows.
    """
    storage.insert_reading(
        city="Ottawa",
        timestamp="2026-05-31T12:00",
        temperature_2m=20.0,
        apparent_temperature=19.0,
        precipitation=0.0,
        wind_speed_10m=10.0,
        weather_code=0,
    )
    storage.insert_reading(
        city="Toronto",
        timestamp="2026-05-31T12:00",
        temperature_2m=24.0,
        apparent_temperature=23.0,
        precipitation=0.0,
        wind_speed_10m=15.0,
        weather_code=1,
    )

    response = client.get("/readings?city=Ottawa")
    data = response.json()

    assert len(data["readings"]) == 1
    assert data["readings"][0]["city"] == "Ottawa"