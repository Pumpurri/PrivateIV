#!/usr/bin/env bash
set -euo pipefail

# Run Celery worker with Datadog APM auto-instrumentation via ddtrace-run.
# Usage:
#   DD_SERVICE="TradeSimulator-worker" DD_ENV="Dev" DD_LOGS_INJECTION=true \
#   ./observability/run_apm_celery.sh

if ! command -v ddtrace-run >/dev/null 2>&1; then
  echo "ddtrace-run not found. Install deps: pip install -r requirements.txt" >&2
  exit 1
fi

exec ddtrace-run celery -A TradeSimulator worker -l info

