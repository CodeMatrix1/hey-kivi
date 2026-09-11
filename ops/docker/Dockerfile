# Hey Kivi Phase 1 — standalone package image
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./hindsight_pipeline_2

RUN mkdir -p /app/hindsight_pipeline_2/artifacts/runtime \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV KIVI_MEMORY_BACKEND=hindsight
ENV HINDSIGHT_BASE_URL=http://hindsight:8888
ENV HINDSIGHT_BANK_PREFIX=kivi
ENV KIVI2_DB_PATH=/app/hindsight_pipeline_2/artifacts/runtime/kivi.sqlite3
ENV KIVI_REQUIRE_LLM=true
ENV KIVI_API_PORT=8002

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["python", "-m", "hindsight_pipeline_2.kivi.api"]
