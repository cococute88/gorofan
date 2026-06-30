# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# install deps first for layer caching
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY . .

# data dir for SQLite + media (mounted volume in compose)
RUN mkdir -p /app/data/media

EXPOSE 8000

# Apply migrations then start (SQLite => single worker, design 15.3)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
