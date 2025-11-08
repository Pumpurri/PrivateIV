from portfolio.models import Portfolio
from portfolio.services.snapshot_service import SnapshotService
from django.utils import timezone
from decimal import Decimal

print("=" * 80)
print("TESTING SNAPSHOT SERVICE FIX")
print("=" * 80)

portfolio = Portfolio.objects.get(id=1)
test_date = timezone.now().date()

print(f"\nPortfolio: {portfolio.name}")
print(f"Current Cash Balance: {portfolio.base_currency} {portfolio.cash_balance:,.2f}")

# Test the fixed method
calculated_cash = SnapshotService._get_historical_cash(portfolio, test_date)
print(f"\nCalculated Cash (fixed method): {portfolio.base_currency} {calculated_cash:,.2f}")
print(f"Actual Cash Balance:            {portfolio.base_currency} {portfolio.cash_balance:,.2f}")
print(f"Difference:                     {portfolio.base_currency} {abs(portfolio.cash_balance - calculated_cash):,.2f}")

if abs(portfolio.cash_balance - calculated_cash) < Decimal('0.01'):
    print("\n✅ SUCCESS! Cash calculation is correct!")
else:
    print(f"\n❌ MISMATCH!")

# Create new snapshot
print(f"\nCreating new snapshot for {test_date}...")
snapshot = SnapshotService.create_daily_snapshot(portfolio, test_date)

print(f"\n✅ Snapshot created!")
print(f"  Date:         {snapshot.date}")
print(f"  Total:        {portfolio.base_currency} {snapshot.total_value:,.2f}")
print(f"  Cash:         {portfolio.base_currency} {snapshot.cash_balance:,.2f}")
print(f"  Investment:   {portfolio.base_currency} {snapshot.investment_value:,.2f}")

print(f"\nCurrent Portfolio:")
print(f"  Total:        {portfolio.base_currency} {portfolio.total_value:,.2f}")
print(f"  Cash:         {portfolio.base_currency} {portfolio.cash_balance:,.2f}")
print(f"  Investment:   {portfolio.base_currency} {portfolio.current_investment_value:,.2f}")
