# Use a small, official Python base image. The slim variant skips
# packages we don't need (compilers, docs) — smaller image, faster pulls.
FROM python:3.11-slim

# Where the app code lives inside the container. Just a convention;
# could be anything, but /app is standard for this kind of layout.
WORKDIR /app

# Install dependencies first, as a separate layer from the source code.
# Docker caches each step, so if requirements.txt doesn't change, the
# slow "pip install" step is reused on subsequent builds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the application code. This layer rebuilds every time you
# change a .py file, which is fine — it's fast.
COPY app/ ./app/

# Where the database file should live inside the container. We'll
# mount a host folder onto /data via docker-compose, so the SQLite
# file persists across restarts.
ENV DB_PATH=/data/watch_agent.db

# The port FastAPI listens on. Documentation only — docker-compose
# is what actually publishes it to the host.
EXPOSE 8000

# Run uvicorn directly (no --reload, since this is production-style).
# Binding to 0.0.0.0 instead of 127.0.0.1 is mandatory inside a
# container — otherwise the port wouldn't be reachable from outside.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]