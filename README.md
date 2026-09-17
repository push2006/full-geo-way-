# GeoWatch Pro

One command. Continuous collection + live dashboard.

## Start

```bash
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Open **http://127.0.0.1:8501**

That's the only command you need.

## Sources

All sources are in **one file**: `config/sources.yaml`

- Set `enabled: false` to skip any source
- Live video streams: `config/streams.yaml`

## Optional

```bash
# Cloud / bind all interfaces
python run.py --host 0.0.0.0 --port 8501
```
