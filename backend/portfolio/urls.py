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
)

urlpatterns = [
    # Portfolio endpoints
    path('portfolios/', PortfolioListView.as_view(), name='portfolio-list'),
    path('portfolios/<int:pk>/', PortfolioDetailView.as_view(), name='portfolio-detail'),
    path('portfolios/<int:portfolio_id>/holdings/', PortfolioHoldingsView.as_view(), name='portfolio-holdings'),
    path('portfolios/<int:portfolio_id>/performance/', PortfolioPerformanceView.as_view(), name='portfolio-performance'),
    
    # Transaction endpoints
    path('transactions/', TransactionListView.as_view(), name='transaction-list'),
    path('transactions/create/', TransactionCreateView.as_view(), name='transaction-create'),
    path('transactions/<uuid:pk>/', TransactionDetailView.as_view(), name='transaction-detail'),
]