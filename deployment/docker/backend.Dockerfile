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
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD curl -fsS http://127.0.0.1:${PORT:-8000}/api/health/ready || exit 1
# Migrations, roles/permissions, optional first admin / demo data, then the server (see backend/scripts/start.sh).
CMD ["sh", "scripts/start.sh"]
