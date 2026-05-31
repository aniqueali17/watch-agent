import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "watch_agent.db")

def get_connection():
    """
    Open a connection to the SQLite database.

    We set row_factory so query results behave like dictionaries
    (row["city"] instead of row[0]) — easier to read and to convert
    into JSON when the API returns results.
    """
    # SQLite creates the file automatically if it doesn't exist yet.
    conn = sqlite3.connect(DB_PATH)

    # By default sqlite3 returns plain tuples. sqlite3.Row gives us
    # dict-like access by column name, which is much clearer downstream.
    conn.row_factory = sqlite3.Row

    return conn

def init_db():
    """
    Create the readings and events tables if they don't already exist.

    Called once when the app starts. Safe to call repeatedly — the
    IF NOT EXISTS clauses make it a no-op after the first run.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Five separate columns instead of one JSON blob — makes per-field
    # queries easy later (avg temp, max wind, etc.) without parsing.
    # UNIQUE(city, timestamp) is the dedup: Open-Meteo only updates
    # hourly but we poll more often, so the same reading keeps coming
    # back. Letting the DB reject duplicates is cleaner than checking
    # in Python first.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            temperature_2m REAL,
            apparent_temperature REAL,
            precipitation REAL,
            wind_speed_10m REAL,
            weather_code INTEGER,
            UNIQUE(city, timestamp)
        )
    """)

    # reason is what someone reading the events list will actually
    # see. event_type is just a tag like "temperature_spike", but
    # reason is the full sentence that explains what happened and
    # why we flagged it.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            reason TEXT NOT NULL
        )
    """)

    conn.commit()  # writes the table creation to disk
    conn.close()


def insert_reading(city, timestamp, temperature_2m, apparent_temperature,
                   precipitation, wind_speed_10m, weather_code):
    """
    Save a single weather reading.

    Returns True if it was actually stored, False if it was a duplicate
    (same city + timestamp already in the DB). The poller uses this
    return value to log "new reading" vs "skipped, already had it".
    """
    conn = get_connection()
    cursor = conn.cursor()

    # INSERT OR IGNORE pairs with the UNIQUE(city, timestamp) constraint
    # in the table. If a row with this city+timestamp already exists,
    # SQLite silently does nothing instead of raising an error.
    # cursor.rowcount tells us whether the row actually went in (1) or
    # was skipped (0), which is how we know if it was a duplicate.
    cursor.execute("""
        INSERT OR IGNORE INTO readings
            (city, timestamp, temperature_2m, apparent_temperature,
             precipitation, wind_speed_10m, weather_code)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (city, timestamp, temperature_2m, apparent_temperature,
          precipitation, wind_speed_10m, weather_code))

    inserted = cursor.rowcount == 1
    conn.commit()
    conn.close()
    return inserted

def insert_event(city, timestamp, event_type, reason):
    """
    Save a single notable event detected by the event logic.

    Unlike readings, events don't need dedup at the DB level. If the
    same event fires twice that's a bug in events.py, not something
    storage should silently swallow.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO events (city, timestamp, event_type, reason)
        VALUES (?, ?, ?, ?)
    """, (city, timestamp, event_type, reason))

    conn.commit()
    conn.close()


def get_readings(city=None, limit=50):
    """
    Fetch stored readings, most recent first.

    city: optional filter. If None, returns readings from all cities.
    limit: how many rows to return (matches the API's default of 50).
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Build the query in two paths instead of one clever conditional.
    # The if/else is more readable than concatenating SQL strings, and
    # we still use ? placeholders so no injection risk either way.
    if city is None:
        cursor.execute("""
            SELECT * FROM readings
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
    else:
        cursor.execute("""
            SELECT * FROM readings
            WHERE city = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (city, limit))

    # Each row is a sqlite3.Row (dict-like). Convert to plain dicts
    # so FastAPI can serialize them to JSON without extra work.
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_events(city=None, limit=50):
    """Same shape as get_readings, but for the events table."""
    conn = get_connection()
    cursor = conn.cursor()

    if city is None:
        cursor.execute("""
            SELECT * FROM events
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
    else:
        cursor.execute("""
            SELECT * FROM events
            WHERE city = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (city, limit))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def count_readings():
    """Total number of readings stored. Used by /health."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM readings")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def count_events():
    """Total number of events stored. Used by /health."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    count = cursor.fetchone()[0]
    conn.close()
    return count