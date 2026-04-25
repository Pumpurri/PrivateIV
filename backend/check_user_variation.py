#!/usr/bin/env python
"""
Local diagnostic script for inspecting a user's portfolio variation via Django ORM.

Usage:
    backend/venv/bin/python backend/check_user_variation.py --email user@example.com
"""
import argparse
import os
import sys
from decimal import Decimal

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "TradeSimulator.settings")
django.setup()

from portfolio.models import DailyPortfolioSnapshot, Portfolio
from portfolio.models.transaction import Transaction
from users.models import CustomUser


def _money(value):
    return Decimal(value or "0.00").quantize(Decimal("0.01"))


def _print_header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _get_portfolio(email, portfolio_id=None):
    user = CustomUser.objects.filter(email__iexact=email).first()
    if not user:
        raise ValueError(f"User with email {email} not found.")

    portfolios = Portfolio.objects.filter(user=user).order_by("-is_default", "id")
    if portfolio_id is not None:
        portfolio = portfolios.filter(id=portfolio_id).first()
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found for {email}.")
        return user, portfolio

    portfolio = portfolios.first()
    if portfolio is None:
        raise ValueError(f"No portfolios found for {email}.")
    return user, portfolio


def analyze_daily_variation(email, portfolio_id=None):
    user, portfolio = _get_portfolio(email=email, portfolio_id=portfolio_id)

    _print_header("USER INFORMATION")
    print(f"User ID: {user.id}")
    print(f"Email: {user.email}")
    print(f"Name: {user.full_name}")

    _print_header("PORTFOLIO INFORMATION")
    print(f"Portfolio ID: {portfolio.id}")
    print(f"Name: {portfolio.name}")
    print(f"Base Currency: {portfolio.base_currency}")
    print(f"Cash Balance: {portfolio.base_currency} {_money(portfolio.cash_balance):,.2f}")
    print(f"USD Cash Balance: USD {_money(portfolio.cash_balance_usd):,.2f}")
    print(f"Current Investment Value: {portfolio.base_currency} {_money(portfolio.current_investment_value):,.2f}")
    print(f"Current Total Value: {portfolio.base_currency} {_money(portfolio.total_value):,.2f}")

    holdings = portfolio.holdings.select_related("stock").filter(is_active=True, quantity__gt=0).order_by("stock__symbol")
    _print_header("CURRENT HOLDINGS")
    if not holdings:
        print("No active holdings found")
    else:
        for holding in holdings:
            stock = holding.stock
            market_value_native = Decimal(holding.quantity) * Decimal(stock.current_price or "0.00")
            cost_basis = Decimal(holding.quantity) * Decimal(holding.average_purchase_price or "0.00")
            pnl = market_value_native - cost_basis
            pnl_pct = (pnl / cost_basis * Decimal("100")) if cost_basis > 0 else Decimal("0.00")
            print(f"\n{stock.symbol} - {stock.name}")
            print(f"  Currency: {stock.currency}")
            print(f"  Quantity: {holding.quantity}")
            print(f"  Current Price: {stock.currency} {_money(stock.current_price):,.2f}")
            print(f"  Market Value: {stock.currency} {_money(market_value_native):,.2f}")
            print(f"  Cost Basis: {stock.currency} {_money(cost_basis):,.2f}")
            print(f"  P&L: {stock.currency} {_money(pnl):,.2f} ({pnl_pct.quantize(Decimal('0.01')):.2f}%)")

    snapshots = list(
        DailyPortfolioSnapshot.objects
        .filter(portfolio=portfolio)
        .order_by("-date")[:10]
    )
    _print_header("DAILY PORTFOLIO SNAPSHOTS (LAST 10)")
    if not snapshots:
        print("No snapshots found")
    else:
        print(f"{'Date':<12} {'Total Value':>15} {'Cash':>15} {'Investment':>15}")
        print("-" * 60)
        for snap in snapshots:
            print(
                f"{snap.date} "
                f"{_money(snap.total_value):>15,.2f} "
                f"{_money(snap.cash_balance):>15,.2f} "
                f"{_money(snap.investment_value):>15,.2f}"
            )

        if len(snapshots) > 1:
            today_snap = snapshots[0]
            previous_snap = snapshots[1]
            daily_change = _money(today_snap.total_value) - _money(previous_snap.total_value)
            daily_change_pct = (
                (daily_change / _money(previous_snap.total_value) * Decimal("100"))
                if _money(previous_snap.total_value) > 0
                else Decimal("0.00")
            )

            _print_header("DAILY VARIATION")
            print(f"Previous ({previous_snap.date}): {portfolio.base_currency} {_money(previous_snap.total_value):,.2f}")
            print(f"Latest ({today_snap.date}): {portfolio.base_currency} {_money(today_snap.total_value):,.2f}")
            print(f"Change: {portfolio.base_currency} {_money(daily_change):,.2f}")
            print(f"Change %: {daily_change_pct.quantize(Decimal('0.01')):.2f}%")

            txs = (
                Transaction.all_objects
                .filter(portfolio=portfolio, timestamp__date__in=[today_snap.date, previous_snap.date])
                .select_related("stock")
                .order_by("-timestamp")
            )
            if txs:
                _print_header("TRANSACTIONS ON SNAPSHOT DATES")
                for tx in txs:
                    symbol = tx.stock.symbol if tx.stock else "N/A"
                    amount = _money(tx.amount)
                    print(f"[{tx.timestamp}] {tx.transaction_type:<10} {symbol:<8} amount={amount:,.2f}")

    perf = getattr(portfolio, "performance", None)
    _print_header("PORTFOLIO PERFORMANCE")
    if perf is None:
        print("No performance record found")
    else:
        print(f"Total Deposits: {portfolio.base_currency} {_money(perf.total_deposits):,.2f}")
        print(f"Total Withdrawals: {portfolio.base_currency} {_money(perf.total_withdrawals):,.2f}")
        print(f"Time-Weighted Return: {Decimal(perf.time_weighted_return or '0.0000'):.4f}")
        print(f"Last Updated: {perf.last_updated}")


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect portfolio daily variation for a specific user.")
    parser.add_argument("--email", required=True, help="User email to inspect.")
    parser.add_argument("--portfolio-id", type=int, help="Optional portfolio ID for users with multiple portfolios.")
    return parser.parse_args()


if __name__ == "__main__":
    options = parse_args()
    analyze_daily_variation(email=options.email, portfolio_id=options.portfolio_id)
