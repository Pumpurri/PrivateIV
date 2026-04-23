from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolio.models import Portfolio, RealizedPNL, Transaction
from portfolio.services.currency_service import (
    DISPLAY_CURRENCY_NATIVE,
    convert_amount,
    get_portfolio_reporting_currency,
    get_transaction_original_currency,
    get_transaction_amount_in_currency,
    normalize_currency,
)


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _resolve_acquisition_date(pnl):
    sell_timestamp = pnl.transaction.timestamp
    acquisition_date = pnl.acquisition_date

    if acquisition_date and acquisition_date <= sell_timestamp:
        return acquisition_date

    buy_timestamp = (
        Transaction.all_objects
        .filter(
            portfolio=pnl.portfolio,
            stock=pnl.stock,
            transaction_type=Transaction.TransactionType.BUY,
            timestamp__lte=sell_timestamp,
        )
        .order_by('timestamp')
        .values_list('timestamp', flat=True)
        .first()
    )
    return buy_timestamp or acquisition_date


def _convert_transaction_total(transaction, target_currency):
    return _to_decimal(
        get_transaction_amount_in_currency(
            transaction,
            target_currency,
            snapshot_date=transaction.timestamp.date(),
        )
    )


def _convert_base_amount(amount, portfolio, target_currency, *, snapshot_date):
    if target_currency == portfolio.base_currency:
        return _to_decimal(amount)

    return _to_decimal(convert_amount(
        amount,
        portfolio.base_currency,
        target_currency,
        snapshot_date=snapshot_date,
        session='cierre',
    ))


def _build_display_metrics(portfolio, pnls, target_currency, *, date_to):
    pnl_by_transaction_id = {pnl.transaction_id: pnl for pnl in pnls}
    stock_ids = {pnl.stock_id for pnl in pnls}
    transactions = (
        Transaction.all_objects
        .filter(
            portfolio=portfolio,
            stock_id__in=stock_ids,
            transaction_type__in=(
                Transaction.TransactionType.BUY,
                Transaction.TransactionType.SELL,
            ),
            timestamp__date__lte=date_to,
        )
        .select_related('stock')
        .order_by('timestamp', 'id')
    )

    running = defaultdict(lambda: {
        'quantity': Decimal('0'),
        'cost': Decimal('0.00'),
    })
    sell_metrics = {}

    for transaction in transactions:
        stock_state = running[transaction.stock_id]
        quantity = Decimal(transaction.quantity or 0)
        if quantity <= 0:
            continue

        if transaction.transaction_type == Transaction.TransactionType.BUY:
            stock_state['quantity'] += quantity
            stock_state['cost'] += _convert_transaction_total(transaction, target_currency)
            stock_state['cost'] = _to_decimal(stock_state['cost'])
            continue

        proceeds = _convert_transaction_total(transaction, target_currency)
        if stock_state['quantity'] > 0:
            avg_cost = stock_state['cost'] / stock_state['quantity']
            cost_basis = _to_decimal(avg_cost * quantity)
        else:
            pnl = pnl_by_transaction_id.get(transaction.id)
            fallback_base_cost = (pnl.purchase_price * quantity) if pnl else Decimal('0.00')
            cost_basis = _convert_base_amount(
                fallback_base_cost,
                portfolio,
                target_currency,
                snapshot_date=transaction.timestamp.date(),
            )

        net = _to_decimal(proceeds - cost_basis)
        closing_price = _to_decimal(proceeds / quantity) if quantity else Decimal('0.00')
        sell_metrics[transaction.id] = {
            'proceeds': proceeds,
            'cost_basis': cost_basis,
            'net': net,
            'closing_price': closing_price,
        }

        if stock_state['quantity'] > 0:
            stock_state['quantity'] -= quantity
            stock_state['cost'] -= cost_basis
            if stock_state['quantity'] <= 0 or abs(stock_state['cost']) < Decimal('0.01'):
                stock_state['quantity'] = Decimal('0')
                stock_state['cost'] = Decimal('0.00')
            else:
                stock_state['cost'] = _to_decimal(stock_state['cost'])

    return sell_metrics


def _init_native_summary():
    return {
        currency: {
            'proceeds': Decimal('0.00'),
            'cost_basis': Decimal('0.00'),
            'net_gain': Decimal('0.00'),
            'long_term': Decimal('0.00'),
            'short_term': Decimal('0.00'),
            'gains': Decimal('0.00'),
            'losses': Decimal('0.00'),
        }
        for currency in ('PEN', 'USD')
    }


class PortfolioRealizedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, portfolio_id):
        portfolio = get_object_or_404(
            Portfolio.objects.filter(user=request.user),
            pk=portfolio_id
        )

        today = timezone.now().date()
        current_year_start = datetime(today.year, 1, 1).date()

        requested_display_currency = request.query_params.get('display_currency')
        try:
            display_mode = normalize_currency(
                requested_display_currency,
                default=get_portfolio_reporting_currency(portfolio),
                allow_native=True,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        summary_currency = (
            get_portfolio_reporting_currency(portfolio)
            if display_mode == DISPLAY_CURRENCY_NATIVE
            else display_mode
        )

        from_param = request.query_params.get('from')
        to_param = request.query_params.get('to')

        try:
            date_from = datetime.strptime(from_param, '%Y-%m-%d').date() if from_param else current_year_start
        except ValueError:
            return Response({'detail': 'Formato inválido para "from". Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            date_to = datetime.strptime(to_param, '%Y-%m-%d').date() if to_param else today
        except ValueError:
            return Response({'detail': 'Formato inválido para "to". Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        if date_from > date_to:
            return Response({'detail': '"from" debe ser anterior o igual a "to".'}, status=status.HTTP_400_BAD_REQUEST)

        symbol = request.query_params.get('symbol')

        pnls = (
            RealizedPNL.objects
            .filter(
                portfolio=portfolio,
                transaction__timestamp__date__gte=date_from,
                transaction__timestamp__date__lte=date_to,
            )
            .select_related('transaction__stock', 'stock')
            .order_by('-transaction__timestamp', '-id')
        )

        if symbol:
            pnls = pnls.filter(stock__symbol__iexact=symbol.strip())

        if not pnls.exists():
            payload = {
                'display_currency': summary_currency,
                'display_currency_mode': display_mode,
                'summary_currency': summary_currency,
                'native_summary': {
                    currency: {key: '0.00' for key in values.keys()}
                    for currency, values in _init_native_summary().items()
                },
                'period': {'from': date_from.isoformat(), 'to': date_to.isoformat()},
                'totals': {
                    'proceeds': '0.00',
                    'cost_basis': '0.00',
                    'net_gain': '0.00',
                    'gain_pct': '0.00',
                },
                'long_short': {
                    'long_term': '0.00',
                    'short_term': '0.00',
                },
                'counts': {
                    'gain': 0,
                    'loss': 0,
                },
                'averages': {
                    'gain_pct': '0.00',
                    'loss_pct': '0.00',
                },
                'chart': [],
                'details': [],
            }
            return Response(payload, status=status.HTTP_200_OK)

        totals = {
            'proceeds': Decimal('0.00'),
            'cost_basis': Decimal('0.00'),
            'net_gain': Decimal('0.00'),
        }
        long_short = {
            'long_term': Decimal('0.00'),
            'short_term': Decimal('0.00'),
        }
        counts = {'gain': 0, 'loss': 0}
        chart_data = defaultdict(lambda: Decimal('0.00'))
        details = []
        gain_pct_sum = Decimal('0.00')
        loss_pct_sum = Decimal('0.00')
        native_summary = _init_native_summary()
        pnl_list = list(pnls)
        summary_metrics = _build_display_metrics(portfolio, pnl_list, summary_currency, date_to=date_to)
        if display_mode == DISPLAY_CURRENCY_NATIVE:
            native_metrics_by_currency = {}
            pnls_by_currency = defaultdict(list)
            for pnl in pnl_list:
                native_currency = get_transaction_original_currency(pnl.transaction)
                pnls_by_currency[native_currency].append(pnl)
            for native_currency, currency_pnls in pnls_by_currency.items():
                native_metrics_by_currency[native_currency] = _build_display_metrics(
                    portfolio,
                    currency_pnls,
                    native_currency,
                    date_to=date_to,
                )
        else:
            native_metrics_by_currency = {}

        for pnl in pnl_list:
            quantity = Decimal(pnl.quantity)
            summary_metric = summary_metrics.get(pnl.transaction_id)
            row_currency = summary_currency
            if display_mode == DISPLAY_CURRENCY_NATIVE:
                row_currency = get_transaction_original_currency(pnl.transaction)
                row_metric = native_metrics_by_currency.get(row_currency, {}).get(pnl.transaction_id)
            else:
                row_metric = summary_metric

            if summary_metric:
                summary_proceeds = summary_metric['proceeds']
                summary_cost_basis = summary_metric['cost_basis']
                summary_net = summary_metric['net']
            else:
                summary_proceeds = _convert_base_amount(
                    pnl.sell_price * quantity,
                    portfolio,
                    summary_currency,
                    snapshot_date=pnl.transaction.timestamp.date(),
                )
                summary_cost_basis = _convert_base_amount(
                    pnl.purchase_price * quantity,
                    portfolio,
                    summary_currency,
                    snapshot_date=pnl.transaction.timestamp.date(),
                )
                summary_net = _to_decimal(summary_proceeds - summary_cost_basis)

            if row_metric:
                proceeds = row_metric['proceeds']
                cost_basis = row_metric['cost_basis']
                net = row_metric['net']
                closing_price = row_metric['closing_price']
            else:
                proceeds = _convert_base_amount(
                    pnl.sell_price * quantity,
                    portfolio,
                    row_currency,
                    snapshot_date=pnl.transaction.timestamp.date(),
                )
                cost_basis = _convert_base_amount(
                    pnl.purchase_price * quantity,
                    portfolio,
                    row_currency,
                    snapshot_date=pnl.transaction.timestamp.date(),
                )
                net = _to_decimal(proceeds - cost_basis)
                closing_price = _to_decimal(proceeds / quantity) if quantity else Decimal('0.00')

            totals['proceeds'] += summary_proceeds
            totals['cost_basis'] += summary_cost_basis
            totals['net_gain'] += summary_net
            native_summary[row_currency]['proceeds'] += proceeds
            native_summary[row_currency]['cost_basis'] += cost_basis
            native_summary[row_currency]['net_gain'] += net

            # Calculate holding period and classify as long-term or short-term
            is_long_term = False
            long_term_gain = Decimal('0.00')
            short_term_gain = Decimal('0.00')
            summary_long_term_gain = Decimal('0.00')
            summary_short_term_gain = Decimal('0.00')

            acquisition_date = _resolve_acquisition_date(pnl)
            if acquisition_date:
                sell_date = pnl.transaction.timestamp
                holding_days = (sell_date - acquisition_date).days

                # Long-term if held for 365 days or more
                if holding_days >= 365:
                    is_long_term = True
                    long_term_gain = net
                    summary_long_term_gain = summary_net
                    long_short['long_term'] += summary_net
                    native_summary[row_currency]['long_term'] += net
                else:
                    short_term_gain = net
                    summary_short_term_gain = summary_net
                    long_short['short_term'] += summary_net
                    native_summary[row_currency]['short_term'] += net
            else:
                # If no acquisition date, assume short-term (conservative approach)
                short_term_gain = net
                summary_short_term_gain = summary_net
                long_short['short_term'] += summary_net
                native_summary[row_currency]['short_term'] += net

            txn_pct = Decimal('0.00')
            if cost_basis != Decimal('0.00'):
                txn_pct = (net / cost_basis * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if summary_net >= 0:
                counts['gain'] += 1
                gain_pct_sum += txn_pct
            else:
                counts['loss'] += 1
                loss_pct_sum += txn_pct

            if net >= 0:
                native_summary[row_currency]['gains'] += net
            else:
                native_summary[row_currency]['losses'] += net

            closed_date = pnl.transaction.timestamp.date()
            chart_data[closed_date] += summary_net

            details.append({
                'symbol': pnl.stock.symbol,
                'description': pnl.stock.name,
                'closed_date': pnl.transaction.timestamp.isoformat(),
                'acquisition_date': acquisition_date.isoformat() if acquisition_date else None,
                'holding_days': holding_days if acquisition_date else None,
                'quantity': pnl.quantity,
                'display_currency': row_currency,
                'closing_price': str(_to_decimal(closing_price)),
                'cost_basis_method': 'Average Cost',
                'proceeds': str(_to_decimal(proceeds)),
                'cost_basis': str(_to_decimal(cost_basis)),
                'total': str(_to_decimal(net)),
                'long_term': str(_to_decimal(long_term_gain)),
                'short_term': str(_to_decimal(short_term_gain)),
                'chart_total': str(_to_decimal(summary_net)),
                'chart_cost_basis': str(_to_decimal(summary_cost_basis)),
                'summary_currency': summary_currency,
            })

        gain_pct = (
            (_to_decimal(totals['net_gain']) / _to_decimal(totals['cost_basis']) * Decimal('100'))
            if totals['cost_basis'] != Decimal('0.00')
            else Decimal('0.00')
        )

        avg_gain_pct = (
            (gain_pct_sum / counts['gain']) if counts['gain'] > 0 else Decimal('0.00')
        )
        avg_loss_pct = (
            (loss_pct_sum / counts['loss']) if counts['loss'] > 0 else Decimal('0.00')
        )

        payload = {
            'display_currency': summary_currency,
            'display_currency_mode': display_mode,
            'summary_currency': summary_currency,
            'native_summary': {
                currency: {
                    key: str(_to_decimal(value))
                    for key, value in values.items()
                }
                for currency, values in native_summary.items()
            },
            'period': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat(),
            },
            'totals': {
                'proceeds': str(_to_decimal(totals['proceeds'])),
                'cost_basis': str(_to_decimal(totals['cost_basis'])),
                'net_gain': str(_to_decimal(totals['net_gain'])),
                'gain_pct': str(_to_decimal(gain_pct)),
            },
            'long_short': {
                'long_term': str(_to_decimal(long_short['long_term'])),
                'short_term': str(_to_decimal(long_short['short_term'])),
            },
            'counts': counts,
            'averages': {
                'gain_pct': str(_to_decimal(avg_gain_pct)),
                'loss_pct': str(_to_decimal(avg_loss_pct)),
            },
            'chart': [
                {'date': day.isoformat(), 'net': str(_to_decimal(value))}
                for day, value in sorted(chart_data.items())
            ],
            'details': details,
        }
        return Response(payload, status=status.HTTP_200_OK)
