FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# libgl/glib are needed by OpenCV's FFmpeg backend for RTSP
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data/storage && chown -R appuser /app /data
USER appuser
ENV STORAGE_DIR=/data/storage
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD curl -fsS http://127.0.0.1:8000/api/health/ready || exit 1
# Apply migrations, make sure roles/permissions exist, then start the server.
CMD ["sh", "-c", "alembic upgrade head && python -m app.db.seed --reference-only && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips='*'"]
