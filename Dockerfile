# AM 30/Jul/26 - base image with the project's Python version
FROM python:3.14-slim

# AM 30/Jul/26 - bring in the uv binary from its official image (no pip needed)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# AM 30/Jul/26 - install dependencies FIRST, in their own cached layer: copy only the
# lock files, then sync. This layer rebuilds only when dependencies change, not on
# every code edit (Docker layer caching). --no-dev skips pytest etc.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# AM 30/Jul/26 - put the project's virtualenv on PATH so we call uvicorn directly,
# without invoking uv at runtime
ENV PATH="/app/.venv/bin:$PATH"

# AM 30/Jul/26 - now copy the app code (edits here do not bust the dependency layer)
COPY app/ ./app/

# AM 30/Jul/26 - the database lives in a mounted volume at /app/data so it survives
# container restarts; override the relative default with an absolute path in the volume
ENV DATABASE_URL="sqlite+aiosqlite:////app/data/monitor.db"

# AM 30/Jul/26 - port the app listens on inside the container
EXPOSE 8000

# AM 30/Jul/26 - bind to 0.0.0.0 so the port is reachable from outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
