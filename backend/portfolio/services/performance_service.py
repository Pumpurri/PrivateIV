from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.db.models import Sum
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot
from portfolio.models.transaction import Transaction
from .historical_valuation import HistoricalValuationService

class PerformanceCalculator:
    @staticmethod
    def calculate_time_weighted_return(portfolio, start_date, end_date):
        """
        Calculates true time-weighted return by geometrically linking daily returns
        and splitting periods at cash flow events (deposits/withdrawals).
        """
        if start_date >= end_date:
            return Decimal('0.0000')

        # Fetch all cash flow dates (deposits and withdrawals) within the period
        cash_flow_dates = Transaction.objects.filter(
            portfolio=portfolio,
            timestamp__range=(start_date, end_date),
            transaction_type__in=[
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.WITHDRAWAL
            ]
        ).annotate(
            date=models.F('timestamp__date')
        ).values_list('date', flat=True).distinct().order_by('date')

        # Build boundary dates for sub-periods
        boundary_dates = [start_date.date()] + list(cash_flow_dates) + [end_date.date()]
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
                sub_return = (end_value - start_value) / start_value
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
    
