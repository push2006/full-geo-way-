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

---

## Later cleanup (single entry + single sources)

- **One sources file:** `config/sources.yaml` only (`sources.csv` and `brics_sources.yaml` removed).
- **One command:** `python run.py` runs collection + dashboard. `start.py` is a thin wrapper.
- **Python 3.12:** `datetime.utcnow()` replaced with `datetime.now(timezone.utc)`.
- **Dependencies:** requirements.txt bumped to current stable floors (Flask 3.1+, SQLAlchemy 2.0.36+, httpx 0.28+, etc.).

## Sources expanded from worldmonitor's validated feed report

Pulled `scripts/rss-feeds-report.csv` from koala73/worldmonitor (a much
larger, separate project — different stack entirely, TypeScript/React,
not something to code-merge). That CSV is their own pre-validated feed
list: 420 feeds, each checked with a live status (`OK`/`STALE`/`DEAD`/
`EMPTY`) and a last-successful-fetch date.

Filtered to the **188** that were `OK` *and* fit a geopolitics monitor —
kept politics, regional news (US/Europe/Asia/Africa/LatAm/Middle East/
Gulf), government, policy, think tanks, crisis, security, economic,
central banks, commodities, energy, markets, finance, analysis,
institutional, regulation. Dropped their startup/VC/crypto/podcast/
github/"inspiring" categories — not relevant here. Deduped by URL
against what was already in `config/sources.yaml` (83 → 271 total).

**Not pulled in**, and worth knowing about if you want to go further:
- Their **Country Instability Index** (31 Tier-1 countries, live scoring
  methodology) — a real feature, but a significant build (needs its own
  scoring methodology, not just a config addition). Their methodology is
  documented at `docs/methodology/` in that repo if you want to build a
  version of it here later.
- Their **map/globe visualization** (globe.gl + deck.gl) — again a
  different stack; `core/webapp.py`'s `/api/geo` + the dashboard's
  Leaflet map tab is our equivalent, just far simpler.

## Beyond Python: Docker, Bash, GitHub Actions (YAML), Make

The project was Python-only. Added a few pieces in other languages/tools
that make it more deployable and self-maintaining, not just more code:

| File | Language | What it does |
|---|---|---|
| `Dockerfile` | Docker | Builds a container image; includes a healthcheck hitting `/api/summary` |
| `docker-compose.yml` | YAML | One command to run it, with an optional `--profile mongo` for a bundled MongoDB instead of SQLite |
| `.dockerignore` | — | Keeps `.env`, `data/`, `.git` out of the image |
| `scripts/check-feeds.sh` | Bash | Validates every feed URL in `config/sources.yaml` via `curl`, writes a CSV report, exits non-zero if >15% are dead. No Python dependency install needed to run it — tested it directly: correctly parses all 271 URLs from the YAML and correctly detects a genuinely dead domain (`000` HTTP code) vs. a live one |
| `.github/workflows/check-feeds.yml` | GitHub Actions (YAML) | Runs `check-feeds.sh` automatically every Monday, on-demand, and on any PR touching `config/sources.yaml` — surfaces dead feeds before they silently start producing empty results |
| `install.sh` | Bash | One-line local setup: venv, deps, `.env` — `./install.sh` then `python run.py` |
| `Makefile` | Make | Shortcuts — `make run`, `make dashboard`, `make docker-up`, `make check-feeds`, etc. Verified all targets resolve correctly with `make -n` |

Tested what could be tested in this environment: bash syntax-checked
(`bash -n`), the Makefile's targets resolve via `make -n`, and
`check-feeds.sh`'s YAML-parsing + dead-domain detection were run for
real against a live feed and a nonexistent one. Docker itself wasn't
buildable here (no Docker daemon in this environment) — worth a test
build on your machine before relying on it.

## Real threat classifier, ported from worldmonitor

`notifications/critical_alert.py` used a flat substring `is_critical()`
before — any headline containing "invasion" or "tariff" fired the same
way. Replaced with a proper port of worldmonitor's
`shared/threat-keyword-classifier.ts`:

- **`core/threat_classifier.py`** — tiered (critical/high/medium/low/info),
  word-boundary regex on ambiguous short words ("war", "ban", "vote"
  don't fire on substrings inside other words), an exclusion list
  ("Israel strikes **deal**" ≠ a military strike), and compound
  escalation (a strike/attack/missile verb near a flashpoint country
  name bumps HIGH to CRITICAL even when the words aren't adjacent —
  "strikes by US and Israel on Iran").
- **`core/diplomacy_signals.py`** — ported from
  `shared/diplomacy-keywords.json`: flags headlines pairing a flashpoint
  country with diplomacy language ("Iran talks", "Gaza ceasefire") —
  the de-escalation counterpart to the threat classifier, not
  previously a distinct signal in this project at all.
- **New API routes**: `/api/threats` (tiered classification of recent
  content, `?level=critical` to filter) and `/api/diplomacy`.
- **`critical_alert.py`** now uses `classify_by_keyword()` instead of
  the old flat check, and tags each alert with its threat category.

Tested for real, not just read: ran both against real headline examples
including the exact false-positive case the exclusion list exists for
("Israel strikes deal with tech giant" → correctly `info`, not a
military alert), confirmed the compound-escalation behavior matches the
original TS source exactly, and seeded real DB rows to confirm
`/api/threats` and `/api/diplomacy` classify actual stored content
end-to-end, not just empty responses.

Ported by hand from TypeScript to Python — same keyword tables, same
tier logic, same regex rules — not a reinterpretation. Source:
`shared/threat-keyword-classifier.ts` and `shared/diplomacy-keywords.json`
in koala73/worldmonitor (AGPL-3.0). Worth checking that license's terms
if you plan to redistribute this project, since the classifier logic
(not just the RSS feed list, which is just data) was taken from an
AGPL-licensed file.

## Trade chokepoints — new map layer

Pulled the 13 canonical global trade chokepoints (Suez, Hormuz, Malacca,
Taiwan Strait, Panama, Bosporus, and 7 more) from worldmonitor's
`src/config/chokepoint-registry.ts` — coordinates and names only, not
their routing/energy-shock-model logic, which is a much bigger feature
tied to data this project doesn't have (EIA baselines, PortWatch transit
feeds).

- **`config/chokepoints.yaml`** — the 13 entries, with aliases for
  matching ("Bab el-Mandeb" also matches "bab-el-mandeb")
- **`core/chokepoints.py`** — `match_chokepoints(text)` tags article
  text against them
- **`/api/chokepoints`** — returns all 13 with a live `recent_mentions`
  count from your actual collected content. Tested end-to-end: seeded a
  Taiwan Strait headline, confirmed it counted correctly and only against
  that one chokepoint.

These are fixed geography, unlike your source pins (which only have a
`country` guessed from feed metadata) — a firmer anchor for the
dashboard's map tab if you want to plot them there. Not yet wired into
`static/dashboard.html`'s Map tab itself, just the API — that's a
frontend change I didn't make since it touches a file you may have
customized since the last update.

## Bug fix: `python run.py` (the documented "one correct way") was silently broken

Found and fixed while doing a real integration pass, not just per-file
checks:

**The bug**: `do_serve()` (what plain `python run.py` runs by default)
starts the 24/7 collector loop on a background thread via
`do_24_7()`. But `do_24_7()` called `signal.signal()` to catch Ctrl+C
— and `signal.signal()` only works on the **main thread** in Python.
Called from a background thread, it raises `ValueError` immediately.
Since nothing caught that exception, the background thread died
silently right after printing "① Initial import..." — the dashboard
would still come up and look fine, but **no collection ever ran**, and
there was nothing in the output telling you why.

Confirmed this for real, three ways:
1. Isolated repro of the exact threading pattern → `ValueError: signal only works in main thread of the main interpreter`
2. Fixed the code, reran the same repro → no crash
3. Ran the actual `do_serve()` from the real, fixed `run.py` as a subprocess for 5 seconds → confirmed in the log that it got past initial import, started fetching trends, **and** the dashboard answered `200` on `/api/summary` at the same time — both halves running together, not one silently dead

**The fix**: register the signal handlers once, on the main thread,
inside `do_serve()` itself — before the background thread starts. Pass
`register_signals=False` to `do_24_7()` when it's launched as that
background thread, so it doesn't try (and fail) to register its own.
`do_24_7()` still registers signals normally when it's the actual
main-thread entrypoint (i.e. `python run.py 24`, no dashboard).

Also fixed a second issue in the same function: the old `_handle_signal`
only ever set a flag (`_running = False`) and never actually terminated
the process. `do_24_7`'s own loop checks that flag and exits cleanly —
but Flask's blocking dashboard server, running on the main thread in
`do_serve()` mode, never checked it at all. Practical effect: Ctrl+C
would stop the collector but leave the dashboard (and the whole
process) running forever, needing a `kill -9` to actually stop.
`_handle_signal` now calls `sys.exit(0)` after setting the flag, which
propagates cleanly through whichever blocking call the main thread is
in — Flask's server or `do_24_7`'s own sleep — and exits without a
traceback (`SystemExit`, unlike an uncaught `KeyboardInterrupt`, exits
silently).

This affected every entrypoint that runs `do_serve()` — `python run.py`
directly, `start.py` (Docker `CMD`), and the cloud `Procfile` — since
all three call the same `main()`.
