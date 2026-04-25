#!/usr/bin/env python
"""
Quick local transaction dump for a user portfolio.

Usage:
    backend/venv/bin/python backend/check_transactions.py --email user@example.com [--portfolio-id 2]
"""
import argparse
import os
import sys
from decimal import Decimal

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "TradeSimulator.settings")
django.setup()

from django.contrib.auth import get_user_model
from portfolio.models import Holding, Portfolio, Transaction

User = get_user_model()


def parse_args():
    parser = argparse.ArgumentParser(description="Dump portfolio transactions for a user.")
    parser.add_argument("--email", required=True, help="User email to inspect.")
    parser.add_argument("--portfolio-id", type=int, help="Optional portfolio ID.")
    return parser.parse_args()


def _money(value):
    return Decimal(value or "0.00").quantize(Decimal("0.01"))


def main():
    args = parse_args()
    user = User.objects.filter(email__iexact=args.email).first()

    if not user:
        print(f"User with email {args.email} not found")
        return

    print(f"User found: {user.email} (ID: {user.id})")
    portfolios = Portfolio.objects.filter(user=user).order_by("-is_default", "id")
    portfolio = portfolios.filter(id=args.portfolio_id).first() if args.portfolio_id else portfolios.first()
    if portfolio is None:
        print("No matching portfolio found")
        return

    print(f"\nPortfolio: {portfolio.name} (ID: {portfolio.id})")
    print(f"Cash Balance: {portfolio.cash_balance}")
    print(f"Total Value: {portfolio.total_value}")
    print("\nTransactions:")
    print("-" * 120)
    print(f'{"Date":<20} | {"Type":10} | {"Symbol":6} | {"Quantity":>8} | {"Price":>12} | {"Total":>14}')
    print("-" * 120)
    txs = Transaction.all_objects.filter(portfolio=portfolio).select_related("stock").order_by("-timestamp")
    for tx in txs:
        price = _money(tx.executed_price)
        qty = tx.quantity or 0
        total = _money(qty * price)
        symbol = tx.stock.symbol if tx.stock else "N/A"
        print(f"{str(tx.timestamp):<20} | {tx.transaction_type:10} | {symbol:6} | {qty:8} | ${price:11.2f} | ${total:13.2f}")
    print("-" * 120)
    print(f"Total transactions: {txs.count()}")

    print("\nCurrent Holdings:")
    print("-" * 100)
    print(f'{"Symbol":6} | {"Quantity":>8} | {"Avg Price":>12} | {"Current Price":>14} | {"Market Value":>14}')
    print("-" * 100)
    holdings = Holding.objects.filter(portfolio=portfolio, quantity__gt=0).select_related("stock")
    for holding in holdings:
        print(
            f"{holding.stock.symbol:6} | {holding.quantity:8} | "
            f"${_money(holding.average_purchase_price):11.2f} | "
            f"${_money(holding.stock.current_price):13.2f} | "
            f"${_money(holding.current_value):13.2f}"
        )
    print("-" * 100)

    print("\n=== PORTFOLIO MATH ===")
    total_spent = sum(
        _money(tx.executed_price) * Decimal(tx.quantity or 0)
        for tx in txs if tx.transaction_type == Transaction.TransactionType.BUY
    )
    total_holdings_value = sum((_money(holding.current_value) for holding in holdings), start=Decimal("0.00"))

    print(f"Total spent on stocks: ${_money(total_spent):.2f}")
    print(f"Current holdings value: ${_money(total_holdings_value):.2f}")
    print(f"Cash balance: ${_money(portfolio.cash_balance):.2f}")
    print(f"Expected total: ${_money(total_holdings_value + portfolio.cash_balance):.2f}")
    print(f"Reported total: ${_money(portfolio.total_value):.2f}")
    print(f"Unrealized P&L: ${_money(total_holdings_value - total_spent):.2f}")

    deposits = Transaction.all_objects.filter(portfolio=portfolio, transaction_type=Transaction.TransactionType.DEPOSIT)
    withdrawals = Transaction.all_objects.filter(portfolio=portfolio, transaction_type=Transaction.TransactionType.WITHDRAWAL)
    total_deposits = sum((_money(tx.amount) for tx in deposits), start=Decimal("0.00"))
    total_withdrawals = sum((_money(tx.amount) for tx in withdrawals), start=Decimal("0.00"))
    print(f"Total deposits: ${_money(total_deposits):.2f}")
    print(f"Total withdrawals: ${_money(total_withdrawals):.2f}")
    print(f"Expected cash: ${_money(total_deposits - total_withdrawals - total_spent):.2f}")


if __name__ == "__main__":
    main()
