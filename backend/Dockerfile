# Development image: installs in editable mode so a bind-mounted ./src
# overlays this at runtime and --reload picks up changes. Used by both the
# `api` and `worker` services in docker-compose.yml (different `command:`).
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "instamart_engine.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
