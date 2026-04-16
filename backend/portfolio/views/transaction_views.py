# backend/portfolio/views/transaction_views.py
import logging
import os
from datetime import datetime, time
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.db.models import Count, Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError as DRFValidationError
from rest_framework.throttling import UserRateThrottle

from portfolio.models import Portfolio, Transaction
from portfolio.serializers.transaction_serializers import TransactionSerializer
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
    def _build_totals(cls, queryset):
        amount_base_expr = ExpressionWrapper(
            F('amount') * Coalesce(F('fx_rate'), 1),
            output_field=DecimalField(max_digits=20, decimal_places=6),
        )
        qs = queryset.annotate(amount_base=amount_base_expr)

        aggregate = qs.aggregate(
            total_count=Count('id'),
            total_amount=Sum('amount'),
            total_amount_base=Sum('amount_base'),
            total_quantity=Sum('quantity'),
        )

        by_type = {
            choice.value: {
                'count': 0,
                'amount_native': '0.00',
                'amount_base': '0.00',
                'quantity': 0,
            }
            for choice in Transaction.TransactionType
        }

        for row in qs.values('transaction_type').annotate(
            count=Count('id'),
            amount_native=Sum('amount'),
            amount_base=Sum('amount_base'),
            quantity=Sum('quantity'),
        ):
            by_type[row['transaction_type']] = {
                'count': row['count'],
                'amount_native': cls._format_decimal(row['amount_native']),
                'amount_base': cls._format_decimal(row['amount_base']),
                'quantity': row['quantity'] or 0,
            }

        deposit_base = Decimal(by_type[Transaction.TransactionType.DEPOSIT]['amount_base'])
        withdrawal_base = Decimal(by_type[Transaction.TransactionType.WITHDRAWAL]['amount_base'])

        return {
            'count': aggregate['total_count'],
            'amount_native': cls._format_decimal(aggregate['total_amount']),
            'amount_base': cls._format_decimal(aggregate['total_amount_base']),
            'quantity': aggregate['total_quantity'] or 0,
            'net_cash_flow': cls._format_decimal(deposit_base - withdrawal_base),
            'by_type': by_type,
        }

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        totals = self._build_totals(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['totals'] = totals
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'totals': totals,
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
