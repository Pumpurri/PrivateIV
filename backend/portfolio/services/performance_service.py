from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from portfolio.models.transaction import Transaction
from portfolio.services.currency_service import get_transaction_amount_in_currency
from .historical_valuation import HistoricalValuationService

class PerformanceCalculator:
    @staticmethod
    def calculate_all_time_weighted_return(portfolio, end_date=None):
        """Calculate the portfolio's annualized TWR from its first transaction to now."""
        end_date = end_date or timezone.now()
        first_transaction_at = (
            Transaction.all_objects
            .filter(portfolio=portfolio)
            .order_by('timestamp')
            .values_list('timestamp', flat=True)
            .first()
        )

        if not first_transaction_at or first_transaction_at >= end_date:
            return Decimal('0.0000')

        return PerformanceCalculator.calculate_time_weighted_return(
            portfolio=portfolio,
            start_date=first_transaction_at,
            end_date=end_date,
        )

    @staticmethod
    def calculate_time_weighted_return(portfolio, start_date, end_date):
        """
        Estimate time-weighted return from end-of-day valuations, adjusting each
        sub-period for deposits and withdrawals on its ending date.

        Exact intraday TWR would require valuations immediately before each flow;
        those are not available from the daily historical price data.
        """
        if start_date >= end_date:
            return Decimal('0.0000')

        cash_flows = Transaction.objects.filter(
            portfolio=portfolio,
            timestamp__range=(start_date, end_date),
            transaction_type__in=[
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.WITHDRAWAL
            ]
        ).order_by('timestamp', 'id')

        net_flows_by_date = defaultdict(lambda: Decimal('0.00'))
        for cash_flow in cash_flows:
            flow_date = cash_flow.timestamp.date()
            amount = get_transaction_amount_in_currency(
                cash_flow,
                portfolio.base_currency,
                snapshot_date=flow_date,
            )
            if cash_flow.transaction_type == Transaction.TransactionType.WITHDRAWAL:
                amount = -amount
            net_flows_by_date[flow_date] += amount

        # Build boundary dates for sub-periods
        boundary_dates = [start_date.date()] + list(net_flows_by_date) + [end_date.date()]
        unique_dates = sorted(set(boundary_dates))

        # Create sub-period ranges
        periods = [(unique_dates[i], unique_dates[i+1]) for i in range(len(unique_dates)-1)]

        cumulative_return = Decimal('1.0')

        for period_start, period_end in periods:
            # Use historical valuation service instead of raw snapshots
            start_value = HistoricalValuationService.get_historical_value(
                portfolio, period_start
            )
            end_value = HistoricalValuationService.get_historical_value(
                portfolio, period_end
            )

            # Ensure values are valid
            if start_value is None or end_value is None:
                raise ValueError(
                    f"Missing valuation for {period_start} or {period_end}"
                )

            if start_value == Decimal('0'):
                sub_return = Decimal('0')
            else:
                # The ending valuation includes that day's external cash flow.
                # Removing it keeps contributions from appearing as returns.
                external_flow = net_flows_by_date[period_end]
                sub_return = (end_value - external_flow - start_value) / start_value
            cumulative_return *= (Decimal('1') + sub_return)

        # Calculate time-weighted return
        twr = cumulative_return - Decimal('1')

        # Annualize
        total_days = (end_date - start_date).days
        if total_days > 0:
            annualized_twr = (
                (Decimal('1') + twr) ** (Decimal('365') / Decimal(total_days)) - Decimal('1')
            )
        else:
            annualized_twr = twr

        return annualized_twr.quantize(
            Decimal('0.0000'), rounding=ROUND_HALF_UP
        )
    
    @staticmethod
    def calculate_total_growth(portfolio):
        """Break down portfolio returns with accurate net cash flow"""
        performance = portfolio.performance
        net_cash_flow = performance.total_deposits - performance.total_withdrawals
        current_value = portfolio.total_value
        investment_growth = current_value - net_cash_flow
        
        return {
            'cash_contributions': performance.total_deposits,
            'cash_withdrawals': performance.total_withdrawals,
            'investment_growth': investment_growth,
            'net_cash_flow': net_cash_flow,
            'total_return': current_value
        }
    
    def calculate_investment_only_growth(portfolio):
        """Growth excluding cash holdings with accurate net cash flow"""
        performance = portfolio.performance
        net_cash_flow = performance.total_deposits - performance.total_withdrawals
        current_value = portfolio.total_value
        cash_balance = portfolio.cash_balance
        investment_growth = current_value - net_cash_flow - cash_balance
        
        return {
            'net_cash_flow': net_cash_flow,
            'investment_growth': investment_growth,
            'total_return': current_value
        }
    
