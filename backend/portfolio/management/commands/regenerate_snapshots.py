from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from portfolio.models import Portfolio
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot
from portfolio.services.snapshot_service import SnapshotService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Regenerate daily portfolio snapshots with corrected cash calculations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--portfolio-id',
            type=int,
            help='Regenerate snapshots for a specific portfolio ID only'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days back to regenerate (default: 30)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Regenerate all historical snapshots'
        )
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing snapshots before regenerating'
        )

    def handle(self, *args, **options):
        portfolio_id = options.get('portfolio_id')
        days_back = options.get('days')
        regenerate_all = options.get('all')
        delete_existing = options.get('delete_existing')

        # Get portfolios
        if portfolio_id:
            portfolios = Portfolio.objects.filter(id=portfolio_id)
            if not portfolios.exists():
                self.stdout.write(self.style.ERROR(f'Portfolio {portfolio_id} not found'))
                return
        else:
            portfolios = Portfolio.objects.all()

        self.stdout.write(self.style.SUCCESS(f'Found {portfolios.count()} portfolio(s)'))

        for portfolio in portfolios:
            self.stdout.write(f'\nProcessing portfolio: {portfolio.name} (ID: {portfolio.id})')

            # Delete existing snapshots if requested
            if delete_existing:
                deleted_count = DailyPortfolioSnapshot.objects.filter(portfolio=portfolio).count()
                DailyPortfolioSnapshot.objects.filter(portfolio=portfolio).delete()
                self.stdout.write(self.style.WARNING(f'  Deleted {deleted_count} existing snapshots'))

            # Determine date range
            today = timezone.now().date()
            if regenerate_all:
                # Get the earliest transaction date
                first_txn = portfolio.transactions.order_by('timestamp').first()
                if first_txn:
                    start_date = first_txn.timestamp.date()
                else:
                    start_date = portfolio.created_at.date()
                self.stdout.write(f'  Regenerating from {start_date} to {today}')
            else:
                start_date = today - timedelta(days=days_back)
                self.stdout.write(f'  Regenerating last {days_back} days: {start_date} to {today}')

            # Generate snapshots
            current_date = start_date
            success_count = 0
            error_count = 0

            while current_date <= today:
                try:
                    snapshot = SnapshotService.create_daily_snapshot(portfolio, current_date)
                    success_count += 1

                    # Show details for recent snapshots
                    if (today - current_date).days <= 7:
                        self.stdout.write(
                            f'  ✓ {current_date}: Total={snapshot.total_value:,.2f}, '
                            f'Cash={snapshot.cash_balance:,.2f}, '
                            f'Investment={snapshot.investment_value:,.2f}'
                        )
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ {current_date}: {str(e)}'))

                current_date += timedelta(days=1)

            self.stdout.write(self.style.SUCCESS(
                f'  Completed: {success_count} snapshots created, {error_count} errors'
            ))

            # Show current portfolio state
            self.stdout.write(f'\n  Current Portfolio State:')
            self.stdout.write(f'    Cash: {portfolio.base_currency} {portfolio.cash_balance:,.2f}')
            self.stdout.write(f'    Investment: {portfolio.base_currency} {portfolio.current_investment_value:,.2f}')
            self.stdout.write(f'    Total: {portfolio.base_currency} {portfolio.total_value:,.2f}')

        self.stdout.write(self.style.SUCCESS('\n✅ Snapshot regeneration complete!'))
