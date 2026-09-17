# GeoWatch Pro — Cross-Connected Architecture

```text
RSS / GNews / Trends / Crawler
             |
             v
     core.integration.py
       |     |      |
       |     |      +--> diplomacy signal
       |     +---------> threat level/category
       +---------------> category + fingerprint + corroboration
             |
             v
     core.storage.py
       |             |
       v             v
    SQLite         MongoDB
       |             |
       +-------> Flask API -------> dashboard.html
                         |
             +-----------+-----------+
             |           |           |
          Feed       Threats     Intelligence
             |           |           |
             +-------> Map / Weekly / Export
```

The central integration pipeline is deliberately small. Collectors produce raw items; `core.integration.process_batch()` normalizes and enriches them before storage. This avoids separate collectors producing incompatible category/threat fields.
