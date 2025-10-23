from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from portfolio.models import Portfolio
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot
from portfolio.models.transaction import Transaction
from portfolio.serializers.transaction_serializers import TransactionSerializer


def _q(val):
    if isinstance(val, Decimal):
        return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()

        portfolios = (
            Portfolio.objects
            .filter(user=request.user)
            .select_related('performance')
        )

        default_p = portfolios.filter(is_default=True).first()
        default_id = default_p.id if default_p else None

        items = []
        for p in portfolios:
            perf = getattr(p, 'performance', None)
            twr = perf.time_weighted_return if perf else Decimal('0.0000')
            deposits = perf.total_deposits if perf else Decimal('0.00')
            withdrawals = perf.total_withdrawals if perf else Decimal('0.00')
            net_cash_flow = deposits - withdrawals

            today_total = p.total_value or Decimal('0.00')

            # Latest snapshot before today
            snap = (
                DailyPortfolioSnapshot.objects
                .filter(portfolio=p, date__lt=today)
                .order_by('-date')
                .first()
            )
            yesterday_total = snap.total_value if snap else None
            if yesterday_total and yesterday_total > 0:
                day_abs = today_total - yesterday_total
                day_pct = (day_abs / yesterday_total) * Decimal('100')
            else:
                day_abs = Decimal('0.00')
                day_pct = Decimal('0.00')

            if net_cash_flow and net_cash_flow > 0:
                since_abs = today_total - net_cash_flow
                since_pct = (since_abs / net_cash_flow) * Decimal('100')
            else:
                since_abs = Decimal('0.00')
                since_pct = Decimal('0.00')

            items.append({
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'is_default': p.is_default,
                'created_at': p.created_at,

                'total_value': _q(today_total),
                'cash_balance': _q(p.cash_balance),
                'current_investment_value': _q(p.current_investment_value),
                'holdings_count': p.holdings.filter(is_active=True).count(),

                'twr_annualized': twr,  # already quantized(0.0000)
                'since_inception_abs': _q(since_abs),
                'since_inception_pct': since_pct.quantize(Decimal('0.01')),

                'day_change_abs': _q(day_abs),
                'day_change_pct': day_pct.quantize(Decimal('0.01')),
            })

        recent_tx = (
            Transaction.objects
            .filter(portfolio__user=request.user)
            .select_related('stock', 'portfolio')
            .order_by('-timestamp')[:5]
        )
        recent_tx_data = TransactionSerializer(recent_tx, many=True).data

        payload = {
            'user': {
                'id': request.user.id,
                'email': request.user.email,
                'full_name': getattr(request.user, 'full_name', ''),
            },
            'default_portfolio_id': default_id,
            'portfolios': items,
            'recent_transactions': recent_tx_data,
        }

        return Response(payload, status=status.HTTP_200_OK)


class PortfolioOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, portfolio_id):
        from portfolio.models import Holding
        from django.shortcuts import get_object_or_404

        today = timezone.now().date()
        p = get_object_or_404(
            Portfolio.objects.select_related('performance').filter(user=request.user),
            pk=portfolio_id
        )

        perf = getattr(p, 'performance', None)
        twr = perf.time_weighted_return if perf else Decimal('0.0000')
        deposits = perf.total_deposits if perf else Decimal('0.00')
        withdrawals = perf.total_withdrawals if perf else Decimal('0.00')
        net_cash_flow = deposits - withdrawals

        total_now = p.total_value or Decimal('0.00')
        snap = (
            DailyPortfolioSnapshot.objects
            .filter(portfolio=p, date__lt=today)
            .order_by('-date')
            .first()
        )
        yesterday_total = snap.total_value if snap else None
        if yesterday_total and yesterday_total > 0:
            day_abs = total_now - yesterday_total
            day_pct = (day_abs / yesterday_total) * Decimal('100')
        else:
            day_abs = Decimal('0.00')
            day_pct = Decimal('0.00')

        if net_cash_flow and net_cash_flow > 0:
            since_abs = total_now - net_cash_flow
            since_pct = (since_abs / net_cash_flow) * Decimal('100')
        else:
            since_abs = Decimal('0.00')
            since_pct = Decimal('0.00')

        # Composition (top holdings by value)
        holdings = list(
            Holding.objects.filter(portfolio=p, is_active=True).select_related('stock')
        )
        # Use total_value (cash + investments) for percentage calculation
        account_total = p.total_value or Decimal('0.00')
        comp = []

        # Use serializer to get all calculated fields including cost_basis
        from portfolio.serializers import HoldingSerializer

        for h in holdings:
            serializer = HoldingSerializer(h)
            cur_val = h.current_value
            weight = (cur_val / account_total * Decimal('100')).quantize(Decimal('0.01')) if account_total > 0 else Decimal('0.00')
            comp.append({
                'symbol': h.stock.symbol,
                'name': h.stock.name,
                'quantity': h.quantity,
                'current_value': _q(cur_val),
                'gain_loss': _q(h.gain_loss),
                'cost_basis': serializer.data['cost_basis'],
                'weight_pct': weight,
            })
        comp.sort(key=lambda x: x['current_value'], reverse=True)

        # Recent transactions for this portfolio
        recent_tx = (
            Transaction.objects
            .filter(portfolio=p)
            .select_related('stock')
            .order_by('-timestamp')[:5]
        )
        recent_tx_data = TransactionSerializer(recent_tx, many=True).data

        # Snapshots (last 30 days by default)
        days = int(request.query_params.get('days', 30))
        since_date = today - timedelta(days=days)
        snaps = (
            DailyPortfolioSnapshot.objects
            .filter(portfolio=p, date__gte=since_date, date__lte=today)
            .order_by('date')
            .values('date', 'total_value', 'cash_balance', 'investment_value')
        )

        payload = {
            'portfolio': {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'is_default': p.is_default,
                'created_at': p.created_at,

                'total_value': _q(total_now),
                'cash_balance': _q(p.cash_balance),
                'current_investment_value': _q(p.current_investment_value),
                'holdings_count': p.holdings.filter(is_active=True).count(),

                'twr_annualized': twr,
                'since_inception_abs': _q(since_abs),
                'since_inception_pct': since_pct.quantize(Decimal('0.01')),
                'day_change_abs': _q(day_abs),
                'day_change_pct': day_pct.quantize(Decimal('0.01')),
            },
            'composition': comp,
            'recent_transactions': recent_tx_data,
            'snapshots': list(snaps),
        }

        return Response(payload, status=status.HTTP_200_OK)
