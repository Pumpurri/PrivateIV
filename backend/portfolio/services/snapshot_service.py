# backend/portfolio/services/snapshot_service.py
from django.db import models, IntegrityError, transaction
import time
from decimal import Decimal, DivisionByZero, ROUND_HALF_UP
import logging
from django.db.models import Sum, Q, Max
from django.utils import timezone
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot
from portfolio.models.transaction import Transaction
from django.db.models import Case, When, F, Value, IntegerField
from stocks.models import Stock
from portfolio.models.holding_snapshot import HoldingSnapshot
from portfolio.services.fx_service import get_fx_rate
from django.core.cache import cache
from portfolio.services.tracing import span

logger = logging.getLogger(__name__)

class SnapshotService:
    @classmethod
    def _get_historical_cash(cls, portfolio, snapshot_date):
        """Calculate cash balance as of snapshot date using transaction history with error handling.

        This method properly accounts for all transaction types:
        - DEPOSIT: adds cash (positive amount)
        - WITHDRAWAL: removes cash (negative amount stored as positive, so we negate)
        - BUY: removes cash (amount * fx_rate if applicable)
        - SELL: adds cash (amount * fx_rate if applicable)
        """
        try:
            transactions = Transaction.objects.filter(
                portfolio=portfolio,
                timestamp__date__lte=snapshot_date
            ).select_related('stock').order_by('timestamp')

            cash_balance = Decimal('0.00')

            for txn in transactions:
                amount = Decimal(str(txn.amount)) if txn.amount else Decimal('0.00')
                fx_rate = Decimal(str(txn.fx_rate)) if txn.fx_rate else Decimal('1.00')

                if txn.transaction_type == Transaction.TransactionType.DEPOSIT:
                    # Deposits add cash
                    cash_balance += amount

                elif txn.transaction_type == Transaction.TransactionType.WITHDRAWAL:
                    # Withdrawals remove cash (amount is stored as positive)
                    cash_balance -= amount

                elif txn.transaction_type == Transaction.TransactionType.BUY:
                    # BUY removes cash
                    # Amount is in native currency (e.g., USD), need to convert to base currency (e.g., PEN)
                    cash_in_base = amount * fx_rate
                    cash_balance -= cash_in_base

                elif txn.transaction_type == Transaction.TransactionType.SELL:
                    # SELL adds cash
                    # Amount is in native currency, need to convert to base currency
                    cash_in_base = amount * fx_rate
                    cash_balance += cash_in_base

            return cash_balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        except Exception as e:
            logger.error(f"Error fetching historical cash for portfolio {portfolio.id} on {snapshot_date}: {str(e)}")
            import traceback
            traceback.print_exc()
            return Decimal('0.00')

    @classmethod
    def _get_historical_deposits(cls, portfolio, snapshot_date):
        """Calculate total deposits as of snapshot date with error handling."""
        try:
            deposit_data = Transaction.objects.filter(
                portfolio=portfolio,
                transaction_type='DEPOSIT',
                timestamp__date__lte=snapshot_date
            ).aggregate(total=Sum('amount'))
            return deposit_data['total'] or Decimal('0.00')
        except Exception as e:
            logger.error(f"Error fetching historical deposits for portfolio {portfolio.id} on {snapshot_date}: {str(e)}")
            return Decimal('0.00')

    @classmethod
    def _get_historical_price(cls, stock_id, snapshot_date, portfolio):
        """Enterprise-grade price resolution with cascading fallbacks"""
        from stocks.models import HistoricalStockPrice
        try:
            # Tier 1: Exact date match
            exact_price = HistoricalStockPrice.objects.filter(
                stock_id=stock_id,
                date=snapshot_date
            ).values_list('price', flat=True).first()
            if exact_price is not None:
                return exact_price, 'exact_date'

            # Tier 2: Latest historical price before snapshot
            historical_price = HistoricalStockPrice.objects.filter(
                stock_id=stock_id,
                date__lt=snapshot_date
            ).order_by('-date').values_list('price', flat=True).first()
            if historical_price is not None:
                return historical_price, 'latest_historical'

            # Tier 3: Most recent portfolio acquisition price
            buy_transaction = Transaction.objects.filter(
                portfolio=portfolio,
                stock_id=stock_id,
                transaction_type='BUY',
                timestamp__date__lte=snapshot_date
            ).exclude(executed_price=None).order_by('-timestamp').first()
            
            if buy_transaction:
                return buy_transaction.executed_price, 'portfolio_acquisition'

            # Tier 4: Nearest historical price (before or after)
            nearest_price = HistoricalStockPrice.objects.filter(
                stock_id=stock_id
            ).annotate(
                date_diff=Case(
                    When(date__lte=snapshot_date,
                         then=snapshot_date - F('date')),
                    When(date__gt=snapshot_date,
                         then=F('date') - snapshot_date),
                    output_field=models.DurationField()
                ),
                date_priority=Case(
                    When(date__lte=snapshot_date, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField()
                )
            ).order_by('date_priority', 'date_diff').values_list('price', flat=True).first()

            if nearest_price:
                return nearest_price, 'nearest_historical'

            # Tier 5: Current market price as last resort
            stock = Stock.objects.get(pk=stock_id)
            if stock.current_price > Decimal('0'):
                logger.warning(f"Using current price for {stock.symbol} on {snapshot_date}")
                return stock.current_price, 'current_price_fallback'
            
            latest_historical = HistoricalStockPrice.objects.filter(
                stock_id=stock_id,
                price__gt=0
            ).order_by('-date').first()
            if latest_historical:
                logger.warning(f"Using latest historical price for {stock.symbol} on {snapshot_date}")
                return latest_historical.price, 'historical_fallback'

            # Final fallback with data integrity check
            logger.error(f"Price resolution failed for {stock.symbol} on {snapshot_date}")
            return Decimal('0.00'), 'error_fallback'

        except Exception as e:
            logger.error(f"Price resolution error: {str(e)}")
            return Decimal('0.00'), 'system_error'
        

    @classmethod
    def _get_historical_holdings(cls, portfolio, snapshot_date):
        """Reconstruct portfolio holdings as of snapshot date using transaction history"""
        cache_version_key = f"holdings_version_{portfolio.pk}"
        cache_key = f"hist_hold_{portfolio.pk}_{snapshot_date}"
        
        # Get latest transaction timestamp for cache validation
        last_txn_time = Transaction.objects.filter(
            portfolio=portfolio,
            timestamp__date__lte=snapshot_date
        ).aggregate(Max('timestamp'))['timestamp__max'] or 0
        
        version = cache.get(cache_version_key, 0)
        cached = cache.get(f"{cache_key}_v{version}")
        
        if cached and cached.get('valid_until') == last_txn_time:
            return cached['holdings']
    
        holdings = {}  # {stock_id: {quantity, total_cost, average_price}}

        transactions = (
            Transaction.objects.filter(
                portfolio=portfolio,
                timestamp__date__lte=snapshot_date,
                transaction_type__in=[
                    Transaction.TransactionType.BUY,
                    Transaction.TransactionType.SELL
                ],
                stock__isnull=False
            )
            .select_related('stock')
            .order_by('timestamp')
        )

        for txn in transactions:
            stock_id = txn.stock.id
            if stock_id not in holdings:
                holdings[stock_id] = {
                    'quantity': 0,
                    'total_cost': Decimal('0.00'),
                    'average_price': Decimal('0.00')
                }
                
            current = holdings[stock_id]
            
            if txn.transaction_type == Transaction.TransactionType.BUY:
                new_quantity = current['quantity'] + txn.quantity
                new_total_cost = current['total_cost'] + (txn.executed_price * txn.quantity)
                new_avg = (new_total_cost / new_quantity).quantize(Decimal('0.01'), ROUND_HALF_UP) if new_quantity > 0 else Decimal('0.00')
                
                holdings[stock_id] = {
                    'quantity': new_quantity,
                    'total_cost': new_total_cost,
                    'average_price': new_avg
                }
                
            elif txn.transaction_type == Transaction.TransactionType.SELL:
                if current['quantity'] >= txn.quantity:
                    new_quantity = current['quantity'] - txn.quantity
                    holdings[stock_id] = {
                        'quantity': new_quantity,
                        'total_cost': current['average_price'] * new_quantity,
                        'average_price': current['average_price']
                    }

         # Filter out fully sold positions
        holdings = {k: v for k, v in holdings.items() if v['quantity'] > 0}

        # Write to versioned cache
        new_version = version + 1
        cache.set_many({
            cache_version_key: new_version,
            f"{cache_key}_v{new_version}": {
                'holdings': holdings,
                'valid_until': last_txn_time
            }
        }, timeout=60 * 60 * 24 * 7)  # 1 week cache

        return holdings

    @classmethod
    def create_daily_snapshot(cls, portfolio, date=None):
        """Creates daily snapshot with robust error handling and retries."""
        from portfolio.models.portfolio import Portfolio
        snapshot_date = date or timezone.now().date()
        with span("snapshot.daily", resource=str(portfolio.pk), tags={"date": str(snapshot_date)}), transaction.atomic():
            try:
                locked_portfolio = Portfolio.objects.select_for_update().get(pk=portfolio.pk)
                
                # Get historical holdings as of snapshot date
                historical_holdings = cls._get_historical_holdings(locked_portfolio, snapshot_date)
                
                # Calculate investment value (in base currency) and create holding snapshots
                investment_value = Decimal('0.00')
                holding_snapshots = []
                
                for stock_id, holding in historical_holdings.items():
                    stock = Stock.objects.get(pk=stock_id)
                    price, source = cls._get_historical_price(
                        stock_id, snapshot_date, locked_portfolio
                    )
                    native_value = price * holding['quantity']
                    # Convert to portfolio base currency
                    # Historical snapshots should use cierre and mid (estimate) for USD->PEN valuation
                    rate = get_fx_rate(
                        snapshot_date,
                        locked_portfolio.base_currency,
                        stock.currency,
                        rate_type='mid',
                        session='cierre'
                    )
                    stock_value_base = (native_value * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    investment_value += stock_value_base
                    
                    holding_snapshots.append(
                        HoldingSnapshot(
                            portfolio=locked_portfolio,
                            stock=stock,
                            date=snapshot_date,
                            quantity=holding['quantity'],
                            average_purchase_price=holding['average_price'],
                            # Store base-currency value to keep totals additive
                            total_value=stock_value_base
                        )
                    )

                # Delete existing snapshots for this date before creating new ones
                HoldingSnapshot.objects.filter(
                    portfolio=locked_portfolio,
                    date=snapshot_date
                ).delete()
                
                # Bulk create new snapshots
                HoldingSnapshot.objects.bulk_create(holding_snapshots)

                # Calculate cash balance and deposits
                # Note: historical_cash is assumed to be in portfolio base currency
                historical_cash = cls._get_historical_cash(locked_portfolio, snapshot_date)
                historical_deposits = cls._get_historical_deposits(locked_portfolio, snapshot_date)
                total_value = (historical_cash + investment_value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                # Retry logic for portfolio snapshot
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        snapshot, created = DailyPortfolioSnapshot.objects.update_or_create(
                            portfolio=locked_portfolio,
                            date=snapshot_date,
                            defaults={
                                'total_value': total_value,
                                'cash_balance': historical_cash,
                                'investment_value': investment_value,
                                'total_deposits': historical_deposits
                            }
                        )
                        return snapshot
                    except IntegrityError:
                        if retry == max_retries - 1:
                            raise
                        time.sleep(1)
                        
            except Exception as e:
                logger.error(f"Snapshot failed: {str(e)}")
                raise
