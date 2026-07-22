# Uptime Monitor

**English** | [Русский](README.ru.md)

Asynchronous website uptime monitoring service built with **FastAPI** and **asyncio**.

You register websites through a REST API. A background scheduler then checks all of
them concurrently on a fixed interval (via `httpx`), and stores the history of every
check — status code, response time, and whether the site was up.

> An MVP built around real async I/O: concurrent network checks with a bounded
> concurrency limit, a background task in the application lifespan, a layered
> architecture, and dependency injection.

---

## Tech stack

| Area | Choice |
| --- | --- |
| Language | Python 3.14 |
| Web framework | FastAPI + Uvicorn (ASGI) |
| API docs | Swagger UI / OpenAPI (auto-generated) |
| HTTP client | httpx (async) |
| Database | SQLite via SQLAlchemy 2.0 (async) + aiosqlite |
| Validation / settings | Pydantic v2, pydantic-settings |
| Tests | pytest, pytest-asyncio |
| Packaging | uv |

---

## Project layout

```
app/
  main.py            # FastAPI app + lifespan (starts the background scheduler)
  config.py          # Settings (overridable via environment variables)
  database.py        # Async engine, session factory, fail-fast DB guard
  models.py          # SQLAlchemy models: Site, CheckResult
  schemas.py         # Pydantic schemas (API input/output)
  crud.py            # Database operations (no HTTP knowledge)
  installation.py    # One-off database setup (create tables)
  routers/
    sites.py         # /sites endpoints
  monitor/
    checker.py       # check_site(): checks ONE site (pure network, no DB)
    scheduler.py     # run_monitor(): background loop, concurrent checks
tests/
  test_database.py   # tests for the fail-fast DB guard
```

The layers are kept separate: `checker` knows the network but not the database,
`crud` knows the database but not HTTP, and `scheduler` is the only place they meet.

---

## Setup

Requires [uv](https://docs.astral.sh/uv/). Install dependencies:

```bash
uv sync
```

This creates a local virtual environment (`.venv`) and installs everything from
`uv.lock`.

> **Run all commands from the project root.** The database path is relative, so
> starting from another directory makes the app look for the database in the wrong
> place — and it will refuse to start rather than create an empty one.

---

## Database

The application never creates the database on its own (fail-fast: if the database
is missing, it refuses to start instead of silently making an empty one). Create it
once with the installation command:

```bash
uv run python -m app.installation
```

To drop and recreate all tables (**erases all data**):

```bash
uv run python -m app.installation --force
```

---

## Running the server

```bash
uv run uvicorn app.main:app --reload
```

Then open the interactive API docs (Swagger UI):

```
http://127.0.0.1:8000/docs
```

On startup the background scheduler begins checking active sites. Round summaries
are logged to the console, for example:

```
Round done: 6 checked, 4 down, took 5.02s
```

---

## Configuration

All settings have defaults and can be overridden with environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `CHECK_INTERVAL_SECONDS` | `30` | Pause between check rounds |
| `REQUEST_TIMEOUT_SECONDS` | `5` | Timeout for one site check |
| `MAX_CONCURRENT_CHECKS` | `20` | Max checks running at the same time |
| `DATABASE_URL` | `sqlite+aiosqlite:///./monitor.db` | Database connection string |

Example (Windows PowerShell):

```powershell
$env:CHECK_INTERVAL_SECONDS = 10
uv run uvicorn app.main:app
```

---

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/sites` | Add a site: `{ "url": "...", "name": "..." }` |
| `GET` | `/sites` | List all sites |
| `GET` | `/sites/{id}` | Get one site |
| `DELETE` | `/sites/{id}` | Delete a site and its history |

A site counts as **up** if it answered and the status code is below 500. A `4xx`
still counts as up (the server is healthy, the request is the problem); only
timeouts, connection errors, and `5xx` count as down.

---

## Trying a single check

`checker.py` is a library module (no command-line entry point). To try one check
interactively, use the Python REPL:

```bash
uv run python
```

```python
import asyncio, httpx
from app.monitor.checker import check_site

async def try_url(url):
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        return await check_site(client, url)

asyncio.run(try_url("https://example.com"))
# CheckOutcome(is_up=True, status_code=200, response_time_ms=120.4, error=None)

asyncio.run(try_url("https://httpbin.org/status/500"))
# CheckOutcome(is_up=False, status_code=500, response_time_ms=310.0, error='http_500')
```

---

## Tests

```bash
uv run pytest
```

---

## Roadmap

- `GET /sites/{id}/checks` — recent check history
- `GET /sites/{id}/stats` — uptime % and average response time over a period
- Unit tests for `check_site` using `httpx.MockTransport`
- Docker image
