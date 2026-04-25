import io

import pytest
from django.core.management import call_command

from portfolio.management.commands.ops_smoke_test import Command
from portfolio.models import BenchmarkPrice


@pytest.mark.django_db
def test_ops_smoke_test_runs_end_to_end_with_stubbed_ops_checks(monkeypatch):
    monkeypatch.setattr(Command, "_check_worker", lambda self: {"responders": ["worker@smoke"]})
    monkeypatch.setattr(
        Command,
        "_check_beat",
        lambda self: {
            "scheduler": "django_celery_beat.schedulers:DatabaseScheduler",
            "enabled_tasks": [
                "portfolio.tasks.create_daily_snapshots",
                "portfolio.tasks.fx_ingest_latest_auto",
                "portfolio.tasks.update_all_time_weighted_returns",
            ],
        },
    )

    stdout = io.StringIO()
    call_command("ops_smoke_test", benchmark_mode="stub", stdout=stdout)

    output = stdout.getvalue()
    assert "[ok] healthz:" in output
    assert "[ok] auth_trading:" in output
    assert "[ok] snapshots:" in output
    assert "[ok] benchmark_ingest:" in output
    assert "Operational smoke test passed." in output
    assert BenchmarkPrice.objects.filter(series__code="sp500").exists()
