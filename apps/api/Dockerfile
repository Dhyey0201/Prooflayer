# ProofLayer API image. Build context: apps/api.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY prooflayer_api ./prooflayer_api

# Non-root runtime user; the only writable path is the SQLite data volume.
RUN useradd --create-home --uid 10001 prooflayer \
    && mkdir -p /app/data && chown prooflayer:prooflayer /app/data
USER prooflayer

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn prooflayer_api.main:app --host 0.0.0.0 --port 8000"]
