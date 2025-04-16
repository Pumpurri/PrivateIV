from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from portfolio.models import Transaction
from portfolio.serializers.transaction_serializers import TransactionSerializer
from rest_framework.pagination import PageNumberPagination

class TransactionPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class TransactionHistoryView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = TransactionPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = {
        'portfolio': ['exact'],
        'transaction_type': ['exact'],
        'stock__symbol': ['exact']
    }
    ordering_fields = ['timestamp', 'amount']
    ordering = ['-timestamp']

    def get_queryset(self):
        return Transaction.objects.filter(
            portfolio__user=self.request.user
        ).select_related('stock', 'portfolio').prefetch_related('portfolio__user')