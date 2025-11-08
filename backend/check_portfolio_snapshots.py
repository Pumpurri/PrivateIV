import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TradeSimulator.settings')
django.setup()

from portfolio.models import PortfolioSnapshot
from datetime import datetime

# Get all snapshots for portfolio 1, ordered by date
snapshots = PortfolioSnapshot.objects.filter(portfolio_id=1).order_by('snapshot_date')

print(f'Total snapshots for portfolio 1: {snapshots.count()}\n')
print('Date                | Total Value    | Cash Balance   | Variation from prev')
print('-' * 80)

prev_value = None
for snap in snapshots:
    variation = ''
    if prev_value is not None:
        diff = snap.total_value - prev_value
        pct = (diff / prev_value * 100) if prev_value != 0 else 0
        variation = f'{diff:+.2f} ({pct:+.2f}%)'

    print(f'{snap.snapshot_date} | {snap.total_value:>14.2f} | {snap.cash_balance:>14.2f} | {variation}')
    prev_value = snap.total_value

# Check statistics
print('\n' + '=' * 80)
print('STATISTICS')
print('=' * 80)

values = [float(s.total_value) for s in snapshots]
cash_values = [float(s.cash_balance) for s in snapshots]

if values:
    import statistics
    print(f'\nTotal Value:')
    print(f'  Min: ${min(values):,.2f}')
    print(f'  Max: ${max(values):,.2f}')
    print(f'  Mean: ${statistics.mean(values):,.2f}')
    print(f'  Std Dev: ${statistics.stdev(values) if len(values) > 1 else 0:,.2f}')
    print(f'  Range: ${max(values) - min(values):,.2f}')

    print(f'\nCash Balance:')
    print(f'  Min: ${min(cash_values):,.2f}')
    print(f'  Max: ${max(cash_values):,.2f}')
    print(f'  Mean: ${statistics.mean(cash_values):,.2f}')
    print(f'  Std Dev: ${statistics.stdev(cash_values) if len(cash_values) > 1 else 0:,.2f}')
    print(f'  Range: ${max(cash_values) - min(cash_values):,.2f}')
