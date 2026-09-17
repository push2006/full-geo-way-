# Release checklist

- [x] Python AST/syntax validation
- [x] Dashboard JavaScript syntax validation with Node.js
- [x] Required-file validation
- [x] No `.env` secret file in release
- [x] No `__pycache__` in release
- [x] No `.bak` backup files in release
- [x] SQLite schema migration for fingerprint/corroboration
- [x] Mongo indexes for URL/fingerprint/score/time
- [x] Cross-collector integration pipeline
- [x] Near-duplicate + corroboration handling
- [x] Tiered threat classification
- [x] Diplomacy signal detection
- [x] Safer notification HTML escaping
- [x] Keyless OpenStreetMap tile endpoint
- [x] Bounded API pagination
- [x] Health endpoint

Runtime note: the build environment used for this release did not have every package from `requirements.txt` installed and had no external package-network access, so live Flask/RSS/network collection tests could not be executed here. The release validator and local SQLite/integration tests were run successfully.
