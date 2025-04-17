from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.db.models import Sum
from portfolio.models import DailyPortfolioSnapshot, Transaction

class PerformanceCalculator:
    @staticmethod
    def calculate_time_weighted_return(portfolio, start_date, end_date):
        """
        Calculates time-weighted return using the Modified Dietz method
        """
        if start_date >= end_date:
            return Decimal('0.0000')

        snapshots = DailyPortfolioSnapshot.objects.filter(
            portfolio=portfolio,
            date__gte=start_date.date(),
            date__lte=end_date.date()
        ).order_by('date')

        if not snapshots.exists():
            return Decimal('0.0000')

        cash_flows = Transaction.objects.filter(
            portfolio=portfolio,
            timestamp__range=(start_date, end_date),
            transaction_type='DEPOSIT'
        ).annotate(
            date=models.F('timestamp__date')
        ).values('date').annotate(
            total=Sum('amount')
        ).order_by('date')

        start_value = snapshots.first().total_value
        end_value = snapshots.last().total_value
        net_cash_flow = Decimal('0.00')
        weighted_cash_flows = Decimal('0.00')
        total_days = (end_date - start_date).days

        # Calculate net cash flows and their time weighting
        for cf in cash_flows:
            days_in_period = (end_date - cf['date']).days
            weight = Decimal(days_in_period) / Decimal(total_days)
            weighted_cash_flows += cf['total'] * weight
            net_cash_flow += cf['total']

        # Modified Dietz formula
        modified_dietz_return = (
            (end_value - start_value - net_cash_flow) /
            (start_value + weighted_cash_flows)
        ).quantize(Decimal('0.0000'), rounding=ROUND_HALF_UP)

        # Annualize if period > 1 day
        if total_days > 1:
            annualized_return = (
                (Decimal('1') + modified_dietz_return) **
                (Decimal('365') / Decimal(total_days)) - Decimal('1')
            )
        else:
            annualized_return = modified_dietz_return

        return annualized_return.quantize(Decimal('0.0000'))

    @staticmethod
    def calculate_total_growth(portfolio):
        """Break down portfolio returns into cash contributions and investment growth"""
        performance = portfolio.performance
        total_deposits = performance.total_deposits
        current_value = portfolio.total_value
        investment_growth = current_value - total_deposits
        
        return {
            'cash_contribution': total_deposits,
            'investment_growth': investment_growth,
            'total_return': current_value
        }
    
    def calculate_investment_only_growth(portfolio):
        """Growth attributed solely to invested assets, excluding cash holdings."""
        performance = portfolio.performance
        total_deposits = performance.total_deposits
        current_value = portfolio.total_value
        cash_balance = portfolio.cash_balance
        investment_growth = current_value - total_deposits - cash_balance
        
        return {
            'cash_contribution': total_deposits,
            'investment_growth': investment_growth,
            'total_return': current_value
        }
    
