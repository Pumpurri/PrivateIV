# Optional observability

Tracing is **off by default**. Ordinary Django, Celery, and test runs do not need a Datadog account or agent. The [tracing helper](portfolio/services/tracing.py) imports `ddtrace` only when `DD_TRACE_ENABLED=true`.

## Enable local tracing

Install `backend/requirements.txt`, set a local Datadog API key outside Git, and start the agent only if you want to send traces to Datadog:

```bash
cd backend
export DD_API_KEY=your-local-datadog-key
docker compose -f docker-compose.datadog.yml up -d
```

The compose file enables APM and collects container logs. Review that collection and Datadog billing/privacy settings before using it with any real data. Never commit the API key. To trace Django and Celery, run their wrappers from `backend/` in separate terminals:

```bash
DD_SERVICE=bolsasim-api DD_ENV=development ./observability/run_apm_django.sh
```

```bash
DD_SERVICE=bolsasim-worker DD_ENV=development ./observability/run_apm_celery.sh
```

The wrappers set `DD_TRACE_ENABLED=true` and use `ddtrace-run` for automatic instrumentation. Setting `DD_TRACE_ENABLED=true` without a wrapper enables only the app's custom spans, not automatic framework instrumentation.

Custom spans cover `transaction.execute`, `transaction.process`, trade and cash actions, and `snapshot.daily` in [transaction settlement](portfolio/services/transaction_service.py) and [snapshot generation](portfolio/services/snapshot_service.py). Do not put user identifiers, credentials, or financial details in span tags or logs.

Stop the local agent with `docker compose -f docker-compose.datadog.yml down` when finished. This documentation does not require starting the paused Railway services.
