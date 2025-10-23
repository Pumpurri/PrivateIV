#!/usr/bin/env bash
set -euo pipefail

# Run Django with Datadog APM auto-instrumentation via ddtrace-run.
# Usage:
#   DD_SERVICE="TradeSimulator" DD_ENV="Dev" DD_LOGS_INJECTION=true \
#   ./observability/run_apm_django.sh

if ! command -v ddtrace-run >/dev/null 2>&1; then
  echo "ddtrace-run not found. Install deps: pip install -r requirements.txt" >&2
  exit 1
fi

# Default bind if not provided
HOST_PORT=${HOST_PORT:-0.0.0.0:8000}

exec ddtrace-run python manage.py runserver "$HOST_PORT"

