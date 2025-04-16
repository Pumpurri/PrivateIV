# backend/portfolio/urls.py
from django.urls import path
from backend.portfolio.views.transaction_views import TransactionHistoryView

urlpatterns = [
    path(
        'transactions/',
        TransactionHistoryView.as_view(),
        name='transaction-history'
    ),
]