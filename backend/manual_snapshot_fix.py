#!/usr/bin/env python
"""
Manual verification script for snapshot generation against a live portfolio.

This is intentionally not a pytest test module.
"""
import os
import sys
from decimal import Decimal

import django
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TradeSimulator.settings')
django.setup()

from portfolio.models import Portfolio
from portfolio.services.snapshot_service import SnapshotService

print("=" * 80)
print("TESTING SNAPSHOT SERVICE FIX")
print("=" * 80)

portfolio = Portfolio.objects.get(id=1)
test_date = timezone.now().date()

print(f"\nPortfolio: {portfolio.name}")
print(f"Current Cash Balance (from Portfolio table): {portfolio.base_currency} {portfolio.cash_balance:,.2f}")
print(f"Test Date: {test_date}")

print(f"\n{'=' * 80}")
print("TESTING _get_historical_cash() METHOD")
print(f"{'=' * 80}")

calculated_cash = SnapshotService._get_historical_cash(portfolio, test_date)
print(f"\nCalculated Cash (from fixed method): {portfolio.base_currency} {calculated_cash:,.2f}")
print(f"Actual Cash Balance (from DB):       {portfolio.base_currency} {portfolio.cash_balance:,.2f}")
print(f"Difference:                           {portfolio.base_currency} {(portfolio.cash_balance - calculated_cash):,.2f}")

if abs(portfolio.cash_balance - calculated_cash) < Decimal('0.01'):
    print("\nSUCCESS! Calculated cash matches actual cash balance!")
else:
    print(f"\nMISMATCH! Difference of {portfolio.base_currency} {(portfolio.cash_balance - calculated_cash):,.2f}")

print(f"\n{'=' * 80}")
print("CREATING NEW SNAPSHOT WITH FIXED METHOD")
print(f"{'=' * 80}")

try:
    snapshot = SnapshotService.create_daily_snapshot(portfolio, test_date)
    print("\nSnapshot created successfully!")
    print("\nSnapshot Details:")
    print(f"  Date:            {snapshot.date}")
    print(f"  Total Value:     {portfolio.base_currency} {snapshot.total_value:,.2f}")
    print(f"  Cash Balance:    {portfolio.base_currency} {snapshot.cash_balance:,.2f}")
    print(f"  Investment:      {portfolio.base_currency} {snapshot.investment_value:,.2f}")

    current_total = portfolio.total_value
    print("\nComparison with Current Portfolio:")
    print(f"  Current Total:   {portfolio.base_currency} {current_total:,.2f}")
    print(f"  Snapshot Total:  {portfolio.base_currency} {snapshot.total_value:,.2f}")
    print(f"  Difference:      {portfolio.base_currency} {(current_total - snapshot.total_value):,.2f}")

    if abs(current_total - snapshot.total_value) < Decimal('100'):
        print("\nSnapshot total value is close to current portfolio value!")
    else:
        print("\nSnapshot differs significantly from current value")
except Exception as exc:
    print(f"\nError creating snapshot: {exc}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
