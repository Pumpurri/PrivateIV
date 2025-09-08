from rest_framework import generics, permissions
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch

from portfolio.models import Portfolio, Holding, PortfolioPerformance
from portfolio.serializers import (
    PortfolioSerializer,
    PortfolioDetailSerializer,
    HoldingSerializer,
    PortfolioPerformanceSerializer
)


class PortfolioListView(generics.ListAPIView):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(
            user=self.request.user
        ).select_related('performance').prefetch_related('holdings')


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