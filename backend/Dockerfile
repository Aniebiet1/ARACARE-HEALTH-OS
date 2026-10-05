FROM python:3.11-slim

# WITH_SCRIBE=1 bundles local Whisper speech-to-text (~200 MB more, plus model weights on first use)
ARG WITH_SCRIBE=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARACARE_ENV=production \
    ARACARE_DATA_DIR=/data \
    HF_HOME=/data/models

WORKDIR /app
COPY requirements.txt requirements-scribe.txt ./
RUN pip install -r requirements.txt \
 && if [ "$WITH_SCRIBE" = "1" ]; then pip install -r requirements-scribe.txt; fi

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --system --uid 10001 --home /app aracare \
 && mkdir -p /data && chown aracare /data
USER aracare
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# ONE worker on purpose: the queue sweeper and the WebSocket hub live in-process.
# Migrations run at startup (app/schema.py) before the server accepts requests.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
