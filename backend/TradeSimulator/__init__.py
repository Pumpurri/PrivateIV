import os
from TradeSimulator.env import env_flag, load_optional_dotenv

load_optional_dotenv()

# Optional Datadog APM integration - enabled by DD_TRACE_ENABLED env var
if env_flag('DD_TRACE_ENABLED', default=False):
    try:
        from ddtrace import patch_all  # type: ignore
        # Auto-instrument Django, DRF, Celery, psycopg2
        patch_all()
    except Exception:
        # ddtrace not installed or failed to init; continue without tracing
        pass

from .celery import app as celery_app

__all__ = ('celery_app',)
