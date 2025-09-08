# backend/portfolio/views/transaction_views.py
import logging
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
        try:
            portfolio = self.request.user.portfolios.get(is_default=True)
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
