# backend/portfolio/urls.py
from django.urls import path
from portfolio.views import (
    # Transaction views
    TransactionListView,
    TransactionCreateView,
    TransactionDetailView,
    # Portfolio views
    PortfolioListView,
    PortfolioDetailView,
    PortfolioHoldingsView,
    PortfolioPerformanceView,
    PortfolioSetDefaultView,
    DashboardView,
    PortfolioOverviewView,
    # FX views
    FXRateView,
    PortfolioRealizedView,
)
from portfolio.views.admin_views import RegenerateSnapshotsView

urlpatterns = [
    # Dashboard endpoints
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/portfolios/<int:portfolio_id>/overview/', PortfolioOverviewView.as_view(), name='dashboard-portfolio-overview'),
    path('dashboard/portfolios/<int:portfolio_id>/realized/', PortfolioRealizedView.as_view(), name='dashboard-portfolio-realized'),
    # Portfolio endpoints
    path('portfolios/', PortfolioListView.as_view(), name='portfolio-list'),
    path('portfolios/<int:pk>/', PortfolioDetailView.as_view(), name='portfolio-detail'),
    path('portfolios/<int:portfolio_id>/holdings/', PortfolioHoldingsView.as_view(), name='portfolio-holdings'),
    path('portfolios/<int:portfolio_id>/performance/', PortfolioPerformanceView.as_view(), name='portfolio-performance'),
    path('portfolios/<int:portfolio_id>/set-default/', PortfolioSetDefaultView.as_view(), name='portfolio-set-default'),

    # Transaction endpoints
    path('transactions/', TransactionListView.as_view(), name='transaction-list'),
    path('transactions/create/', TransactionCreateView.as_view(), name='transaction-create'),
    path('transactions/<int:pk>/', TransactionDetailView.as_view(), name='transaction-detail'),

    # FX endpoints
    path('fx-rates/', FXRateView.as_view(), name='fx-rates'),

    # Admin endpoints
    path('admin/regenerate-snapshots/', RegenerateSnapshotsView.as_view(), name='admin-regenerate-snapshots'),
]
