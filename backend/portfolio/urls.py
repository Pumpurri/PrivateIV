# backend/portfolio/urls.py
from django.urls import path
from portfolio.views.transaction_views import (
    TransactionListView,
    TransactionCreateView,
    TransactionDetailView,
)

urlpatterns = [
    # List all transactions for the current user
    path('transactions/', TransactionListView.as_view(), name='transaction-list'),
    # Create a new transaction
    path('transactions/create/', TransactionCreateView.as_view(), name='transaction-create'),
    # Retrieve a single transaction by its UUID
    path('transactions/<uuid:pk>/', TransactionDetailView.as_view(), name='transaction-detail'),
]