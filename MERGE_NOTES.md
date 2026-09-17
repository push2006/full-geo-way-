# Merge notes — BRICS-- + geonews-main + GeoWatch-Pro → one project

All three feed the same running app now — not "one base project with the
others attached as extras." GeoWatch-Pro's `core/` package (the newest,
cleanest of the three) is the foundation everything else got rewired
onto, because it's the only one of the three with a storage layer
(`core/storage.py`) that isn't hard-locked to one specific database. Every
feature below runs against that same storage, so a story collected by
any collector shows up in the same dashboard, the same digest, the same
weekly report.

## Every feature, and where it lives now

| Feature | Originally from | Now at | Status |
|---|---|---|---|
| Crawler, RSS, trends, dashboard, SQLite/Mongo storage, Tor | GeoWatch-Pro | `core/` | unchanged |
| Email / Telegram / WhatsApp digest + critical alerts | BRICS-- `reports/` | `notifications/` | ported, rewritten onto `core.storage` |
| Weekly top-stories + category-count report | geonews-main `reports/weekly_report.py` | `notifications/weekly_report.py` | **ported for real** — added `weekly_top_articles()` / `category_counts()` to `core/storage.py` since geonews's version queried its own Mongo-only schema (`country` isn't a tracked field here, so top-countries was dropped, not faked) |
| Google News keyword collector | geonews-main `collectors/gnews_search.py` | `core/gnews_search.py` | ported, writes through `core.storage.upsert_site()` like the RSS/crawl collectors instead of geonews's Mongo-only bulk insert |
| OFAC sanctions-list screening | geonews-main `collectors/sanctions.py` | `core/sanctions.py` | ported as-is (no schema dependency to rewrite) |
| Live YouTube stream list for the dashboard | BRICS-- `video.py` + `config/streams.yaml` | `core/video.py` + `config/streams.yaml` | ported as-is |
| Source/feed list | all three had overlapping CSV/YAML lists | `config/sources.csv` (+ `config/brics_sources.yaml`, identical between GeoWatch-Pro and BRICS--, kept) | merged — geonews's feeds not already covered got appended; most were already duplicates of `brics_sources.yaml` |
| Google Sheets export | geonews-main `apps_script/` | `extras/apps_script/` | kept as reference — it posts to a Sheets webhook, not this app's DB, so there's no meaningful "port," just copy |

## How to run each piece

```bash
python run.py              # one full pass: trends + RSS + check
python run.py gnews        # Google News keyword collector (needs ENABLE_GNEWS=true, pip install gnews)
python run.py streams      # list configured YouTube streams
python run.py notify       # send digest + weekly report now, over whichever ENABLE_* channels are on
python run.py 24           # 24/7 loop
```

Everything new (`gnews`, notifications, weekly report, sanctions
screening) is **off by default** via `ENABLE_*` flags in `.env` — copy
`.env.example` first. Nothing sends a message or hits an external API
until you flip its flag.

## What's genuinely still separate (and why)

- **`extras/apps_script/`** — a Google Apps Script that lives in a Sheet,
  not in this codebase. There's nothing to "merge" past copying the
  files; you deploy it in Google's editor if you want it.
- **`notifications/critical_alert.py`** calls GeoWatch-Pro's own
  `core.classifier.is_critical()`, not BRICS's original — BRICS's
  version was tied to its own article-scoring pipeline, which doesn't
  exist here. `CRITICAL_KEYWORDS` in `.env.example` is unused now that
  this is wired to the real classifier; left in only in case you'd
  rather swap back to a plain keyword match.

## Collaboration ("add collab")

It's a git repo (`git log` shows the merge history). To work on it with
someone else:

```bash
git remote add origin <your-repo-url>
git push -u origin main
# collaborators:
git clone <your-repo-url>
git checkout -b feature/whatever
git push -u origin feature/whatever   # then open a PR into main
```

`.gitignore` excludes `.env`, `data/`, `logs/`, `__pycache__/` so nobody
commits secrets or the local DB. Adding collaborators as repo members
happens on whichever host you push to (GitHub/GitLab/etc.) — that step
isn't something that happens from inside the repo itself.

## Trends — expanded beyond Reddit/HN

`core/trends.py` now pulls from six platforms, all free/public endpoints
(no paid API keys):

| Platform | How | Default |
|---|---|---|
| Reddit | public `.json` endpoint per subreddit | on |
| Hacker News | public Firebase API | on |
| YouTube | per-channel RSS feed (`YOUTUBE_CHANNEL_IDS`) | on |
| Mastodon | public `/api/v1/trends/statuses` (most instances allow anonymous reads) | on |
| Telegram | scrapes the public `t.me/s/<channel>` preview page — no bot token needed, but HTML-scraped so more fragile | off |
| Twitter/X | via a Nitter mirror's RSS feed — X has had no free public API since 2023, so this is the only no-cost path; only as reliable as whichever `NITTER_INSTANCE` you point at (self-host one if you depend on this) | off |

All controlled by `ENABLE_*_TRENDS` flags in `.env.example`. `python run.py trends` runs all enabled platforms in one pass; results land in `core.storage` the same way as every other collector.

## Facebook / Instagram — different shape than the rest

These two don't fit the "free public endpoint" pattern the six platforms
above use. Meta's Graph API requires a token tied to a specific
Page/Instagram Business account you administer — there's no anonymous
"trending on Facebook" or "Instagram explore" feed to poll, by design.
So `fetch_all_facebook_trends()` / `fetch_all_instagram_trends()` only
ever return posts from Pages/accounts *you* own and have generated a
token for (`FACEBOOK_PAGE_ACCESS_TOKEN` via
https://developers.facebook.com/tools/explorer). Both off by default;
there was no scraping fallback built for either, since evading Meta's
login wall and anti-bot measures would be a ToS violation, not a
missing feature.

## Dashboard — rebuilt, not patched

The dashboard that shipped in the original GeoWatch-Pro (`static/geowatch.html`)
turned out to be a **standalone demo**: a hardcoded source list baked into
the page, plus two calls straight to `api.anthropic.com` for AI summaries.
It never read `data/geowatch.db` — opening it showed sample content, not
anything the pipeline actually collected.

Fixed properly, not patched:
- **`core/webapp.py`** — a small Flask app with `/api/sites`, `/api/content`,
  `/api/changes`, `/api/weekly`, `/api/streams`, `/api/summary`, all reading
  live from `core.storage` (works on both SQLite and MongoDB backends)
- **`static/dashboard.html`** — new page, fetches those endpoints, renders
  sources/content/changes/breakdown/weekly-report/streams as tabs. No AI
  calls anywhere in it.
- **`static/geowatch.html`** — old AI-summary demo removed; the file now
  just redirects to `dashboard.html` so any bookmark/link to it still lands
  somewhere useful.
- **`python run.py dashboard`** — new subcommand, starts the Flask server
  (`DASHBOARD_HOST`/`DASHBOARD_PORT`, or `HOST`/`PORT` in `.env`, default
  `127.0.0.1:8501`).

Run `python run.py` first to populate the database, then `python run.py
dashboard` in a second terminal and open the printed URL.

## One command, not two — `python run.py serve`

`run.py 24` (collector loop) and `run.py dashboard` (viewer) were two
separate processes in two terminals. `python run.py serve` runs both in
**one process**: the 24/7 collector loop on a background thread, the
dashboard server on the main thread. One command, one terminal, one
thing to start and stop.

`run.py 24` and `run.py dashboard` are both still there separately, for
when you actually want them apart (e.g. a cloud worker process
collecting while a different web process serves the dashboard — see the
`Procfile`, which now just runs `serve` as the single web process).
