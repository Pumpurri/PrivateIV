from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response

from portfolio.models import Portfolio, Holding, PortfolioPerformance, Transaction
from portfolio.services.currency_service import get_portfolio_reporting_currency, normalize_currency
from portfolio.services.fx_service import get_current_fx_context
from portfolio.services.position_metrics_service import get_holding_metrics
from portfolio.services.transaction_service import TransactionService
from stocks.market import previous_business_day
from decimal import Decimal
import uuid
from portfolio.serializers import (
    PortfolioSerializer,
    PortfolioDetailSerializer,
    HoldingSerializer,
    PortfolioPerformanceSerializer
)


class PortfolioListView(generics.ListCreateAPIView):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(
            user=self.request.user
        ).select_related('performance').prefetch_related('holdings')

    def perform_create(self, serializer):
        def _parse_amount(field, raw):
            if raw in (None, ''):
                return Decimal('0')
            try:
                amt = Decimal(str(raw))
            except Exception:
                raise ValidationError({field: 'Invalid amount format.'})
            if amt < Decimal('0'):
                raise ValidationError({field: 'Amount cannot be negative.'})
            return amt

        pen_amount = _parse_amount('initial_deposit_pen', self.request.data.get('initial_deposit_pen'))
        usd_amount = _parse_amount('initial_deposit_usd', self.request.data.get('initial_deposit_usd'))

        deposits = []
        if pen_amount > 0:
            deposits.append((pen_amount, 'PEN'))
        if usd_amount > 0:
            deposits.append((usd_amount, 'USD'))

        # Legacy single-deposit path (kept for backward compatibility with existing clients/tests).
        if not deposits:
            raw_legacy = self.request.data.get('initial_deposit')
            if raw_legacy not in (None, ''):
                legacy_amount = _parse_amount('initial_deposit', raw_legacy)
                if legacy_amount <= Decimal('0'):
                    raise ValidationError({'initial_deposit': 'Initial deposit must be greater than 0.'})
                raw_currency = self.request.data.get('initial_deposit_currency')
                try:
                    legacy_currency = normalize_currency(raw_currency) if raw_currency else None
                except ValueError as exc:
                    raise ValidationError({'initial_deposit_currency': str(exc)}) from exc
                deposits.append((legacy_amount, legacy_currency))

        if not deposits:
            raise ValidationError({'initial_deposit_pen': 'Provide an initial deposit in PEN or USD.'})

        # Create portfolio and initial funding as one unit.
        with transaction.atomic():
            portfolio = serializer.save(user=self.request.user, is_default=False)
            for amount, currency in deposits:
                deposit_currency = currency or get_portfolio_reporting_currency(portfolio)
                TransactionService.execute_transaction({
                    'portfolio': portfolio,
                    'idempotency_key': uuid.uuid4(),
                    'transaction_type': Transaction.TransactionType.DEPOSIT,
                    'amount': amount,
                    'cash_currency': deposit_currency,
                })


class PortfolioDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PortfolioDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
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
        return Portfolio.objects.filter(
            user=self.request.user
        ).select_related('performance').prefetch_related(
            Prefetch(
                'holdings',
                queryset=Holding.objects.filter(is_active=True).select_related('stock', 'portfolio').prefetch_related(trade_prefetch)
            )
        )

    def get_object(self):
        portfolio = get_object_or_404(self.get_queryset(), pk=self.kwargs['pk'])
        return portfolio


class PortfolioHoldingsView(generics.ListAPIView):
    serializer_class = HoldingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        portfolio_id = self.kwargs['portfolio_id']
        portfolio = get_object_or_404(
            Portfolio.objects.filter(user=self.request.user), 
            pk=portfolio_id
        )
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
        return Holding.objects.filter(
            portfolio=portfolio,
            is_active=True
        ).select_related('stock', 'portfolio').prefetch_related(trade_prefetch)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        display_currency = self.request.query_params.get('display_currency')
        if display_currency:
            try:
                context['display_currency'] = normalize_currency(display_currency, allow_native=True)
            except ValueError as exc:
                raise ValidationError({'display_currency': str(exc)}) from exc
        return context

    def _resolve_display_mode(self):
        display_currency = self.request.query_params.get('display_currency')
        if display_currency:
            try:
                return normalize_currency(display_currency, allow_native=True)
            except ValueError as exc:
                raise ValidationError({'display_currency': str(exc)}) from exc
        return None

    def _resolve_summary_currency(self, portfolio):
        display_mode = self._resolve_display_mode()
        if display_mode and display_mode != 'NATIVE':
            return display_mode
        return get_portfolio_reporting_currency(portfolio)

    def _build_summary(self, portfolio, holdings):
        summary_currency = self._resolve_summary_currency(portfolio)
        total_cost_basis = Decimal('0.00')
        total_day_change = Decimal('0.00')
        total_gain_loss = Decimal('0.00')
        total_investment_value = Decimal('0.00')

        for holding in holdings:
            metrics = get_holding_metrics(holding, display_currency=summary_currency)
            total_cost_basis += Decimal(metrics['cost_basis'] or '0.00')
            total_day_change += Decimal(metrics['day_change'] or '0.00')
            total_gain_loss += Decimal(metrics['gain_loss'] or '0.00')
            total_investment_value += Decimal(metrics['current_value'] or '0.00')

        total_cash = portfolio.get_total_cash_balance(summary_currency)
        current_fx_date, _ = get_current_fx_context()
        previous_fx_date = previous_business_day(current_fx_date)
        previous_cash = portfolio.get_total_cash_balance(
            summary_currency,
            snapshot_date=previous_fx_date,
            session='cierre',
        )
        cash_day_change = total_cash - previous_cash
        total_day_change += cash_day_change
        total_value = (total_cash + total_investment_value).quantize(Decimal('0.01'))
        total_day_baseline = total_value - total_day_change
        total_day_change_pct = Decimal('0.00')
        if total_day_baseline:
            total_day_change_pct = (total_day_change / total_day_baseline * Decimal('100')).quantize(Decimal('0.01'))

        total_gain_loss_pct = Decimal('0.00')
        if total_cost_basis:
            total_gain_loss_pct = (total_gain_loss / total_cost_basis * Decimal('100')).quantize(Decimal('0.01'))

        return {
            'summary_currency': summary_currency,
            'cash_balance': total_cash.quantize(Decimal('0.01')),
            'current_investment_value': total_investment_value.quantize(Decimal('0.01')),
            'total_value': total_value,
            'cost_basis': total_cost_basis.quantize(Decimal('0.01')),
            'day_change': total_day_change.quantize(Decimal('0.01')),
            'day_change_percentage': total_day_change_pct,
            'gain_loss': total_gain_loss.quantize(Decimal('0.01')),
            'gain_loss_percentage': total_gain_loss_pct,
        }

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        holdings = list(queryset)
        serializer = self.get_serializer(holdings, many=True)
        portfolio = holdings[0].portfolio if holdings else get_object_or_404(
            Portfolio.objects.filter(user=request.user),
            pk=self.kwargs['portfolio_id'],
        )
        display_mode = self._resolve_display_mode()
        summary = self._build_summary(portfolio, holdings)
        return Response({
            'results': serializer.data,
            'summary': summary,
            'display_currency': summary['summary_currency'],
            'display_currency_mode': display_mode or get_portfolio_reporting_currency(portfolio),
            'reporting_currency': get_portfolio_reporting_currency(portfolio),
        })


class PortfolioPerformanceView(generics.RetrieveAPIView):
    serializer_class = PortfolioPerformanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        portfolio_id = self.kwargs['portfolio_id']
        portfolio = get_object_or_404(
            Portfolio.objects.filter(user=self.request.user),
            pk=portfolio_id
        )
        performance, _ = PortfolioPerformance.objects.get_or_create(
            portfolio=portfolio
        )
        return performance


class PortfolioSetDefaultView(APIView):
    """Set a given portfolio as the user's default portfolio."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, portfolio_id):
        # Ensure the portfolio belongs to the authenticated user
        portfolio = get_object_or_404(
            Portfolio.objects.filter(user=request.user, is_deleted=False),
            pk=portfolio_id
        )
        with transaction.atomic():
            # Lock user's active portfolios to avoid race conditions
            user_portfolios = Portfolio.objects.select_for_update().filter(
                user=request.user,
                is_deleted=False
            )
            # Unset current default(s)
            user_portfolios.update(is_default=False)
            # Set requested one as default
            Portfolio.objects.filter(pk=portfolio.pk).update(is_default=True)
            portfolio.refresh_from_db()
        return Response({'detail': 'Default portfolio updated', 'portfolio_id': portfolio.id}, status=status.HTTP_200_OK)
