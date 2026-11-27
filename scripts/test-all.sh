#!/usr/bin/env bash
# Runs the same checks as the CI pipeline, for all three services.
set -euo pipefail
cd "$(dirname "$0")/.."

ruff check services

for s in url-api redirect-service analytics-worker; do
  echo "=== $s ==="
  (cd "services/$s" && pytest -q)
done

echo "All checks passed."
