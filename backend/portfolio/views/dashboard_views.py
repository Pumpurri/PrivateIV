from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange
from django.utils import timezone
from datetime import timedelta
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from portfolio.models import Portfolio, Holding, Transaction, BenchmarkSeries, BenchmarkPrice
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot
from portfolio.serializers import HoldingSerializer
from portfolio.serializers.transaction_serializers import TransactionSerializer
from portfolio.services.currency_service import (
    convert_amount,
    get_portfolio_reporting_currency,
    get_transaction_amount_in_currency,
    normalize_currency,
)
from stocks.market import get_market_date


def _parse_iso_date_param(value):
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise ValueError('Date parameters must use YYYY-MM-DD format')


def _annualize_return(total_return, total_days):
    total_return = Decimal(total_return)
    if total_days <= 0:
        return total_return
    if total_days <= 365:
        return total_return
    return ((Decimal('1') + total_return) ** (Decimal('365') / Decimal(total_days))) - Decimal('1')


def _subtract_months(date_value, months):
    year = date_value.year
    month = date_value.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(date_value.day, monthrange(year, month)[1])
    return date_value.replace(year=year, month=month, day=day)


def _dashboard_today():
    # Anchor dashboard "today" to the U.S. market date so range and live-value
    # calculations stay stable for users outside UTC late in the day.
    return get_market_date(currency='USD')


def _build_portfolio_twr_payload(portfolio, display_currency, from_date, to_date):
    today = timezone.now().date()
    snapshots = [
        {
            'date': snap.date,
            'total_value': _convert_from_base(snap.total_value, portfolio, display_currency, snapshot_date=snap.date),
        }
        for snap in (
            DailyPortfolioSnapshot.objects
            .filter(portfolio=portfolio, date__gte=from_date, date__lte=to_date)
            .order_by('date')
        )
    ]

    if to_date >= today:
        live_total = _convert_from_base(portfolio.total_value or Decimal('0.00'), portfolio, display_currency)
        if snapshots and snapshots[-1]['date'] == today:
            snapshots[-1]['total_value'] = live_total
        elif not snapshots or snapshots[-1]['date'] < today:
            snapshots.append({'date': today, 'total_value': live_total})

    if len(snapshots) < 2:
        return None

    cash_flows = [
        {
            'date': txn.timestamp.date(),
            'amount': get_transaction_amount_in_currency(
                txn,
                display_currency,
                snapshot_date=txn.timestamp.date(),
            ),
        }
        for txn in (
            Transaction.objects.filter(
                portfolio=portfolio,
                timestamp__date__gt=snapshots[0]['date'],
                timestamp__date__lte=snapshots[-1]['date'],
                transaction_type__in=[
                    Transaction.TransactionType.DEPOSIT,
                    Transaction.TransactionType.WITHDRAWAL,
                ],
            )
            .order_by('timestamp', 'id')
        )
    ]

    cumulative = Decimal('1.0')
    series = [{'date': snapshots[0]['date'], 'return_pct': Decimal('0.00')}]
    flow_index = 0

    for previous, current in zip(snapshots, snapshots[1:]):
        period_cash_flow = Decimal('0.00')
        while flow_index < len(cash_flows):
            flow = cash_flows[flow_index]
            if flow['date'] <= previous['date']:
                flow_index += 1
                continue
            if flow['date'] > current['date']:
                break
            period_cash_flow += Decimal(flow['amount'])
            flow_index += 1

        previous_value = Decimal(previous['total_value'])
        current_value = Decimal(current['total_value'])
        if previous_value <= 0:
            sub_return = Decimal('0.00')
        else:
            sub_return = ((current_value - period_cash_flow) / previous_value) - Decimal('1')
        cumulative *= (Decimal('1') + sub_return)
        cumulative_return = cumulative - Decimal('1')
        series.append({
            'date': current['date'],
            'return_pct': (cumulative_return * Decimal('100')).quantize(Decimal('0.01')),
        })

    total_days = (snapshots[-1]['date'] - snapshots[0]['date']).days
    cumulative_return = cumulative - Decimal('1')
    annualized_return = _annualize_return(cumulative_return, total_days)

    return {
        'from': snapshots[0]['date'],
        'to': snapshots[-1]['date'],
        'cumulative_return_pct': (cumulative_return * Decimal('100')).quantize(Decimal('0.01')),
        'annualized_return_pct': (annualized_return * Decimal('100')).quantize(Decimal('0.01')),
        'series': series,
    }


def _get_snapshot_breakdown_rows(portfolio, display_currency, from_date, to_date):
    today = timezone.now().date()
    rows = [
        {
            'date': snap.date,
            'total_value': _convert_from_base(snap.total_value, portfolio, display_currency, snapshot_date=snap.date),
            'cash_balance': _convert_from_base(snap.cash_balance, portfolio, display_currency, snapshot_date=snap.date),
            'investment_value': _convert_from_base(snap.investment_value, portfolio, display_currency, snapshot_date=snap.date),
        }
        for snap in (
            DailyPortfolioSnapshot.objects
            .filter(portfolio=portfolio, date__gte=from_date, date__lte=to_date)
            .order_by('date')
        )
    ]

    if to_date >= today:
        live_total = _convert_from_base(portfolio.total_value or Decimal('0.00'), portfolio, display_currency)
        live_cash = _q(portfolio.get_total_cash_balance(display_currency))
        live_investment = _convert_from_base(portfolio.current_investment_value or Decimal('0.00'), portfolio, display_currency)
        if rows and rows[-1]['date'] == today:
            rows[-1] = {
                'date': today,
                'total_value': live_total,
                'cash_balance': live_cash,
                'investment_value': live_investment,
            }
        elif not rows or rows[-1]['date'] < today:
            rows.append({
                'date': today,
                'total_value': live_total,
                'cash_balance': live_cash,
                'investment_value': live_investment,
            })

    return rows


def _empty_history_range(from_date, to_date):
    return {
        'range': {'from': from_date, 'to': to_date},
        'beginning_value': None,
        'beginning_market_value': None,
        'beginning_cash_value': None,
        'deposits': None,
        'withdrawals': None,
        'net_contributions': None,
        'investment_changes': None,
        'ending_value': None,
        'ending_market_value': None,
        'ending_cash_value': None,
    }


def _build_history_range_breakdown(portfolio, display_currency, from_date, to_date):
    snapshot_rows = _get_snapshot_breakdown_rows(portfolio, display_currency, from_date, to_date)
    if not snapshot_rows:
        return _empty_history_range(from_date, to_date)

    deposits = Decimal('0.00')
    withdrawals = Decimal('0.00')
    for txn in (
        Transaction.objects.filter(
            portfolio=portfolio,
            timestamp__date__gte=snapshot_rows[0]['date'],
            timestamp__date__lte=snapshot_rows[-1]['date'],
            transaction_type__in=[
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.WITHDRAWAL,
            ],
        )
        .order_by('timestamp', 'id')
    ):
        amount = Decimal(get_transaction_amount_in_currency(
            txn,
            display_currency,
            snapshot_date=txn.timestamp.date(),
        ) or '0.00')
        if txn.transaction_type == Transaction.TransactionType.DEPOSIT:
            deposits += abs(amount)
        else:
            withdrawals += abs(amount)

    beginning = snapshot_rows[0]
    ending = snapshot_rows[-1]
    net_contributions = deposits - withdrawals
    investment_changes = Decimal(ending['total_value']) - Decimal(beginning['total_value']) - net_contributions

    return {
        'range': {'from': beginning['date'], 'to': ending['date']},
        'beginning_value': _q(beginning['total_value']),
        'beginning_market_value': _q(beginning['investment_value']),
        'beginning_cash_value': _q(beginning['cash_balance']),
        'deposits': _q(deposits),
        'withdrawals': _q(withdrawals),
        'net_contributions': _q(net_contributions),
        'investment_changes': _q(investment_changes),
        'ending_value': _q(ending['total_value']),
        'ending_market_value': _q(ending['investment_value']),
        'ending_cash_value': _q(ending['cash_balance']),
    }


def _build_history_payload(portfolio, display_currency, selected_from, selected_to):
    latest_snapshot = (
        DailyPortfolioSnapshot.objects
        .filter(portfolio=portfolio)
        .order_by('-date')
        .values_list('date', flat=True)
        .first()
    )
    earliest_snapshot = (
        DailyPortfolioSnapshot.objects
        .filter(portfolio=portfolio)
        .order_by('date')
        .values_list('date', flat=True)
        .first()
    )

    today = _dashboard_today()
    latest_available = max(latest_snapshot or today, today)
    earliest_available = earliest_snapshot or portfolio.created_at.date() or latest_available

    one_year_start = _subtract_months(latest_available, 12)
    ytd_start = latest_available.replace(month=1, day=1)

    return {
        'selected': _build_history_range_breakdown(portfolio, display_currency, selected_from, selected_to),
        'ytd': (
            _empty_history_range(ytd_start, latest_available)
            if earliest_available > ytd_start
            else _build_history_range_breakdown(portfolio, display_currency, ytd_start, latest_available)
        ),
        'one_year': (
            _empty_history_range(one_year_start, latest_available)
            if earliest_available > one_year_start
            else _build_history_range_breakdown(portfolio, display_currency, one_year_start, latest_available)
        ),
        'max': _build_history_range_breakdown(portfolio, display_currency, earliest_available, latest_available),
    }


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
    perf = getattr(portfolio, 'performance', None)
    if perf is not None:
        return (
            _convert_from_base(perf.total_deposits or Decimal('0.00'), portfolio, display_currency),
            _convert_from_base(perf.total_withdrawals or Decimal('0.00'), portfolio, display_currency),
        )

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


class PortfolioBenchmarkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, portfolio_id):
        portfolio = get_object_or_404(
            Portfolio.objects.filter(user=request.user),
            pk=portfolio_id,
        )

        try:
            from_date = _parse_iso_date_param(request.query_params.get('from'))
            to_date = _parse_iso_date_param(request.query_params.get('to'))
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if from_date is None or to_date is None:
            return Response({'error': 'from and to query parameters are required'}, status=status.HTTP_400_BAD_REQUEST)
        if from_date > to_date:
            return Response({'error': 'from must be less than or equal to to'}, status=status.HTTP_400_BAD_REQUEST)

        requested_codes = request.query_params.get('codes')
        code_list = None
        if requested_codes:
            code_list = [code.strip().lower() for code in requested_codes.split(',') if code.strip()]

        benchmark_qs = BenchmarkSeries.objects.filter(is_active=True)
        if code_list is not None:
            benchmark_qs = benchmark_qs.filter(code__in=code_list)

        display_currency = _resolve_display_currency(request, portfolio)
        portfolio_payload = _build_portfolio_twr_payload(portfolio, display_currency, from_date, to_date)
        history_payload = _build_history_payload(portfolio, display_currency, from_date, to_date)
        benchmarks = []
        for series in benchmark_qs.order_by('name'):
            prices = list(
                BenchmarkPrice.objects
                .filter(series=series, date__gte=from_date, date__lte=to_date)
                .order_by('date')
                .values('date', 'close')
            )
            if len(prices) < 2:
                continue

            start_close = Decimal(prices[0]['close'])
            end_close = Decimal(prices[-1]['close'])
            if start_close <= 0:
                continue

            cumulative_return = (end_close / start_close) - Decimal('1')
            total_days = (prices[-1]['date'] - prices[0]['date']).days
            annualized_return = _annualize_return(cumulative_return, total_days)

            benchmarks.append({
                'code': series.code,
                'name': series.name,
                'provider_symbol': series.provider_symbol,
                'currency': series.currency,
                'from': prices[0]['date'],
                'to': prices[-1]['date'],
                'cumulative_return_pct': (cumulative_return * Decimal('100')).quantize(Decimal('0.01')),
                'annualized_return_pct': (annualized_return * Decimal('100')).quantize(Decimal('0.01')),
                'series': [
                    {
                        'date': item['date'],
                        'return_pct': (((Decimal(item['close']) / start_close) - Decimal('1')) * Decimal('100')).quantize(Decimal('0.01')),
                    }
                    for item in prices
                ],
            })

        return Response(
            {
                'portfolio_id': portfolio.id,
                'from': from_date,
                'to': to_date,
                'portfolio': portfolio_payload,
                'history': history_payload,
                'benchmarks': benchmarks,
            },
            status=status.HTTP_200_OK,
        )
