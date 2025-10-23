from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolio.models import Portfolio, RealizedPNL


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class PortfolioRealizedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, portfolio_id):
        portfolio = get_object_or_404(
            Portfolio.objects.filter(user=request.user),
            pk=portfolio_id
        )

        today = timezone.now().date()
        current_year_start = datetime(today.year, 1, 1).date()

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
                realized_at__date__gte=date_from,
                realized_at__date__lte=date_to,
            )
            .select_related('transaction__stock', 'stock')
        )

        if symbol:
            pnls = pnls.filter(stock__symbol__iexact=symbol.strip())

        if not pnls.exists():
            payload = {
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

        for pnl in pnls:
            quantity = Decimal(pnl.quantity)
            proceeds = pnl.sell_price * quantity
            cost_basis = pnl.purchase_price * quantity
            net = pnl.pnl

            totals['proceeds'] += proceeds
            totals['cost_basis'] += cost_basis
            totals['net_gain'] += net

            # Calculate holding period and classify as long-term or short-term
            is_long_term = False
            long_term_gain = Decimal('0.00')
            short_term_gain = Decimal('0.00')

            if pnl.acquisition_date:
                sell_date = pnl.transaction.timestamp
                acquisition_date = pnl.acquisition_date
                holding_days = (sell_date - acquisition_date).days

                # Long-term if held for 365 days or more
                if holding_days >= 365:
                    is_long_term = True
                    long_term_gain = net
                    long_short['long_term'] += net
                else:
                    short_term_gain = net
                    long_short['short_term'] += net
            else:
                # If no acquisition date, assume short-term (conservative approach)
                short_term_gain = net
                long_short['short_term'] += net

            txn_pct = Decimal('0.00')
            if cost_basis != Decimal('0.00'):
                txn_pct = (net / cost_basis * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if net >= 0:
                counts['gain'] += 1
                gain_pct_sum += txn_pct
            else:
                counts['loss'] += 1
                loss_pct_sum += txn_pct

            closed_date = pnl.transaction.timestamp.date()
            chart_data[closed_date] += net

            details.append({
                'symbol': pnl.stock.symbol,
                'description': pnl.stock.name,
                'closed_date': pnl.transaction.timestamp.isoformat(),
                'quantity': pnl.quantity,
                'closing_price': str(_to_decimal(pnl.sell_price)),
                'cost_basis_method': 'Average Cost',
                'proceeds': str(_to_decimal(proceeds)),
                'cost_basis': str(_to_decimal(cost_basis)),
                'total': str(_to_decimal(net)),
                'long_term': str(_to_decimal(long_term_gain)),
                'short_term': str(_to_decimal(short_term_gain)),
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
