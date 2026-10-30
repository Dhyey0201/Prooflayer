# Hosted read-only replay of recorded ProofLayer runs (docs/08_HOSTED_DEMO.md).
# Build context: repository root.
#   docker build -f demo/Dockerfile -t prooflayer-demo .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PROOFLAYER_ENV=production \
    PROOFLAYER_READ_ONLY=true \
    PROOFLAYER_MOCK_MODE=true \
    PROOFLAYER_WORKER_ENABLED=false \
    VERIFIER_DRIVER=disabled \
    DATABASE_URL=sqlite:////app/data/prooflayer.db \
    PROOFLAYER_EVIDENCE_LEDGER=/app/data/evidence-ledger.jsonl \
    PROOFLAYER_BENCHMARK_REPORT=/app/demo/benchmark-report.json

WORKDIR /app

COPY apps/api/requirements.txt .
RUN pip install -r requirements.txt

COPY apps/api/alembic.ini .
COPY apps/api/migrations ./migrations
COPY apps/api/prooflayer_api ./prooflayer_api
# Recorded evidence, copied byte for byte: hash chains and ledger entries are as issued.
COPY demo/prooflayer-demo.db demo/evidence-ledger.jsonl /app/demo/
COPY benchmarks/results/benchmark-report.json /app/demo/

RUN useradd --create-home --uid 10001 prooflayer \
    && mkdir -p /app/data && chown prooflayer:prooflayer /app/data
USER prooflayer

EXPOSE 8000
# The app mirrors templates into the DB on boot, so it works on a fresh copy; the
# originals in /app/demo are never written. PORT is set by most hosting platforms.
CMD ["sh", "-c", "cp /app/demo/prooflayer-demo.db /app/data/prooflayer.db && cp /app/demo/evidence-ledger.jsonl /app/data/ && alembic upgrade head && exec uvicorn prooflayer_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
