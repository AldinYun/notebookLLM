FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INSIGHT_ENVIRONMENT=production \
    INSIGHT_SQLITE_PATH=/data/insight.db \
    INSIGHT_STORAGE_PATH=/data/storage

WORKDIR /app

RUN pip install --no-cache-dir "fastapi>=0.115.0" "uvicorn[standard]>=0.30.0" \
    && useradd --create-home --uid 10001 insight \
    && mkdir -p /data/storage \
    && chown -R insight:insight /app /data

COPY --chown=insight:insight app ./app

USER insight

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
