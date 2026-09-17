"""GeoWatch release sanity checks. Run: python scripts/validate_release.py"""
from pathlib import Path
import ast
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "run.py", "start.py", "requirements.txt", "core/webapp.py",
    "core/rss.py", "core/dedupe.py", "core/storage.py",
    "static/dashboard.html", "config/sources.yaml", "core/integration.py",
]

for rel in REQUIRED:
    p = ROOT / rel
    if not p.exists():
        raise SystemExit(f"MISSING: {rel}")

for p in ROOT.rglob("*.py"):
    if "__pycache__" in p.parts:
        continue
    ast.parse(p.read_text(encoding="utf-8"), filename=str(p))

dashboard = (ROOT / "static/dashboard.html").read_text(encoding="utf-8")
for marker in ("tile.openstreetmap.org", "/api/content", "/api/geo", "function ensureMap"):
    if marker not in dashboard:
        raise SystemExit(f"DASHBOARD MARKER MISSING: {marker}")

for p in ROOT.rglob(".env"):
    raise SystemExit(f"SECRET FILE IN RELEASE: {p}")
for p in ROOT.rglob("*.bak"):
    raise SystemExit(f"BACKUP FILE IN RELEASE: {p}")
for p in ROOT.rglob("__pycache__"):
    raise SystemExit(f"PYTHON CACHE IN RELEASE: {p}")

print("GeoWatch release validation: PASS")
print(f"Python files checked: {len(list(ROOT.rglob('*.py')))}")
print(f"Dashboard lines: {len(dashboard.splitlines())}")
