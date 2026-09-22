"""Build a single, fictional portfolio for a disposable local walkthrough."""

from datetime import date
from io import StringIO
import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import override_settings

from portfolio.models import FXRate, Portfolio
from portfolio.services.performance_service import PerformanceCalculator
from stocks.models import Stock
from users.models import CustomUser


class Command(BaseCommand):
    help = "Create a fictional login and one populated portfolio in a fresh disposable database."

    EMAIL = "showcase@example.invalid"

    def add_arguments(self, parser):
        parser.add_argument("--confirm-disposable", action="store_true")
        parser.add_argument("--days", type=int, default=120)
        parser.add_argument("--transactions", type=int, default=70)

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Showcase generation requires DEBUG=True.")
        if not options["confirm_disposable"]:
            raise CommandError("Pass --confirm-disposable only for a fresh, disposable local database.")
        if CustomUser.objects.exists() or Portfolio.all_objects.exists() or Stock.objects.exists() or FXRate.objects.exists():
            raise CommandError("The database is not empty; use a fresh disposable database instead.")

        password = os.getenv("SHOWCASE_PASSWORD", "")
        if not password:
            raise CommandError("Set SHOWCASE_PASSWORD for the fictional local account.")

        with transaction.atomic():
            # The normal signup signal adds a starter portfolio; this fixture needs
            # just the populated one. Other portfolio signals remain enabled.
            with override_settings(DISABLE_SIGNALS=True):
                CustomUser.objects.create_user(
                    email=self.EMAIL,
                    password=password,
                    full_name="Showcase Investor",
                    dob=date(1998, 1, 1),
                )

            call_command(
                "create_test_portfolio",
                username=self.EMAIL,
                portfolio_name="Investment Portfolio Simulator demo",
                days=options["days"],
                transactions=options["transactions"],
                confirm_disposable=True,
                stdout=StringIO(),
            )

            portfolio = Portfolio.objects.get(user__email=self.EMAIL)
            portfolio.is_default = True
            portfolio.description = "Fictional local portfolio with generated trades and market history."
            portfolio.save(update_fields=["is_default", "description"])
            portfolio.performance.time_weighted_return = (
                PerformanceCalculator.calculate_all_time_weighted_return(portfolio)
            )
            portfolio.performance.save(update_fields=["time_weighted_return"])

        self.stdout.write(self.style.SUCCESS(f"Showcase login: {self.EMAIL}"))
        self.stdout.write("All holdings, prices, and trades are generated local data.")
