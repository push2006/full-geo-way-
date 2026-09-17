# GeoWatch Pro
### Merged from BRICS-- + geonews-main + GeoWatch-Pro. One command, real dashboard.

## Start (one command)

```bash
pip install -r requirements.txt
cp .env.example .env
python run.py serve
```

That's it — one process, one terminal. It collects continuously in the
background (same as `run.py 24`) and serves the live dashboard in the
foreground at http://127.0.0.1:8501. Open that URL, hit refresh whenever
you want the latest — no second terminal needed.

## If you'd rather run collection and viewing separately

```bash
python run.py              # single pass, then exits
python run.py 24            # loops forever, no dashboard
python run.py dashboard     # dashboard only, reads whatever's already collected
```

## Other commands

```bash
python run.py check
python run.py trends
python run.py gnews
python run.py rss --from-sources
python run.py crawl URL --pages 20
python run.py streams
python run.py notify        # send digest + weekly report now
```

## Sources (single file)

All news sources live in **one file**: `config/sources.yaml`

- RSS feeds, pages, and scrape targets
- Set `enabled: false` to skip any source
- No more `sources.csv` or `brics_sources.yaml`

Live video streams stay in `config/streams.yaml` (different purpose).

See `MERGE_NOTES.md` for what came from which of the three original projects.
