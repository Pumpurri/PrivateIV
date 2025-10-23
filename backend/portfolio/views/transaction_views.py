# backend/portfolio/views/transaction_views.py
import logging
import os
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import APIException, PermissionDenied
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

    def get_queryset(self):
        qs = Transaction.objects.filter(
            portfolio__user=self.request.user,
            portfolio__is_deleted=False
        ).select_related('stock', 'portfolio')

        portfolio_id = self.request.query_params.get('portfolio')
        if portfolio_id:
            qs = qs.filter(portfolio_id=portfolio_id)

        return qs


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
            portfolio = None
            if portfolio_id:
                try:
                    portfolio = qs.get(pk=int(portfolio_id))
                except (ValueError, Portfolio.DoesNotExist):
                    portfolio = None
            if portfolio is None:
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
