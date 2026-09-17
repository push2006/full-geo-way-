# GeoWatch Pro

One command. Continuous geopolitical collection + live dashboard.

## Start

```bash
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Open **http://127.0.0.1:8501**

## What it does

- RSS + page change monitoring from `config/sources.yaml` (single file)
- Trends (Reddit, HN, YouTube, Mastodon, …)
- Google News keywords (`ENABLE_GNEWS=true`)
- OFAC sanctions name screen (`ENABLE_SANCTIONS_SCREEN=true`)
- Optional Tor / onion (`USE_TOR=true`)
- Live YouTube streams (add links in the dashboard)
- SQLite **or** MongoDB (one or **two** full Mongo URLs)

## Storage

### SQLite (default)
```env
STORAGE_BACKEND=sqlite
```

### One MongoDB
```env
STORAGE_BACKEND=mongodb
MONGODB_URI=mongodb://user:pass@host:27017/geowatch?authSource=admin
MONGODB_DB=geowatch
```

### Two MongoDB full URLs
```env
STORAGE_BACKEND=mongodb
MONGODB_URI=mongodb://user:pass@host1:27017/geowatch?authSource=admin
MONGODB_DB=geowatch
MONGODB_URI_2=mongodb://user:pass@host2:27017/archive?authSource=admin
MONGODB_DB_2=archive
```

- **Primary** (`MONGODB_URI`): reads + writes  
- **Secondary** (`MONGODB_URI_2`): reads merged into the feed  
- Content API supports large collections (limit up to 10,000,000)

## Dashboard

Feed · Sources · Changes · Breakdown · Weekly · Live Streams  

Filters: All / Critical / BRICS / High score · Auto-refresh · Dark/light theme  

## Cloud

```bash
python run.py --host 0.0.0.0 --port 8501
```

`Procfile` included for platform deploys.

## Map & export

- Dashboard **Map** tab: region pins from sources (Leaflet)
- **Export** button: download recent content as JSON

## Docker

```bash
docker compose up                      # SQLite, simplest
docker compose --profile mongo up      # with a bundled MongoDB
```
or plain Docker:
```bash
docker build -t geowatch .
docker run -p 8501:8501 --env-file .env -v geowatch-data:/app/data geowatch
```

## One-line local setup

```bash
./install.sh      # venv + deps + .env, then: python run.py
```

Or `make install`. See `make help`-style targets in the `Makefile` (`make run`, `make dashboard`, `make check-feeds`, `make docker-up`, ...).

## Automated feed health checks

`scripts/check-feeds.sh` — plain bash + curl, no Python needed — checks every URL in `config/sources.yaml` and writes `scripts/feed-health-report.csv`. Runs automatically every Monday via `.github/workflows/check-feeds.yml`, and immediately on any PR that touches `config/sources.yaml`.
