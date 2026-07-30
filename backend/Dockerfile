FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml alembic.ini ./
COPY alembic ./alembic

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY app ./app

RUN useradd \
      --create-home \
      --uid 10001 \
      --shell /usr/sbin/nologin \
      bcworkspace \
    && chown -R bcworkspace:bcworkspace /app

USER bcworkspace

EXPOSE 8000

HEALTHCHECK \
  --interval=20s \
  --timeout=5s \
  --start-period=30s \
  --retries=5 \
  CMD curl --fail --silent http://localhost:8000/api/health >/dev/null || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
