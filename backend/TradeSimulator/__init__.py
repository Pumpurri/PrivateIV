from .celery import app as celery_app
import os

# Ensure .env is loaded before checking Datadog flags.
# Django imports this package (__init__) before TradeSimulator.settings,
# so load_dotenv here to make DD_* envs available early.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Optional Datadog APM integration - enabled by DD_TRACE_ENABLED env var
if os.getenv('DD_TRACE_ENABLED', 'false').lower() == 'true':
    try:
        from ddtrace import patch_all  # type: ignore
        # Auto-instrument Django, DRF, Celery, psycopg2
        patch_all()
    except Exception:
        # ddtrace not installed or failed to init; continue without tracing
        pass

__all__ = ('celery_app',)
