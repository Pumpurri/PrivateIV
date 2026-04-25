from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
import io
import os
from unittest.mock import patch
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from TradeSimulator.celery import app as celery_app
from portfolio.models import BenchmarkPrice, DailyPortfolioSnapshot, Portfolio, Transaction
from portfolio.tasks import create_daily_snapshots
from stocks.models import Stock
from users.models import CustomUser


class Command(BaseCommand):
    help = (
        "Run an operational smoke test covering deploy health, migrations, Celery readiness, "
        "snapshot generation, benchmark ingest, and an end-to-end auth + trading flow."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--benchmark-mode",
            choices=("stub", "live", "skip"),
            default="stub",
            help="Use stubbed ingest (default), hit the live provider, or skip benchmark ingest.",
        )
        parser.add_argument(
            "--benchmark-days",
            type=int,
            default=5,
            help="Number of history days to request during benchmark ingest.",
        )
        parser.add_argument(
            "--skip-worker-check",
            action="store_true",
            help="Skip the Celery worker ping check.",
        )
        parser.add_argument(
            "--skip-beat-check",
            action="store_true",
            help="Skip the Celery beat schedule check.",
        )
        parser.add_argument(
            "--keep-artifacts",
            action="store_true",
            help="Keep the disposable smoke-test user/portfolio/stock for inspection.",
        )

    def handle(self, *args, **options):
        artifacts = {}
        results = []

        try:
            results.append(("healthz", self._check_healthz()))
            results.append(("migrations", self._check_migrations()))

            if options["skip_worker_check"]:
                results.append(("worker", {"skipped": True}))
            else:
                results.append(("worker", self._check_worker()))

            if options["skip_beat_check"]:
                results.append(("beat", {"skipped": True}))
            else:
                results.append(("beat", self._check_beat()))

            artifacts = self._run_auth_and_trading_flow()
            results.append(("auth_trading", artifacts["summary"]))

            results.append(("snapshots", self._check_snapshot_generation(artifacts["portfolio"])))

            benchmark_mode = options["benchmark_mode"]
            if benchmark_mode != "skip":
                results.append((
                    "benchmark_ingest",
                    self._check_benchmark_ingest(
                        mode=benchmark_mode,
                        days=max(2, int(options["benchmark_days"])),
                    ),
                ))
            else:
                results.append(("benchmark_ingest", {"skipped": True}))
        finally:
            if artifacts and not options["keep_artifacts"]:
                self._cleanup_artifacts(artifacts)

        for name, payload in results:
            self.stdout.write(self.style.SUCCESS(f"[ok] {name}: {payload}"))

        self.stdout.write(self.style.SUCCESS("Operational smoke test passed."))

    def _check_healthz(self):
        response = Client().get(reverse("healthz"))
        if response.status_code != 200:
            raise CommandError(f"healthz failed with {response.status_code}: {response.content!r}")

        payload = response.json()
        if payload.get("status") != "ok" or payload.get("database") != "ok":
            raise CommandError(f"healthz returned degraded payload: {payload}")
        return payload

    def _check_migrations(self):
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        if plan:
            pending = [f"{migration.app_label}.{migration.name}" for migration, _ in plan]
            raise CommandError(f"Unapplied migrations detected: {pending}")
        return {"pending_steps": 0}

    def _check_worker(self):
        if not settings.CELERY_BROKER_URL:
            raise CommandError("CELERY_BROKER_URL is not configured.")

        try:
            inspect = celery_app.control.inspect(timeout=2)
            ping = inspect.ping() if inspect is not None else None
        except Exception as exc:
            raise CommandError(f"Celery worker ping failed: {exc}") from exc

        if not ping:
            raise CommandError("No Celery workers responded to ping.")
        return {"responders": sorted(ping.keys())}

    def _check_beat(self):
        if not apps.is_installed("django_celery_beat"):
            raise CommandError("django_celery_beat is not installed in this environment.")

        sync_output = io.StringIO()
        call_command("sync_periodic_tasks", stdout=sync_output)

        from django_celery_beat.models import PeriodicTask

        required_tasks = {
            "portfolio.tasks.create_daily_snapshots",
            "portfolio.tasks.fx_ingest_latest_auto",
            "portfolio.tasks.update_all_time_weighted_returns",
        }
        enabled_tasks = set(
            PeriodicTask.objects.filter(enabled=True, task__in=required_tasks).values_list("task", flat=True)
        )
        missing = sorted(required_tasks - enabled_tasks)
        if missing:
            raise CommandError(f"Missing enabled periodic tasks: {missing}")

        return {
            "scheduler": settings.CELERY_BEAT_SCHEDULER,
            "enabled_tasks": sorted(enabled_tasks),
        }

    def _run_auth_and_trading_flow(self):
        client = APIClient()
        token = uuid4().hex[:8]
        email = f"smoke-{token}@example.com"
        password = "SmokePass123!"
        user_payload = {
            "email": email,
            "password": password,
            "full_name": "Smoke User",
            "dob": date(1995, 1, 1).isoformat(),
        }

        register_response = client.post(reverse("register"), user_payload, format="json")
        self._assert_status(register_response.status_code, 201, "register")

        profile_response = client.get(reverse("user-profile"))
        self._assert_status(profile_response.status_code, 200, "profile after register")

        logout_response = client.post(reverse("logout"), format="json")
        self._assert_status(logout_response.status_code, 200, "logout")

        login_response = client.post(
            reverse("login"),
            {"email": email, "password": password},
            format="json",
        )
        self._assert_status(login_response.status_code, 200, "login")

        portfolio_response = client.post(
            reverse("portfolio-list"),
            {
                "name": "Smoke Portfolio",
                "description": "Disposable operational smoke portfolio",
                "initial_deposit_pen": "1000.00",
            },
            format="json",
        )
        self._assert_status(portfolio_response.status_code, 201, "portfolio create")
        portfolio_id = portfolio_response.json()["id"]

        stock = Stock.objects.create(
            symbol=f"SMK{token[:4]}",
            name="Smoke Asset",
            currency="PEN",
            current_price=Decimal("100.00"),
        )

        transaction_response = client.post(
            reverse("transaction-create"),
            {
                "portfolio_id": portfolio_id,
                "transaction_type": Transaction.TransactionType.BUY,
                "stock": stock.id,
                "quantity": 2,
                "cash_currency": "PEN",
            },
            format="json",
        )
        self._assert_status(transaction_response.status_code, 201, "buy transaction")

        holdings_response = client.get(reverse("portfolio-holdings", kwargs={"portfolio_id": portfolio_id}))
        self._assert_status(holdings_response.status_code, 200, "portfolio holdings")
        holdings_payload = holdings_response.json()
        if len(holdings_payload["results"]) != 1:
            raise CommandError(f"Expected 1 active holding, got {holdings_payload['results']}")

        transactions_response = client.get(
            reverse("transaction-list"),
            {"portfolio": portfolio_id},
        )
        self._assert_status(transactions_response.status_code, 200, "transaction list")
        transaction_count = transactions_response.json()["count"]
        if transaction_count < 2:
            raise CommandError(f"Expected at least 2 transactions for smoke portfolio, got {transaction_count}")

        dashboard_response = client.get(reverse("dashboard"))
        self._assert_status(dashboard_response.status_code, 200, "dashboard")
        dashboard_payload = dashboard_response.json()
        portfolio_ids = {item["id"] for item in dashboard_payload["portfolios"]}
        if portfolio_id not in portfolio_ids:
            raise CommandError("Smoke portfolio is missing from dashboard response.")

        user = CustomUser.objects.get(email=email)
        portfolio = Portfolio.objects.get(pk=portfolio_id, user=user)
        buy_transaction = Transaction.objects.filter(
            portfolio=portfolio,
            transaction_type=Transaction.TransactionType.BUY,
        ).latest("timestamp")

        return {
            "user": user,
            "portfolio": portfolio,
            "stock": stock,
            "summary": {
                "user_id": user.id,
                "portfolio_id": portfolio.id,
                "stock_symbol": stock.symbol,
                "transaction_id": buy_transaction.id,
                "dashboard_portfolios": len(dashboard_payload["portfolios"]),
            },
        }

    def _check_snapshot_generation(self, portfolio):
        today = date.today()
        create_daily_snapshots()
        snapshot = DailyPortfolioSnapshot.objects.filter(portfolio=portfolio, date=today).first()
        if snapshot is None:
            raise CommandError(f"No snapshot created for portfolio {portfolio.id} on {today}.")

        return {
            "portfolio_id": portfolio.id,
            "date": snapshot.date.isoformat(),
            "total_value": f"{snapshot.total_value:.2f}",
        }

    def _check_benchmark_ingest(self, *, mode, days):
        from portfolio.management.commands.ingest_benchmark_history import Command as IngestCommand

        with self._temporary_env("FMP_API", "smoke-test-key" if mode == "stub" else None):
            if mode == "stub":
                end_date = date.today()
                payload = [
                    {"date": (end_date - timedelta(days=1)).isoformat(), "close": "100.00"},
                    {"date": end_date.isoformat(), "close": "101.00"},
                ]
                with patch.object(IngestCommand, "_fetch_fmp_history", return_value=payload):
                    call_command("ingest_benchmark_history", days=days, benchmarks=["sp500"])
            elif mode == "live":
                if not (os.getenv("FMP_API") or "").strip():
                    raise CommandError("FMP_API is required for --benchmark-mode live.")
                call_command("ingest_benchmark_history", days=days, benchmarks=["sp500"])
            else:
                raise CommandError(f"Unsupported benchmark mode: {mode}")

        rows = BenchmarkPrice.objects.filter(series__code="sp500").count()
        latest = BenchmarkPrice.objects.filter(series__code="sp500").order_by("-date").first()
        if rows < 2 or latest is None:
            raise CommandError("Benchmark ingest did not create enough rows for sp500.")

        return {
            "mode": mode,
            "code": "sp500",
            "rows": rows,
            "latest_date": latest.date.isoformat(),
        }

    def _cleanup_artifacts(self, artifacts):
        user = artifacts.get("user")
        stock = artifacts.get("stock")

        if user is not None:
            CustomUser.objects.filter(pk=user.pk).delete()
        if stock is not None:
            Stock.objects.filter(pk=stock.pk).delete()

    @contextmanager
    def _temporary_env(self, key, default_stub_value=None):
        previous = os.getenv(key)
        try:
            if previous is None and default_stub_value is not None:
                os.environ[key] = default_stub_value
            yield
        finally:
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    def _assert_status(self, actual, expected, label):
        if actual != expected:
            raise CommandError(f"{label} failed with status {actual}; expected {expected}.")
