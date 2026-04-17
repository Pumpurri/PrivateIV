# backend/portfolio/views/transaction_views.py
import logging
import os
from datetime import datetime, time
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError as DRFValidationError
from rest_framework.throttling import UserRateThrottle

from portfolio.models import Portfolio, Transaction
from portfolio.serializers.transaction_serializers import TransactionSerializer
from portfolio.services.currency_service import (
    get_portfolio_reporting_currency,
    get_transaction_amount_in_currency,
    normalize_currency,
)
from portfolio.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

# Optional Datadog custom spans
if os.getenv('DD_TRACE_ENABLED', 'false').lower() == 'true':
    from ddtrace import tracer
else:
    tracer = None

class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _parse_portfolio_id(self):
        portfolio_id = self.request.query_params.get('portfolio')
        if not portfolio_id:
            return None
        try:
            parsed_id = int(portfolio_id)
        except (TypeError, ValueError):
            raise DRFValidationError({'portfolio': 'Portfolio must be a valid integer id.'})
        if parsed_id <= 0:
            raise DRFValidationError({'portfolio': 'Portfolio must be a positive integer id.'})
        return parsed_id

    def _parse_transaction_types(self):
        raw_type = self.request.query_params.get('type') or self.request.query_params.get('transaction_type')
        if not raw_type:
            return None

        requested = [item.strip().upper() for item in raw_type.split(',') if item.strip()]
        valid_types = {choice.value for choice in Transaction.TransactionType}
        invalid = [item for item in requested if item not in valid_types]
        if invalid:
            raise DRFValidationError({
                'type': f"Invalid transaction type(s): {', '.join(invalid)}"
            })
        return requested

    def _parse_datetime_filter(self, param_name, *, end_of_day=False):
        value = self.request.query_params.get(param_name)
        if not value:
            return None

        parsed = parse_datetime(value)
        if parsed is None:
            parsed_date = parse_date(value)
            if parsed_date is None:
                raise DRFValidationError({param_name: 'Use YYYY-MM-DD or ISO 8601 datetime.'})
            parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min)

        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def _parse_currency(self, param_name, *, required=False):
        value = self.request.query_params.get(param_name)
        if not value:
            if required:
                raise DRFValidationError({param_name: 'Currency is required.'})
            return None
        try:
            return normalize_currency(value)
        except ValueError as exc:
            raise DRFValidationError({param_name: str(exc)}) from exc

    def get_queryset(self):
        qs = Transaction.objects.filter(
            portfolio__user=self.request.user,
            portfolio__is_deleted=False
        ).select_related('stock', 'portfolio')

        portfolio_id = self._parse_portfolio_id()
        if portfolio_id is not None:
            qs = qs.filter(portfolio_id=portfolio_id)

        transaction_types = self._parse_transaction_types()
        if transaction_types:
            qs = qs.filter(transaction_type__in=transaction_types)

        symbol = self.request.query_params.get('symbol')
        if symbol:
            qs = qs.filter(stock__symbol__iexact=symbol.strip())

        currency = self._parse_currency('currency')
        if currency:
            qs = qs.filter(
                Q(transaction_type__in=[Transaction.TransactionType.BUY, Transaction.TransactionType.SELL], stock__currency=currency)
                | Q(transaction_type__in=[Transaction.TransactionType.DEPOSIT, Transaction.TransactionType.WITHDRAWAL], cash_currency=currency)
                | Q(transaction_type=Transaction.TransactionType.CONVERT, cash_currency=currency)
                | Q(transaction_type=Transaction.TransactionType.CONVERT, counter_currency=currency)
            )

        date_from = (
            self._parse_datetime_filter('date_from')
            or self._parse_datetime_filter('from')
        )
        if date_from:
            qs = qs.filter(timestamp__gte=date_from)

        date_to = (
            self._parse_datetime_filter('date_to', end_of_day=True)
            or self._parse_datetime_filter('to', end_of_day=True)
        )
        if date_to:
            qs = qs.filter(timestamp__lte=date_to)

        return qs

    @staticmethod
    def _format_decimal(value):
        return f"{(value or Decimal('0.00')):.2f}"

    @classmethod
    def _build_totals(cls, queryset, *, display_currency, currency_filter=None):
        total_count = queryset.count()
        total_quantity = sum(int(tx.quantity or 0) for tx in queryset)
        total_amount_display = Decimal('0.00')
        total_amount_native = Decimal('0.00')
        total_amount_pen = Decimal('0.00')

        by_type = {
            choice.value: {
                'count': 0,
                'amount': '0.00',
                'amount_native': '0.00',
                'amount_base': '0.00',
                'amount_display': '0.00',
                'display_currency': display_currency,
                'quantity': 0,
            }
            for choice in Transaction.TransactionType
        }

        for tx in queryset:
            display_amount = get_transaction_amount_in_currency(
                tx,
                display_currency,
                use_counter_amount=bool(currency_filter and tx.transaction_type == Transaction.TransactionType.CONVERT and tx.counter_currency == currency_filter),
                snapshot_date=tx.timestamp.date(),
            )
            pen_amount = get_transaction_amount_in_currency(
                tx,
                'PEN',
                snapshot_date=tx.timestamp.date(),
            )
            native_amount = Decimal(tx.amount or '0.00')

            total_amount_display += display_amount
            total_amount_native += native_amount
            total_amount_pen += pen_amount

            bucket = by_type[tx.transaction_type]
            bucket['count'] += 1
            bucket['quantity'] += int(tx.quantity or 0)
            bucket['amount_native'] = cls._format_decimal(Decimal(bucket['amount_native']) + native_amount)
            bucket['amount_base'] = cls._format_decimal(Decimal(bucket['amount_base']) + pen_amount)
            bucket['amount_display'] = cls._format_decimal(Decimal(bucket['amount_display']) + display_amount)
            bucket['amount'] = bucket['amount_native']

        deposit_base = Decimal(by_type[Transaction.TransactionType.DEPOSIT]['amount_base'])
        withdrawal_base = Decimal(by_type[Transaction.TransactionType.WITHDRAWAL]['amount_base'])

        return {
            'count': total_count,
            'amount': cls._format_decimal(total_amount_native),
            'amount_native': cls._format_decimal(total_amount_native),
            'amount_base': cls._format_decimal(total_amount_pen),
            'amount_display': cls._format_decimal(total_amount_display),
            'display_currency': display_currency,
            'quantity': total_quantity,
            'net_cash_flow': cls._format_decimal(deposit_base - withdrawal_base),
            'by_type': by_type,
        }

    def _resolve_display_currency(self, queryset):
        explicit = self._parse_currency('display_currency')
        if explicit:
            return explicit

        currency_filter = self._parse_currency('currency')
        if currency_filter:
            return currency_filter

        portfolio_id = self._parse_portfolio_id()
        if portfolio_id is not None:
            portfolio = Portfolio.objects.filter(user=self.request.user, pk=portfolio_id).only('reporting_currency').first()
            if portfolio:
                return get_portfolio_reporting_currency(portfolio)

        default_portfolio = self.request.user.portfolios.filter(is_default=True, is_deleted=False).only('reporting_currency').first()
        if default_portfolio:
            return get_portfolio_reporting_currency(default_portfolio)
        return 'PEN'

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        display_currency = self._resolve_display_currency(queryset)
        currency_filter = self._parse_currency('currency')
        totals = self._build_totals(queryset, display_currency=display_currency, currency_filter=currency_filter)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={**self.get_serializer_context(), 'display_currency': display_currency})
            response = self.get_paginated_response(serializer.data)
            response.data['totals'] = totals
            response.data['display_currency'] = display_currency
            return response

        serializer = self.get_serializer(queryset, many=True, context={**self.get_serializer_context(), 'display_currency': display_currency})
        return Response({
            'results': serializer.data,
            'totals': totals,
            'display_currency': display_currency,
        })


class TransactionCreateView(generics.CreateAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def handle_exception(self, exc):
        if isinstance(exc, (ValidationError, PermissionDenied)):
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)

    def perform_create(self, serializer):
        if tracer:
            with tracer.trace('transaction.create', service='tradesimulator') as span:
                span.set_tag('user.id', self.request.user.id)
                span.set_tag('transaction.type', serializer.validated_data.get('transaction_type'))
                self._execute_transaction(serializer)
        else:
            self._execute_transaction(serializer)
    
    def _execute_transaction(self, serializer):
        try:
            # Prefer explicit portfolio_id if provided and owned by the user; fallback to default
            portfolio_id = self.request.data.get('portfolio_id')
            qs = self.request.user.portfolios.filter(is_deleted=False)
            if portfolio_id:
                try:
                    portfolio = qs.get(pk=int(portfolio_id))
                except (ValueError, Portfolio.DoesNotExist):
                    raise ValidationError("Invalid or inaccessible portfolio_id")
            else:
                portfolio = qs.get(is_default=True)

            txn = TransactionService.execute_transaction({
                **serializer.validated_data,
                'portfolio': portfolio
            })
            serializer.instance = txn
        except Portfolio.DoesNotExist:
            raise ValidationError("User has no default portfolio")
        except DatabaseError as e:
            logger.error(f"Transaction database error: {e}")
            raise APIException("Failed to process transaction")


class TransactionDetailView(generics.RetrieveAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(
            portfolio__user=self.request.user,
            portfolio__is_deleted=False
        ).select_related('stock', 'portfolio')
