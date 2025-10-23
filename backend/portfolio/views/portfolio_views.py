from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response

from portfolio.models import Portfolio, Holding, PortfolioPerformance, Transaction
from portfolio.services.transaction_service import TransactionService
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
        # Require initial_deposit on creation
        raw_amount = self.request.data.get('initial_deposit')
        if raw_amount in (None, ''):
            raise ValidationError({'initial_deposit': 'Initial deposit is required.'})
        try:
            amount = Decimal(str(raw_amount))
        except Exception:
            raise ValidationError({'initial_deposit': 'Invalid amount format.'})
        if amount <= Decimal('0'):
            raise ValidationError({'initial_deposit': 'Initial deposit must be greater than 0.'})

        # Create portfolio, then create a DEPOSIT transaction to fund it
        portfolio = serializer.save(user=self.request.user, is_default=False)
        tx_data = {
            'portfolio': portfolio,
            'idempotency_key': uuid.uuid4(),
            'transaction_type': Transaction.TransactionType.DEPOSIT,
            'amount': amount,
        }
        TransactionService.execute_transaction(tx_data)


class PortfolioDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PortfolioDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(
            user=self.request.user
        ).select_related('performance').prefetch_related(
            Prefetch(
                'holdings',
                queryset=Holding.objects.filter(is_active=True).select_related('stock')
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
        return Holding.objects.filter(
            portfolio=portfolio,
            is_active=True
        ).select_related('stock')


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
