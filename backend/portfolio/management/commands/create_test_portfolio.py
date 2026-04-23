"""
Create a large local portfolio dataset for UI behavior testing.

Usage:
    python manage.py create_test_portfolio --username=sjjs0805@gmail.com
"""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import math
import random
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from portfolio.models import (
    DailyPortfolioSnapshot,
    FXRate,
    Portfolio,
    PortfolioPerformance,
    RealizedPNL,
    Transaction,
)
from portfolio.models.holding_snapshot import HoldingSnapshot
from portfolio.services.snapshot_service import SnapshotService
from portfolio.services.transaction_service import TransactionService
from stocks.models import HistoricalStockPrice, Stock
from users.models import CustomUser


class Command(BaseCommand):
    help = "Create a heavy deterministic test portfolio with transactions and EOD snapshots."

    STOCKS = [
        ("AAPL", "Apple Inc.", "USD", Decimal("184.25"), Decimal("0.00055"), Decimal("7.5")),
        ("MSFT", "Microsoft Corporation", "USD", Decimal("412.30"), Decimal("0.00048"), Decimal("6.2")),
        ("GOOGL", "Alphabet Inc.", "USD", Decimal("147.80"), Decimal("0.00038"), Decimal("8.8")),
        ("AMZN", "Amazon.com Inc.", "USD", Decimal("178.40"), Decimal("0.00042"), Decimal("9.5")),
        ("NVDA", "NVIDIA Corporation", "USD", Decimal("875.00"), Decimal("0.00115"), Decimal("18.0")),
        ("META", "Meta Platforms Inc.", "USD", Decimal("486.10"), Decimal("0.00062"), Decimal("10.0")),
        ("TSLA", "Tesla Inc.", "USD", Decimal("242.70"), Decimal("-0.00018"), Decimal("17.0")),
        ("JPM", "JPMorgan Chase & Co.", "USD", Decimal("198.90"), Decimal("0.00025"), Decimal("4.5")),
        ("V", "Visa Inc.", "USD", Decimal("281.60"), Decimal("0.00036"), Decimal("4.2")),
        ("NFLX", "Netflix Inc.", "USD", Decimal("605.25"), Decimal("0.00052"), Decimal("11.0")),
        ("BAP", "Credicorp Ltd.", "USD", Decimal("166.50"), Decimal("0.00022"), Decimal("5.8")),
        ("IFS", "Intercorp Financial Services", "USD", Decimal("26.40"), Decimal("0.00015"), Decimal("6.0")),
        ("BVN", "Compania de Minas Buenaventura", "USD", Decimal("16.75"), Decimal("0.00012"), Decimal("13.0")),
        ("SPY", "SPDR S&P 500 ETF Trust", "USD", Decimal("521.20"), Decimal("0.00032"), Decimal("3.4")),
        ("EPU", "iShares MSCI Peru ETF", "USD", Decimal("42.35"), Decimal("0.00010"), Decimal("6.8")),
    ]

    def add_arguments(self, parser):
        parser.add_argument("--username", default="sjjs0805@gmail.com", help="User email to populate.")
        parser.add_argument("--portfolio-name", default="UI Stress Portfolio", help="Portfolio name.")
        parser.add_argument("--days", type=int, default=900, help="Number of historical days.")
        parser.add_argument("--transactions", type=int, default=850, help="Target transaction count.")
        parser.add_argument("--seed", type=int, default=805, help="Random seed for deterministic data.")
        parser.add_argument(
            "--no-reset",
            action="store_true",
            help="Do not remove existing portfolios with the same name for this user.",
        )

    def handle(self, *args, **options):
        self.random = random.Random(options["seed"])
        email = options["username"].lower().strip()
        days = max(options["days"], 30)
        target_transactions = max(options["transactions"], 50)
        portfolio_name = options["portfolio_name"]
        start_date = timezone.now() - timedelta(days=days)
        end_date = timezone.now().date()

        user = CustomUser.objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError(f"User with email {email} not found.")

        self.stdout.write(f"Using database alias: default")
        self.stdout.write(f"Populating user: {user.email}")

        if not options["no_reset"]:
            stale = Portfolio.all_objects.filter(user=user, name=portfolio_name)
            stale_ids = list(stale.values_list("id", flat=True))
            if stale_ids:
                self.stdout.write(f"Removing existing '{portfolio_name}' portfolios: {stale_ids}")
                HoldingSnapshot.objects.filter(portfolio_id__in=stale_ids).delete()
                DailyPortfolioSnapshot.all_objects.filter(portfolio_id__in=stale_ids).delete()
                RealizedPNL.objects.filter(portfolio_id__in=stale_ids).delete()
                Transaction.all_objects.filter(portfolio_id__in=stale_ids).delete()
                PortfolioPerformance.objects.filter(portfolio_id__in=stale_ids).delete()
                Portfolio.all_objects.filter(id__in=stale_ids).delete()

        stocks = self._ensure_market_data(start_date.date(), end_date)

        with transaction.atomic():
            portfolio = Portfolio.objects.create(
                user=user,
                name=portfolio_name,
                description="Large deterministic local dataset for testing dashboard, balances, holdings, transactions, and realized P&L UI behavior.",
                base_currency="PEN",
                reporting_currency="PEN",
                cash_balance=Decimal("0.00"),
                cash_balance_usd=Decimal("0.00"),
            )
            Portfolio.all_objects.filter(pk=portfolio.pk).update(created_at=start_date)

        self._execute_transaction(
            portfolio,
            "DEPOSIT",
            timestamp=start_date,
            amount=Decimal("850000.00"),
            cash_currency="PEN",
        )
        self._execute_transaction(
            portfolio,
            "DEPOSIT",
            timestamp=start_date + timedelta(hours=3),
            amount=Decimal("25000.00"),
            cash_currency="USD",
        )

        created_transactions = 2
        current_dt = start_date + timedelta(days=2)
        step = max(1, days / max(target_transactions - 2, 1))

        while created_transactions < target_transactions and current_dt.date() <= end_date:
            stock = self.random.choice(stocks)
            self._set_stock_price_for_date(stock, current_dt.date())
            action = self._choose_action(portfolio, created_transactions)

            try:
                if action == "BUY":
                    created_transactions += self._create_buy(portfolio, stock, current_dt)
                elif action == "SELL":
                    created_transactions += self._create_sell(portfolio, current_dt)
                elif action == "DEPOSIT":
                    amount = Decimal(self.random.randrange(2500, 35000)).quantize(Decimal("0.01"))
                    currency = "USD" if self.random.random() < 0.20 else "PEN"
                    self._execute_transaction(portfolio, "DEPOSIT", current_dt, amount=amount, cash_currency=currency)
                    created_transactions += 1
                elif action == "WITHDRAWAL":
                    created_transactions += self._create_withdrawal(portfolio, current_dt)
                elif action == "CONVERT":
                    created_transactions += self._create_conversion(portfolio, current_dt)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Skipped {action} on {current_dt.date()}: {exc}"))

            current_dt += timedelta(days=step + self.random.uniform(-0.35, 0.65))

        self._set_latest_stock_prices(stocks, end_date)
        portfolio.refresh_from_db()

        self.stdout.write("Generating daily snapshots and holding snapshots...")
        DailyPortfolioSnapshot.all_objects.filter(portfolio=portfolio).delete()
        HoldingSnapshot.objects.filter(portfolio=portfolio).delete()

        snapshot_count = 0
        snapshot_date = start_date.date()
        while snapshot_date <= end_date:
            SnapshotService.create_daily_snapshot(portfolio, snapshot_date)
            snapshot_count += 1
            if snapshot_count % 100 == 0:
                self.stdout.write(f"  snapshots: {snapshot_count}")
            snapshot_date += timedelta(days=1)

        portfolio.refresh_from_db()
        txn_count = Transaction.all_objects.filter(portfolio=portfolio).count()
        holding_snapshot_count = HoldingSnapshot.objects.filter(portfolio=portfolio).count()
        realized_count = RealizedPNL.objects.filter(portfolio=portfolio).count()
        active_holding_count = portfolio.holdings.filter(is_active=True).count()

        self.stdout.write(self.style.SUCCESS("Created UI stress portfolio."))
        self.stdout.write(f"Portfolio ID: {portfolio.id}")
        self.stdout.write(f"Transactions: {txn_count}")
        self.stdout.write(f"Daily snapshots: {snapshot_count}")
        self.stdout.write(f"Holding snapshots: {holding_snapshot_count}")
        self.stdout.write(f"Realized P&L rows: {realized_count}")
        self.stdout.write(f"Active holdings: {active_holding_count}")
        self.stdout.write(f"Cash PEN: {portfolio.cash_balance:,.2f}")
        self.stdout.write(f"Cash USD: {portfolio.cash_balance_usd:,.2f}")
        self.stdout.write(f"Investment value: {portfolio.current_investment_value:,.2f}")
        self.stdout.write(f"Total value: {portfolio.total_value:,.2f}")

    def _choose_action(self, portfolio, created_transactions):
        if created_transactions % 31 == 0:
            return "DEPOSIT"
        if created_transactions % 47 == 0:
            return "CONVERT"
        if created_transactions % 67 == 0:
            return "WITHDRAWAL"
        if portfolio.holdings.filter(is_active=True, quantity__gt=0).exists():
            return self.random.choices(
                ["BUY", "SELL", "DEPOSIT", "WITHDRAWAL"],
                weights=[58, 28, 9, 5],
                k=1,
            )[0]
        return "BUY"

    def _ensure_market_data(self, start_date, end_date):
        self.stdout.write("Ensuring FX rates and historical prices...")
        self._ensure_fx_rates(start_date, end_date)

        stocks = []
        for index, (symbol, name, currency, base_price, drift, volatility) in enumerate(self.STOCKS):
            price = self._price_for_offset(base_price, drift, volatility, 0, index)
            stock, _ = Stock.objects.update_or_create(
                symbol=symbol,
                defaults={
                    "name": name,
                    "currency": currency,
                    "current_price": price,
                    "previous_close": price,
                    "previous_close_date": end_date - timedelta(days=1),
                    "is_active": True,
                },
            )
            stocks.append(stock)

            current = start_date
            offset = 0
            while current <= end_date:
                HistoricalStockPrice.objects.update_or_create(
                    stock=stock,
                    date=current,
                    defaults={"price": self._price_for_offset(base_price, drift, volatility, offset, index)},
                )
                current += timedelta(days=1)
                offset += 1

        self.stdout.write(f"Prepared {len(stocks)} stocks across {(end_date - start_date).days + 1} days.")
        return stocks

    def _ensure_fx_rates(self, start_date, end_date):
        current = start_date
        offset = 0
        while current <= end_date:
            mid = (Decimal("3.70") + Decimal(str(math.sin(offset / 41) * 0.055))).quantize(Decimal("0.000001"))
            rates = {
                "compra": (mid - Decimal("0.012000")).quantize(Decimal("0.000001")),
                "venta": (mid + Decimal("0.012000")).quantize(Decimal("0.000001")),
                "mid": mid,
            }
            for session in ("cierre", "intraday"):
                for rate_type, rate in rates.items():
                    FXRate.objects.update_or_create(
                        date=current,
                        base_currency="PEN",
                        quote_currency="USD",
                        rate_type=rate_type,
                        session=session,
                        defaults={
                            "rate": rate,
                            "provider": "local-seed",
                            "source_series": "UISTRESS",
                            "notes": "Generated local UI stress-test FX rate.",
                        },
                    )
            current += timedelta(days=1)
            offset += 1

    def _price_for_offset(self, base_price, drift, volatility, offset, stock_index):
        cycle = Decimal(str(math.sin((offset + stock_index * 11) / 23) * float(volatility)))
        longer_cycle = Decimal(str(math.cos((offset + stock_index * 7) / 67) * float(volatility / 2)))
        trend = Decimal(offset) * drift * base_price
        price = base_price + trend + cycle + longer_cycle
        return max(price, Decimal("1.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _set_stock_price_for_date(self, stock, snapshot_date):
        historical = HistoricalStockPrice.objects.filter(stock=stock, date__lte=snapshot_date).order_by("-date").first()
        if historical:
            stock.current_price = historical.price
            stock.previous_close = historical.price
            stock.previous_close_date = historical.date
            stock.save(update_fields=["current_price", "previous_close", "previous_close_date", "last_updated"])

    def _set_latest_stock_prices(self, stocks, end_date):
        for stock in stocks:
            self._set_stock_price_for_date(stock, end_date)

    def _create_buy(self, portfolio, stock, timestamp):
        price = Decimal(stock.current_price or "1.00")
        fx_rate = FXRate.objects.filter(
            date__lte=timestamp.date(),
            base_currency="PEN",
            quote_currency="USD",
            rate_type="venta",
        ).order_by("-date").values_list("rate", flat=True).first() or Decimal("3.72")
        max_quantity = max(1, int((portfolio.cash_balance * Decimal("0.018")) / (price * Decimal(fx_rate))))
        quantity = self.random.randint(1, min(max_quantity + 1, 45))
        self._execute_transaction(portfolio, "BUY", timestamp, stock=stock, quantity=quantity)
        return 1

    def _create_sell(self, portfolio, timestamp):
        holdings = list(portfolio.holdings.select_related("stock").filter(is_active=True, quantity__gt=0))
        if not holdings:
            return 0
        holding = self.random.choice(holdings)
        self._set_stock_price_for_date(holding.stock, timestamp.date())
        sell_max = max(1, min(holding.quantity, math.ceil(holding.quantity * 0.55)))
        quantity = self.random.randint(1, sell_max)
        self._execute_transaction(portfolio, "SELL", timestamp, stock=holding.stock, quantity=quantity)
        return 1

    def _create_withdrawal(self, portfolio, timestamp):
        portfolio.refresh_from_db()
        if portfolio.cash_balance < Decimal("30000.00"):
            return 0
        amount = Decimal(self.random.randrange(1000, min(25000, int(portfolio.cash_balance - Decimal("10000.00")))))
        self._execute_transaction(portfolio, "WITHDRAWAL", timestamp, amount=amount, cash_currency="PEN")
        return 1

    def _create_conversion(self, portfolio, timestamp):
        portfolio.refresh_from_db()
        if portfolio.cash_balance < Decimal("25000.00"):
            return 0
        amount = Decimal(self.random.randrange(1000, min(20000, int(portfolio.cash_balance - Decimal("10000.00")))))
        self._execute_transaction(
            portfolio,
            "CONVERT",
            timestamp,
            amount=amount,
            cash_currency="PEN",
            counter_currency="USD",
        )
        return 1

    def _execute_transaction(
        self,
        portfolio,
        transaction_type,
        timestamp,
        *,
        amount=None,
        stock=None,
        quantity=None,
        cash_currency=None,
        counter_currency=None,
    ):
        transaction_data = {
            "portfolio": portfolio,
            "transaction_type": transaction_type,
            "idempotency_key": uuid.uuid4(),
        }
        if amount is not None:
            transaction_data["amount"] = Decimal(amount).quantize(Decimal("0.01"))
        if stock is not None:
            transaction_data["stock"] = stock
        if quantity is not None:
            transaction_data["quantity"] = int(quantity)
        if cash_currency is not None:
            transaction_data["cash_currency"] = cash_currency
        if counter_currency is not None:
            transaction_data["counter_currency"] = counter_currency

        txn = TransactionService.execute_transaction(transaction_data)
        Transaction.all_objects.filter(pk=txn.pk).update(timestamp=timestamp)
        if transaction_type == "SELL":
            buy_timestamp = (
                Transaction.all_objects
                .filter(
                    portfolio=portfolio,
                    stock=stock,
                    transaction_type="BUY",
                    timestamp__lte=timestamp,
                )
                .order_by("timestamp")
                .values_list("timestamp", flat=True)
                .first()
            )
            RealizedPNL.objects.filter(transaction=txn).update(
                realized_at=timestamp,
                acquisition_date=buy_timestamp or timestamp,
            )
        return txn
