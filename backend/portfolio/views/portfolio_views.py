from rest_framework import generics, permissions, status
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response

from portfolio.models import Portfolio, Holding, PortfolioPerformance
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
        # Always create with current user and cash_balance=0 via model default.
        # Do not allow clients to set is_default here; selection is via dedicated endpoint.
        serializer.save(user=self.request.user, is_default=False)


class PortfolioDetailView(generics.RetrieveUpdateAPIView):
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
