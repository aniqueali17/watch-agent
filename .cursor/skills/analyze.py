"""
Data analysis skill for the WatchAgent project.

Run from the command line with a question:
    python .cursor/skills/analyze.py "summary for Ottawa"
    python .cursor/skills/analyze.py "compare cities"
    python .cursor/skills/analyze.py "recent events"
    python .cursor/skills/analyze.py "trend for Vancouver"

Outputs a JSON object with the original question, what the script
understood, and the structured result. Pattern matching is used
instead of LLM parsing so the skill runs offline, needs no API
keys, and gives deterministic output.
"""

import json
import sys
import sqlite3
import os
from datetime import datetime, timedelta


# The skill reads the same DB the app writes to. DB_PATH matches
# storage.py: env var override, or the local file in the repo root.
DB_PATH = os.environ.get("DB_PATH", "watch_agent.db")


def parse_question(question):
    """
    Figure out which of the four analyses the question is asking for
    and pull out the city name if there is one.

    Returns a dict like {"type": "summary", "city": "Ottawa"} or
    {"type": "unknown"} if nothing matched.
    """
    q = question.lower()

    # City detection happens first so the routing doesn't have to
    # repeat the same check four times. None if no city mentioned.
    city = None
    for known in ("ottawa", "toronto", "vancouver"):
        if known in q:
            city = known.title()
            break

    if "compare" in q or "comparison" in q:
        return {"type": "comparison"}

    if "event" in q:
        return {"type": "events", "city": city}

    if "trend" in q:
        return {"type": "trend", "city": city}

    if "summary" in q or "average" in q or "summarize" in q:
        return {"type": "summary", "city": city}

    return {"type": "unknown"}

def get_db_rows(query, params=()):
    """
    Open the database, run a query, return rows as plain dicts.

    Uses row_factory so we get dict-like access instead of tuples,
    matching the pattern in storage.py so this script feels native
    to the rest of the project.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def analyze_summary(city):
    """
    Min, max, and average for temperature, precipitation, and wind
    over the last 24 hours. If a city is given, scoped to that city;
    otherwise across all three.
    """
    # 24 hours ago in ISO format. We compare TEXT timestamps as
    # strings, which works because ISO 8601 is sortable.
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat(timespec="minutes")

    if city is None:
        rows = get_db_rows(
            """
            SELECT temperature_2m, precipitation, wind_speed_10m
            FROM readings
            WHERE timestamp >= ?
            """,
            (cutoff,),
        )
        scope = "all cities"
    else:
        rows = get_db_rows(
            """
            SELECT temperature_2m, precipitation, wind_speed_10m
            FROM readings
            WHERE city = ? AND timestamp >= ?
            """,
            (city, cutoff),
        )
        scope = city

    if not rows:
        return {
            "scope": scope,
            "window_hours": 24,
            "reading_count": 0,
            "message": "No readings in the last 24 hours for this scope.",
        }

    temps = [r["temperature_2m"] for r in rows if r["temperature_2m"] is not None]
    precip = [r["precipitation"] for r in rows if r["precipitation"] is not None]
    wind = [r["wind_speed_10m"] for r in rows if r["wind_speed_10m"] is not None]

    return {
        "scope": scope,
        "window_hours": 24,
        "reading_count": len(rows),
        "temperature_c": {
            "min": min(temps),
            "max": max(temps),
            "avg": round(sum(temps) / len(temps), 2),
        },
        "precipitation_mm": {
            "min": min(precip),
            "max": max(precip),
            "avg": round(sum(precip) / len(precip), 2),
        },
        "wind_speed_kmh": {
            "min": min(wind),
            "max": max(wind),
            "avg": round(sum(wind) / len(wind), 2),
        },
    }


def analyze_comparison():
    """
    Side-by-side averages for all three cities over the last 24 hours,
    plus the biggest temperature gap between any pair.

    The gap callout is the interesting bit — it surfaces "something
    different is happening between cities" in one number, which is
    exactly the cross-city signal the spec hints at.
    """
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat(timespec="minutes")

    rows = get_db_rows(
        """
        SELECT city,
               AVG(temperature_2m) AS avg_temp,
               AVG(precipitation) AS avg_precip,
               AVG(wind_speed_10m) AS avg_wind,
               COUNT(*) AS reading_count
        FROM readings
        WHERE timestamp >= ?
        GROUP BY city
        """,
        (cutoff,),
    )

    if not rows:
        return {
            "window_hours": 24,
            "cities": [],
            "message": "No readings in the last 24 hours.",
        }

    # Clean up the per-city dicts and round the numbers.
    cities = []
    for r in rows:
        cities.append({
            "city": r["city"],
            "reading_count": r["reading_count"],
            "avg_temperature_c": round(r["avg_temp"], 2) if r["avg_temp"] is not None else None,
            "avg_precipitation_mm": round(r["avg_precip"], 2) if r["avg_precip"] is not None else None,
            "avg_wind_speed_kmh": round(r["avg_wind"], 2) if r["avg_wind"] is not None else None,
        })

    # Biggest temperature gap. Skip if fewer than two cities have data.
    temp_gap = None
    cities_with_temp = [c for c in cities if c["avg_temperature_c"] is not None]
    if len(cities_with_temp) >= 2:
        hottest = max(cities_with_temp, key=lambda c: c["avg_temperature_c"])
        coldest = min(cities_with_temp, key=lambda c: c["avg_temperature_c"])
        temp_gap = {
            "hottest_city": hottest["city"],
            "coldest_city": coldest["city"],
            "difference_c": round(
                hottest["avg_temperature_c"] - coldest["avg_temperature_c"], 2
            ),
        }

    return {
        "window_hours": 24,
        "cities": cities,
        "biggest_temperature_gap": temp_gap,
    }


def analyze_events(city):
    """
    Events from the last 24 hours, newest first, optionally scoped
    to one city. Returns counts grouped by event_type alongside the
    raw event list, so the reader can see both "what fired" and
    "how often" in one shot.
    """
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat(timespec="minutes")

    if city is None:
        rows = get_db_rows(
            """
            SELECT city, timestamp, event_type, reason
            FROM events
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            """,
            (cutoff,),
        )
        scope = "all cities"
    else:
        rows = get_db_rows(
            """
            SELECT city, timestamp, event_type, reason
            FROM events
            WHERE city = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            """,
            (city, cutoff),
        )
        scope = city

    # Count how many fired per type. This will tell the reader at a glance
    # whether one detector is dominating or whether things are mixed.
    counts_by_type = {}
    for r in rows:
        counts_by_type[r["event_type"]] = counts_by_type.get(r["event_type"], 0) + 1

    return {
        "scope": scope,
        "window_hours": 24,
        "total_events": len(rows),
        "counts_by_type": counts_by_type,
        "events": rows,
    }

def analyze_trend(city):
    """
    Last 24 readings for one city in chronological order, plus a
    "direction" callout that says rising, falling, or steady based
    on first vs last temperature.

    The direction is intentionally simple — it's a sanity check, not
    a forecast. A more accurate version would fit a line and check
    the slope, but for 24 points an honest first-vs-last comparison
    is more transparent.
    """
    if city is None:
        return {
            "message": "Trend needs a specific city. Try 'trend for Ottawa'.",
        }

    rows = get_db_rows(
        """
        SELECT timestamp, temperature_2m
        FROM readings
        WHERE city = ?
        ORDER BY timestamp DESC
        LIMIT 24
        """,
        (city,),
    )

    if len(rows) < 2:
        return {
            "city": city,
            "reading_count": len(rows),
            "message": "Not enough data to determine a trend.",
        }

    # Reverse so the list is oldest-first, which reads more naturally
    # for a "trend over time" view.
    rows.reverse()

    first_temp = rows[0]["temperature_2m"]
    last_temp = rows[-1]["temperature_2m"]
    change = round(last_temp - first_temp, 2)

    # 1°C threshold so we don't call random fluctuation a trend.
    if change > 1:
        direction = "rising"
    elif change < -1:
        direction = "falling"
    else:
        direction = "steady"

    return {
        "city": city,
        "reading_count": len(rows),
        "first_reading": rows[0],
        "last_reading": rows[-1],
        "temperature_change_c": change,
        "direction": direction,
        "series": rows,
    }


def main():
    """
    Read a question from the command line, route to the right
    analysis, print a structured JSON answer.
    """
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "No question provided.",
            "usage": "python analyze.py \"<question>\"",
            "examples": [
                "summary for Ottawa",
                "compare cities",
                "recent events",
                "trend for Vancouver",
            ],
        }, indent=2))
        sys.exit(1)

    question = sys.argv[1]
    parsed = parse_question(question)

    # Route to the right analysis based on what the parser understood.
    if parsed["type"] == "summary":
        result = analyze_summary(parsed.get("city"))
        interpretation = f"Per-city summary for {parsed.get('city') or 'all cities'}"
    elif parsed["type"] == "comparison":
        result = analyze_comparison()
        interpretation = "Cross-city comparison over the last 24 hours"
    elif parsed["type"] == "events":
        result = analyze_events(parsed.get("city"))
        interpretation = f"Events for {parsed.get('city') or 'all cities'}"
    elif parsed["type"] == "trend":
        result = analyze_trend(parsed.get("city"))
        interpretation = f"Temperature trend for {parsed.get('city') or '(no city specified)'}"
    else:
        result = {
            "error": "Could not understand the question.",
            "supported_question_types": [
                "summary for <city>",
                "compare cities",
                "recent events [for <city>]",
                "trend for <city>",
            ],
        }
        interpretation = "Unrecognized question"

    output = {
        "question": question,
        "interpretation": interpretation,
        "result": result,
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()