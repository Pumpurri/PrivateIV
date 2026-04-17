from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from datetime import timedelta
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from portfolio.models import Portfolio, Holding, Transaction
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot
from portfolio.serializers import HoldingSerializer
from portfolio.serializers.transaction_serializers import TransactionSerializer
from portfolio.services.currency_service import (
    convert_amount,
    get_portfolio_reporting_currency,
    get_transaction_amount_in_currency,
    normalize_currency,
)


def _q(val):
    if isinstance(val, Decimal):
        return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _convert_from_base(amount, portfolio, display_currency, *, snapshot_date=None):
    amount = Decimal(amount or '0.00')
    if display_currency == portfolio.base_currency:
        return _q(amount)
    return _q(
        convert_amount(
            amount,
            portfolio.base_currency,
            display_currency,
            snapshot_date=snapshot_date,
            session='cierre' if snapshot_date else None,
        )
    )


def _resolve_display_currency(request, portfolio):
    requested = request.query_params.get('currency')
    if requested in (None, ''):
        return get_portfolio_reporting_currency(portfolio)
    return normalize_currency(requested)


def _calculate_cash_flow_totals(portfolio, display_currency):
    deposits = Decimal('0.00')
    withdrawals = Decimal('0.00')

    for txn in Transaction.objects.filter(
        portfolio=portfolio,
        transaction_type__in=[
            Transaction.TransactionType.DEPOSIT,
            Transaction.TransactionType.WITHDRAWAL,
        ],
    ).order_by('timestamp', 'id'):
        amount = get_transaction_amount_in_currency(
            txn,
            display_currency,
            snapshot_date=txn.timestamp.date(),
        )
        if txn.transaction_type == Transaction.TransactionType.DEPOSIT:
            deposits += amount
        else:
            withdrawals += amount

    return _q(deposits), _q(withdrawals)


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        try:
            requested_currency = request.query_params.get('currency')
            if requested_currency not in (None, ''):
                normalize_currency(requested_currency)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        portfolios = (
            Portfolio.objects
            .filter(user=request.user)
            .select_related('performance')
        )

        default_p = portfolios.filter(is_default=True).first()
        default_id = default_p.id if default_p else None

        items = []
        for p in portfolios:
            display_currency = _resolve_display_currency(request, p)
            perf = getattr(p, 'performance', None)
            twr = perf.time_weighted_return if perf else Decimal('0.0000')
            deposits, withdrawals = _calculate_cash_flow_totals(p, display_currency)
            net_cash_flow = deposits - withdrawals

            today_total = _convert_from_base(p.total_value or Decimal('0.00'), p, display_currency)
            today_cash = _q(p.get_total_cash_balance(display_currency))
            today_investment = _convert_from_base(p.current_investment_value or Decimal('0.00'), p, display_currency)

            # Latest snapshot before today
            snap = (
                DailyPortfolioSnapshot.objects
                .filter(portfolio=p, date__lt=today)
                .order_by('-date')
                .first()
            )
            yesterday_total = (
                _convert_from_base(snap.total_value, p, display_currency, snapshot_date=snap.date)
                if snap else None
            )
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
                'base_currency': p.base_currency,
                'reporting_currency': get_portfolio_reporting_currency(p),
                'display_currency': display_currency,

                'total_value': _q(today_total),
                'cash_balance': today_cash,
                'current_investment_value': today_investment,
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
        recent_tx_display_currency = 'PEN'
        if requested_currency not in (None, ''):
            recent_tx_display_currency = normalize_currency(requested_currency)
        elif default_p is not None:
            recent_tx_display_currency = get_portfolio_reporting_currency(default_p)

        recent_tx_data = TransactionSerializer(
            recent_tx,
            many=True,
            context={'display_currency': recent_tx_display_currency},
        ).data

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
        today = timezone.now().date()
        p = get_object_or_404(
            Portfolio.objects.select_related('performance').filter(user=request.user),
            pk=portfolio_id
        )
        try:
            display_currency = _resolve_display_currency(request, p)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        perf = getattr(p, 'performance', None)
        twr = perf.time_weighted_return if perf else Decimal('0.0000')
        deposits, withdrawals = _calculate_cash_flow_totals(p, display_currency)
        net_cash_flow = deposits - withdrawals

        total_now = _convert_from_base(p.total_value or Decimal('0.00'), p, display_currency)
        cash_now = _q(p.get_total_cash_balance(display_currency))
        investment_now = _convert_from_base(p.current_investment_value or Decimal('0.00'), p, display_currency)
        snap = (
            DailyPortfolioSnapshot.objects
            .filter(portfolio=p, date__lt=today)
            .order_by('-date')
            .first()
        )
        yesterday_total = (
            _convert_from_base(snap.total_value, p, display_currency, snapshot_date=snap.date)
            if snap else None
        )
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
        trade_prefetch = Prefetch(
            'portfolio__transactions',
            queryset=Transaction.objects.filter(
                stock__isnull=False,
                transaction_type__in=[
                    Transaction.TransactionType.BUY,
                    Transaction.TransactionType.SELL,
                ],
            ).select_related('stock').order_by('timestamp', 'id'),
            to_attr='prefetched_transactions',
        )
        holdings = list(
            Holding.objects.filter(portfolio=p, is_active=True)
            .select_related('stock', 'portfolio')
            .prefetch_related(trade_prefetch)
        )
        account_total = total_now
        comp = []

        for h in holdings:
            holding_data = HoldingSerializer(
                h,
                context={'display_currency': display_currency},
            ).data
            cur_val = Decimal(holding_data['current_value'])
            weight = (cur_val / account_total * Decimal('100')).quantize(Decimal('0.01')) if account_total > 0 else Decimal('0.00')
            comp.append({
                'symbol': h.stock.symbol,
                'name': h.stock.name,
                'quantity': h.quantity,
                'current_value': _q(cur_val),
                'gain_loss': _q(holding_data['gain_loss']),
                'cost_basis': holding_data['cost_basis'],
                'weight_pct': weight,
                'display_currency': display_currency,
                'native_currency': h.stock.currency,
            })
        comp.sort(key=lambda x: x['current_value'], reverse=True)

        # Recent transactions for this portfolio
        recent_tx = (
            Transaction.objects
            .filter(portfolio=p)
            .select_related('stock')
            .order_by('-timestamp')[:5]
        )
        recent_tx_data = TransactionSerializer(
            recent_tx,
            many=True,
            context={'display_currency': display_currency},
        ).data

        # Snapshots (last 30 days by default)
        try:
            days = int(request.query_params.get('days', 30))
            if days < 1 or days > 3650:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'error': 'days must be an integer between 1 and 3650'}, status=400)
        since_date = today - timedelta(days=days)
        snaps = (
            DailyPortfolioSnapshot.objects
            .filter(portfolio=p, date__gte=since_date, date__lte=today)
            .order_by('date')
        )
        snapshot_payload = [
            {
                'date': snap.date,
                'total_value': _convert_from_base(snap.total_value, p, display_currency, snapshot_date=snap.date),
                'cash_balance': _convert_from_base(snap.cash_balance, p, display_currency, snapshot_date=snap.date),
                'investment_value': _convert_from_base(snap.investment_value, p, display_currency, snapshot_date=snap.date),
                'display_currency': display_currency,
            }
            for snap in snaps
        ]

        payload = {
            'portfolio': {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'is_default': p.is_default,
                'created_at': p.created_at,
                'base_currency': p.base_currency,
                'reporting_currency': get_portfolio_reporting_currency(p),
                'display_currency': display_currency,

                'total_value': _q(total_now),
                'cash_balance': cash_now,
                'current_investment_value': investment_now,
                'holdings_count': p.holdings.filter(is_active=True).count(),

                'twr_annualized': twr,
                'since_inception_abs': _q(since_abs),
                'since_inception_pct': since_pct.quantize(Decimal('0.01')),
                'day_change_abs': _q(day_abs),
                'day_change_pct': day_pct.quantize(Decimal('0.01')),
            },
            'composition': comp,
            'recent_transactions': recent_tx_data,
            'snapshots': snapshot_payload,
        }

        return Response(payload, status=status.HTTP_200_OK)
