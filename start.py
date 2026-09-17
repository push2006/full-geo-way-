#!/usr/bin/env python3
"""
GeoWatch Pro — ONE START (local + cloud) — NO Streamlit

  python start.py

Runs continuous updates every 30 seconds:
  trends + all GeoNews/BRICS RSS + content check
"""
import os
import sys
import time
import signal
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL", "30"))
running = True


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def stop(*_args):
    global running
    running = False
    log("Stopping...")


def bootstrap():
    try:
        from core.storage import init_db, get_session, get_enabled_sites
        from run import do_import
        init_db()
        session = get_session()
        sites = get_enabled_sites(session)
        n = len(list(sites)) if sites is not None else 0
        if hasattr(session, "close"):
            try:
                session.close()
            except Exception:
                pass
        if n < 5:
            log("Importing sources...")
            do_import()
        else:
            log(f"Sources already loaded ({n})")
    except Exception as e:
        log(f"Bootstrap: {e}")


def run_one_cycle():
    from run import do_trends, do_rss, do_check
    do_trends(quiet=True)
    do_rss(all_merged=True, quiet=True)
    changed, errors = do_check(quiet=True)
    return changed, errors


def main():
    global running
    running = True
    signal.signal(signal.SIGINT, stop)
    try:
        signal.signal(signal.SIGTERM, stop)
    except Exception:
        pass

    print("=" * 56, flush=True)
    print("  GeoWatch Pro — 24/7 (no Streamlit)", flush=True)
    print(f"  Update every {UPDATE_INTERVAL}s  |  Ctrl+C to stop", flush=True)
    print("=" * 56, flush=True)

    bootstrap()
    log("First cycle...")
    try:
        c, e = run_one_cycle()
        log(f"Cycle #1 — changed={c} errors={e}")
    except Exception as ex:
        log(f"Cycle error: {ex}")

    cycle = 1
    while running:
        for _ in range(UPDATE_INTERVAL):
            if not running:
                break
            time.sleep(1)
        if not running:
            break
        cycle += 1
        try:
            c, e = run_one_cycle()
            log(f"Cycle #{cycle} — changed={c} errors={e}")
        except Exception as ex:
            log(f"Cycle error: {ex}")

    log("Shutdown complete")


if __name__ == "__main__":
    main()
