"""Audit and optionally repair trade cost basis from recorded execution data."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from portfolio.models import Holding, Portfolio, RealizedPNL, Transaction
from portfolio.models.holding_snapshot import HoldingSnapshot
from portfolio.services.trade_basis_service import TradeReplayError, replay_trade_basis


class Command(BaseCommand):
    help = 'Audit one portfolio trade basis; use --apply only after reviewing the dry run.'

    def add_arguments(self, parser):
        parser.add_argument('--portfolio-id', type=int, required=True)
        parser.add_argument('--apply', action='store_true', help='Write the audited corrections')

    def handle(self, *args, **options):
        portfolio_id = options['portfolio_id']
        apply = options['apply']

        with transaction.atomic():
            try:
                portfolio = Portfolio.all_objects.select_for_update().get(pk=portfolio_id)
            except Portfolio.DoesNotExist as exc:
                raise CommandError(f'Portfolio {portfolio_id} does not exist') from exc

            trades = list(
                Transaction.all_objects.filter(
                    portfolio_id=portfolio_id,
                    transaction_type__in=('BUY', 'SELL'),
                ).select_related('stock').order_by('timestamp', 'id')
            )
            try:
                positions, expected_realized = replay_trade_basis(trades, portfolio.base_currency)
            except (TradeReplayError, ValueError) as exc:
                raise CommandError(str(exc)) from exc

            holdings = {row.stock_id: row for row in Holding.objects.filter(portfolio_id=portfolio_id)}
            if set(holdings) != set(positions):
                raise CommandError('Current holdings do not match the recorded trade history; no changes made')
            for stock_id, expected in positions.items():
                if holdings[stock_id].quantity != expected['quantity']:
                    raise CommandError(f'Stock {stock_id} holding quantity differs from trade history; no changes made')

            realized_rows = {
                row.transaction_id: row
                for row in RealizedPNL.objects.filter(portfolio_id=portfolio_id)
            }
            if set(realized_rows) != set(expected_realized):
                raise CommandError('Realized P&L records do not match recorded sells; no changes made')
            for trade in trades:
                if trade.transaction_type != 'SELL':
                    continue
                row = realized_rows[trade.pk]
                if row.stock_id != trade.stock_id or row.quantity != trade.quantity or row.portfolio_id != portfolio_id:
                    raise CommandError(f'Realized P&L for trade {trade.pk} has inconsistent ownership or quantity')

            snapshots = list(HoldingSnapshot.objects.filter(portfolio_id=portfolio_id).order_by('date', 'id'))
            snapshot_changes = []
            for snapshot_date in sorted({row.date for row in snapshots}):
                dated_trades = [
                    trade for trade in trades
                    if timezone.localtime(trade.timestamp).date() <= snapshot_date
                ]
                try:
                    dated_positions, _ = replay_trade_basis(dated_trades, portfolio.base_currency)
                except (TradeReplayError, ValueError) as exc:
                    raise CommandError(f'Snapshot {snapshot_date}: {exc}') from exc
                dated_rows = [row for row in snapshots if row.date == snapshot_date]
                if {row.stock_id for row in dated_rows} != set(dated_positions):
                    raise CommandError(f'Snapshot {snapshot_date} positions differ from trade history; no changes made')
                for row in dated_rows:
                    expected = dated_positions[row.stock_id]
                    if row.quantity != expected['quantity']:
                        raise CommandError(f'Snapshot {snapshot_date} quantity differs from trade history; no changes made')
                    if row.average_purchase_price != expected['average_price']:
                        snapshot_changes.append((row, expected['average_price']))

            holding_changes = [
                (holdings[stock_id], expected['average_price'])
                for stock_id, expected in positions.items()
                if holdings[stock_id].average_purchase_price != expected['average_price']
            ]
            realized_changes = [
                (realized_rows[trade_id], expected)
                for trade_id, expected in expected_realized.items()
                if any(getattr(realized_rows[trade_id], field) != value for field, value in expected.items())
            ]

            self.stdout.write(
                f"Portfolio {portfolio_id} ({portfolio.base_currency}): "
                f"{len(holding_changes)} holding(s), {len(realized_changes)} realized record(s), "
                f"{len(snapshot_changes)} holding snapshot(s) differ."
            )
            for row, value in holding_changes:
                self.stdout.write(f'  Holding {row.pk}: {row.average_purchase_price} -> {value}')
            for row, expected in realized_changes:
                self.stdout.write(f'  Realized P&L {row.pk}: '
                                  f'{row.purchase_price}/{row.sell_price}/{row.pnl} -> '
                                  f"{expected['purchase_price']}/{expected['sell_price']}/{expected['pnl']}")
            for row, value in snapshot_changes:
                self.stdout.write(f'  Snapshot {row.pk} ({row.date}): {row.average_purchase_price} -> {value}')

            if not apply:
                self.stdout.write('Dry run only; no data changed. Review before running with --apply.')
                return

            for row, value in holding_changes:
                Holding.objects.filter(pk=row.pk).update(average_purchase_price=value)
            for row, expected in realized_changes:
                # This explicit audited repair bypasses RealizedPNL.save's immutability guard.
                RealizedPNL.objects.filter(pk=row.pk).update(**expected)
            for row, value in snapshot_changes:
                HoldingSnapshot.objects.filter(pk=row.pk).update(average_purchase_price=value)
            self.stdout.write(self.style.SUCCESS('Corrections applied atomically.'))
