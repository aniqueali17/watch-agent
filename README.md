# watch-agent

# WatchAgent

A small backend service that polls live weather for Ottawa, Toronto, and Vancouver, decides when something worth noticing happened, and exposes both the raw readings and the detected events through an HTTP API.

Built as a take-home challenge focused on infrastructure and event-detection design. The interesting part of this project is not collecting the data, that part is easy. The interesting part is deciding what counts as a "notable" event as mentioned in challenge, which is what most of the design discussion below is about.

## What it does

Every five minutes, a background poller fetches the current weather for each of the three cities from the [Open-Meteo](https://open-meteo.com/) API. Each new reading is stored in a local SQLite database. After a reading is stored, three small detectors run on it to decide whether anything notable happened, a sharp temperature change, heavy rain, or a severe weather code from the WMO classification. Any event that fires is also stored in the database.

A FastAPI app exposes the data through three endpoints:

- `GET /health` — service status plus how many readings and events are in the database.
- `GET /readings?city=Ottawa&limit=50` — most recent readings, optionally filtered by city.
- `GET /events?city=Ottawa&limit=50` — most recent events, optionally filtered by city.

The poller runs in a background thread inside the same process as the API, so the whole thing is one container.