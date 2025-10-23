Minimal Datadog APM (opt‑in)

Prereqs
- Datadog account + API key
- Docker (to run local Agent)

1) Install tracer
- Add to your environment (already in requirements.txt):
  pip install ddtrace

2) Run Datadog Agent locally (receives traces)
- Replace <your_key> with your Datadog API key
  docker run -d --name dd-agent \
    -e DD_API_KEY=<your_key> \
    -e DD_APM_ENABLED=true \
    -p 8126:8126 \
    gcr.io/datadoghq/agent:latest

3) Run Django with tracing
- Use ddtrace-run wrapper and set env vars:
  DD_SERVICE="TradeSimulator" \
  DD_ENV="Dev" \
  DD_LOGS_INJECTION=true \
  ./observability/run_apm_django.sh

4) (Optional) Celery with tracing
  DD_SERVICE="TradeSimulator-worker" \
  DD_ENV="Dev" \
  DD_LOGS_INJECTION=true \
  ./observability/run_apm_celery.sh

Notes
- This repo includes light custom spans around transaction execution and daily snapshots.
- If ddtrace is not installed, spans no‑op and tests are unaffected.
- Avoid tagging PII in spans.

Useful envs
- DD_LOGS_INJECTION=true (correlate logs ↔ traces)
- DD_TRACE_SAMPLE_RATE=1.0 (dev only)
- DD_AGENT_HOST=host.docker.internal (app runs in Docker, Agent on host)
