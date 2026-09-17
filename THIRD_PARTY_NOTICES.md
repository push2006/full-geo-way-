# Third-party / design notes

GeoWatch Pro uses selected architectural ideas from the reviewed WorldMonitor and GeoNews projects. It does **not** bundle their full source trees.

- WorldMonitor review influenced the tiered threat-classification approach, diplomacy-signal separation, panel-oriented dashboard thinking, resilience checks, and map concepts.
- GeoNews review influenced near-duplicate headline handling, corroboration counts, multi-source collection flow, and bulk-oriented storage patterns.
- GeoWatch's existing Python/Flask/SQLite/MongoDB architecture remains the primary implementation.

The `core/threat_classifier.py` module contains its own notice describing the relationship to WorldMonitor's AGPL-licensed classifier logic. Review the applicable upstream license before redistributing derivative code.
