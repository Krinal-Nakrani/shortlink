#!/usr/bin/env bash
# End-to-end check for ShortLink: shorten a URL, click it 3 times, read the stats.
# Works locally, in Docker Compose and on Kubernetes (change the two URLs).
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
REDIRECT_URL="${REDIRECT_URL:-http://localhost:8001}"
CLICKS=3

echo "1) Creating a short link..."
response=$(curl -fsS -X POST "$API_URL/shorten" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/devops"}')
echo "   $response"
code=$(printf '%s' "$response" | python3 -c 'import sys, json; print(json.load(sys.stdin)["code"])')

echo "2) Clicking the short link $CLICKS times..."
for i in $(seq 1 "$CLICKS"); do
  curl -s -o /dev/null -w "   click $i -> HTTP %{http_code}, redirects to %{redirect_url}\n" "$REDIRECT_URL/$code"
done

echo "3) Waiting for the analytics worker..."
sleep 2

echo "4) Reading the statistics..."
stats=$(curl -fsS "$API_URL/stats/$code")
echo "   $stats"

clicks=$(printf '%s' "$stats" | python3 -c 'import sys, json; print(json.load(sys.stdin)["clicks"])')
if [ "$clicks" -eq "$CLICKS" ]; then
  echo "PASS: $clicks clicks recorded."
else
  echo "FAIL: expected $CLICKS clicks, found $clicks."
  exit 1
fi
