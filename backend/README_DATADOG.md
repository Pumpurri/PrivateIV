# Datadog APM Integration

## Overview
Optional Datadog APM integration for the TradeSimulator app, providing distributed tracing, performance monitoring, and observability.

## Quick Setup

### 1. Environment Configuration
Set the following in your `.env` file:
```bash
DD_TRACE_ENABLED=true          # Enable/disable tracing
DD_API_KEY=your_api_key_here   # Your Datadog API key
DD_SERVICE=tradesimulator      # Service name
DD_ENV=development             # Environment (dev/staging/prod)
DD_VERSION=1.0.0              # App version
DD_AGENT_HOST=localhost        # Agent host
```

### 2. Start Datadog Agent (Local Development)
```bash
# Start the Datadog agent container
docker-compose -f docker-compose.datadog.yml up -d

# Verify agent is running
docker logs datadog-agent
```

### 3. Run Your Application with Tracing

Option A — Recommended (ddtrace-run wrapper):
```bash
# Django (auto-instrument)
DD_SERVICE="TradeSimulator" DD_ENV="Dev" DD_LOGS_INJECTION=true \
  ./observability/run_apm_django.sh

# Celery worker (auto-instrument)
DD_SERVICE="TradeSimulator-worker" DD_ENV="Dev" DD_LOGS_INJECTION=true \
  ./observability/run_apm_celery.sh
```

Option B — Built-in toggle in code:
```bash
# Set env flag (from your .env) and run normally
DD_TRACE_ENABLED=true python manage.py runserver
DD_TRACE_ENABLED=true celery -A TradeSimulator worker --loglevel=INFO
```

## What Gets Instrumented

**Automatic instrumentation** (via `patch_all()`):
- Django views and middleware
- Django REST Framework views
- PostgreSQL database queries (psycopg2)
- Celery tasks and workflows
- HTTP requests made by the application

**Custom spans** added for critical business flows:
- `transaction.create` - Stock buy/sell transactions
- Additional spans can be added as needed

## Viewing Traces

1. Log into your Datadog account
2. Navigate to APM → Traces
3. Filter by service: `tradesimulator`
4. Explore traces for:
   - API endpoint performance
   - Database query patterns
   - Celery task execution
   - Transaction processing flows

## Key Benefits

- **Performance Monitoring**: See exactly where time is spent in requests
- **Database Insights**: Identify slow queries and N+1 problems
- **Error Tracking**: Automatic error tagging and alerting
- **Dependency Mapping**: Visual service topology
- **Custom Business Metrics**: Track transaction volumes, portfolio updates, etc.

## Development Tips

- Prefer `ddtrace-run` during development; it’s simple and reliable.
- If using the built-in toggle, set `DD_TRACE_ENABLED=true` in your `.env`.
- Use custom spans sparingly around critical business logic
- Agent runs on ports 8126 (traces) and 8125 (metrics)

### Agent connectivity notes
- App on host + Agent in Docker: defaults work (tracer sends to `localhost:8126`).
- App in Docker + Agent on host: set `DD_AGENT_HOST=host.docker.internal` in the app env.

## Security Notes

- Keep API keys out of source control. Prefer `.env` and secret stores.
- Traces may contain sensitive data - review before production
- Consider data scrubbing for PII in production environments

## Next Steps

- Add custom metrics for business KPIs
- Set up alerts for error rates/latency
- Create dashboards for portfolio performance
- Configure log injection for correlated logging
