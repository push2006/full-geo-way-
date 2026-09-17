#!/usr/bin/env bash
# Validates every RSS feed URL in config/sources.yaml with a plain HTTP
# HEAD/GET check. Deliberately shell + curl, not Python — this way CI
# can run it in seconds with no dependency install, and you can run it
# yourself with nothing but curl:
#
#   ./scripts/check-feeds.sh
#   ./scripts/check-feeds.sh config/sources.yaml   # explicit path
#
# Writes scripts/feed-health-report.csv and exits non-zero if more than
# FAIL_THRESHOLD percent of feeds are dead, so CI can fail the build.

set -uo pipefail

SOURCES_FILE="${1:-config/sources.yaml}"
REPORT="scripts/feed-health-report.csv"
TIMEOUT=10
FAIL_THRESHOLD=15   # percent

if [ ! -f "$SOURCES_FILE" ]; then
    echo "Sources file not found: $SOURCES_FILE" >&2
    exit 2
fi

# Pull "name: ..." / "url: ..." pairs out of the YAML without needing a
# YAML parser installed — sources.yaml is a flat list of mappings, so a
# line-oriented read is reliable enough for this.
mapfile -t URLS < <(grep -oP '(?<=url:\s).*' "$SOURCES_FILE" | tr -d '"'"'"'' | sed 's/[[:space:]]*$//')
mapfile -t NAMES < <(grep -oP '(?<=name:\s).*' "$SOURCES_FILE" | tr -d '"'"'"'' | sed 's/[[:space:]]*$//')

total=${#URLS[@]}
if [ "$total" -eq 0 ]; then
    echo "No feed URLs found in $SOURCES_FILE" >&2
    exit 2
fi

echo "Checking $total feeds (timeout ${TIMEOUT}s each)..."
echo "name,url,status,http_code" > "$REPORT"

ok=0
dead=0

for i in "${!URLS[@]}"; do
    url="${URLS[$i]}"
    name="${NAMES[$i]:-unknown}"
    code=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time "$TIMEOUT" -A "GeoWatch-FeedCheck/1.0" -L "$url" 2>/dev/null)
    if [ -z "$code" ] || [ "$code" = "000" ]; then
        status="DEAD"; dead=$((dead+1))
    elif [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then
        status="OK"; ok=$((ok+1))
    else
        status="FAIL"; dead=$((dead+1))
    fi
    printf '%s,%s,%s,%s\n' "\"$name\"" "\"$url\"" "$status" "$code" >> "$REPORT"
    printf '\r  %d/%d checked (%d ok, %d dead)' "$((i+1))" "$total" "$ok" "$dead"
done
echo

pct_dead=$(( dead * 100 / total ))
echo
echo "Result: $ok ok, $dead dead/failing out of $total ($pct_dead% dead)"
echo "Full report: $REPORT"

if [ "$pct_dead" -gt "$FAIL_THRESHOLD" ]; then
    echo "FAIL: more than ${FAIL_THRESHOLD}% of feeds are dead — check $REPORT" >&2
    exit 1
fi
exit 0
