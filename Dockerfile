# GeoWatch Pro — container image
# Build:  docker build -t geowatch .
# Run:    docker run -p 8501:8501 --env-file .env -v geowatch-data:/app/data geowatch

FROM python:3.12-slim

# libxml2/libxslt for lxml, git for pip installs that need it
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/logs

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8501

EXPOSE 8501

# Healthcheck hits the dashboard's own status endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/api/summary', timeout=4)" || exit 1

CMD ["python", "run.py"]
