from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Stock, StockRefreshStatus
from .serializers import StockSerializer, StockRefreshStatusSerializer

class StockListCreateView(generics.ListCreateAPIView):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        status_obj = StockRefreshStatus.objects.order_by('-last_refreshed_at').first()
        if status_obj:
            last_refresh = status_obj.last_refreshed_at.isoformat()
            if isinstance(response.data, dict) and 'results' in response.data:
                response.data['last_refreshed_at'] = last_refresh
            else:
                response.data = {
                    'results': response.data,
                    'last_refreshed_at': last_refresh,
                }
        return response

class StockRetrieveUpdateView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAdminUser]


class StockRefreshStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        status_obj = StockRefreshStatus.objects.order_by('-last_refreshed_at').first()
        if not status_obj:
            status_obj = StockRefreshStatus.mark_refreshed()
        serializer = StockRefreshStatusSerializer(status_obj)
        return Response(serializer.data)
