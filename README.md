# ShortLink

A mini Bitly built as three small Python (FastAPI) services backed by Redis and PostgreSQL.
This is the starter project for the **DevOps from Scratch** workshop.

## Architecture

```
                POST /shorten                       GET /{code}
   client ─────────────────────► url-api     client ─────────────► redirect-service
                                  │   │                              │       │
                       save code  │   │ cache code             look  │       │ add click event
                       + URL      ▼   ▼ + URL                  up    ▼       ▼ (Redis Stream "clicks")
                          PostgreSQL   Redis  ◄──────────────────────┘     Redis
                               ▲                                              │
                               │ count clicks                                 │ read events
                               └──────────────── analytics-worker ◄───────────┘
   client ── GET /stats/{code} ──► url-api (reads URL + click count from PostgreSQL)
```

| Service | Port | What it does |
|---|---|---|
| url-api | 8000 | `POST /shorten` creates a short code, `GET /stats/{code}` returns the click count |
| redirect-service | 8001 | `GET /{code}` redirects to the original URL and records a click event |
| analytics-worker | none | Reads click events from the Redis Stream and updates click counts in PostgreSQL |

## Run it locally (no Docker)

You need Python 3.10+, a running Redis and a running PostgreSQL with a `shortlink` user and database.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/url-api/requirements.txt \
            -r services/redirect-service/requirements.txt \
            -r services/analytics-worker/requirements.txt
```

Start each service in its own terminal (with the virtual environment active):

```bash
cd services/url-api          && uvicorn main:app --port 8000
cd services/redirect-service && uvicorn main:app --port 8001
cd services/analytics-worker && python worker.py
```

Then run the end-to-end check from the project root:

```bash
./scripts/smoke-test.sh
```

## Configuration

All settings are environment variables with local defaults (see `.env.example`):
`DATABASE_URL`, `REDIS_URL`, `BASE_URL`, `STREAM_NAME`.
