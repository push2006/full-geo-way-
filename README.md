# GeoWatch Pro

> One command. Continuous geopolitical collection + live dashboard.

GeoWatch Pro is an automated intelligence collector and analytics dashboard engineered to continuously aggregate geopolitical data, open-source trends, and critical web changes into a unified operational feed.

---

## 🚀 Quick Start

Get your local instance up and running in less than a minute.

### Standard Setup
```bash
pip install -r requirements.txt
cp .env.example .env
python run.py
```
Open your browser and navigate to **http://127.0.0.1:8501**

### One-Line Setup
Alternatively, use the automated setup script or Makefile shortcuts:
```bash
./install.sh      # Sets up venv, installs dependencies, and creates .env
# Then run:
python run.py
```
*You can also use `make install`. Run `make help` to see all available workflow automation hooks (`make run`, `make dashboard`, `make check-feeds`, `make docker-up`).*

---

## 🛠 Core Capabilities

- **OSINT Aggregator:** Continuous parsing of RSS feeds and raw page delta tracking defined in a single file (`config/sources.yaml`).
- **Trend Indexing:** Scrapes trending metrics across major networks including Reddit, Hacker News, YouTube, and Mastodon.
- **Deep Monitoring:** Native hook integrations for Google News keywords (`ENABLE_GNEWS=true`) and OFAC sanctions list screening (`ENABLE_SANCTIONS_SCREEN=true`).
- **Anonymity Routing:** Built-in support for proxying collection traffic securely through Tor/Onion layers (`USE_TOR=true`).
- **Live Operations:** Embed and monitor operational live YouTube video streams directly from the frontend.

---

## 💾 Storage Backends

Configure your data layer directly within your `.env` file. The repository's data engine is scale-tested to comfortably manage up to **10,000,000 documents**.

### SQLite (Default / Lightweight Development)
```env
STORAGE_BACKEND=sqlite
```

### Single MongoDB Instance
```env
STORAGE_BACKEND=mongodb
MONGODB_URI=mongodb://user:pass@host:27017/geowatch?authSource=admin
MONGODB_DB=geowatch
```

### Dual MongoDB Cluster (Federated Reads)
```env
STORAGE_BACKEND=mongodb
MONGODB_URI=mongodb://user:pass@host1:27017/geowatch?authSource=admin
MONGODB_DB=geowatch
MONGODB_URI_2=mongodb://user:pass@host2:27017/archive?authSource=admin
MONGODB_DB_2=archive
```
- **Primary (`MONGODB_URI`):** Handles core runtime read and write collection cycles.
- **Secondary (`MONGODB_URI_2`):** Aggregates historical read archives, blending them seamlessly into the active dashboard feed.

---

## 📊 Dashboard Navigation

The interactive web interface maps your collection infrastructure into distinct operational modules:
**Feed** · **Sources** · **Changes** · **Breakdown** · **Weekly** · **Live Streams**

- **Geospatial Mapping:** A specialized **Map** tab dynamically plots visual region pins using Leaflet based on parsed geographic source origins.
- **Intelligence Filters:** Instantly toggle datasets through pre-sorted views: *All*, *Critical*, *BRICS*, or *High Score*.
- **Data Export:** Download active filtered data feeds into structured JSON payloads with a single click.

---

## 🐋 Docker & Cloud Deployment

### Containerized Environment
Spin up the complete stack out of the box using Docker Compose:
```bash
docker compose up                      # Deploys with default localized SQLite
docker compose --profile mongo up      # Deploys along with a bundled MongoDB instance
```

For custom single-container environments:
```bash
docker build -t geowatch .
docker run -p 8501:8501 --env-file .env -v geowatch-data:/app/data geowatch
```

### Cloud Environments
Bind network hosts for live servers or edge deployments:
```bash
python run.py --host 0.0.0.0 --port 8501
```
A native `Procfile` is pre-configured and included out of the box for PaaS engine platform hosting (e.g., Heroku, Dokku).

---

## 🩺 Automated Feed Health Checks

Keep your collection targets clean without degrading your collection runtime applications. The system leverages `scripts/check-feeds.sh`—a pure Bash + cURL engine requiring **no Python runtime overhead**—to audit URLs listed in `config/sources.yaml` and export a health report to `scripts/feed-health-report.csv`.

- **Automated Schedule:** Runs completely hands-free every Monday via integrated GitHub actions (`.github/workflows/check-feeds.yml`).
- **Pre-Merge Validation:** Fires automatically on any incoming Pull Requests that modify `config/sources.yaml`.

---

## 🛡 Stability & Production Robustness

GeoWatch Pro features built-in defensive coding layers optimized for continuous, 24/7 mission-critical operations:

- **Graceful Error Isolation:** Upstream API network drops (Reddit, YouTube, HN) are intercepted safely and logged instead of interrupting the collector thread.
- **Resource Leak Protection:** Active MongoDB client connections cleanly drop on termination signals or system exits, eliminating orphaned connections.
- **Sandboxed Alerts:** Delivery hooks (Telegram, Email, WhatsApp) are fully decoupled. If one messaging platform encounters an explicit timeout, remaining channels complete their delivery successfully.
- **Config Assertion Safeguards:** Malformed or broken configuration text files present clean, contextual warnings in terminal spaces rather than throwing unhandled stack traces.
