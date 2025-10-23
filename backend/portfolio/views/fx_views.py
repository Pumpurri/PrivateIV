from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.utils import timezone
from portfolio.models import FXRate


class FXRateView(APIView):
    """Get current FX rates for USD->PEN conversion"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()

        # Get latest compra and venta rates
        compra = FXRate.objects.filter(
            base_currency='PEN',
            quote_currency='USD',
            rate_type='compra'
        ).order_by('-date').first()

        venta = FXRate.objects.filter(
            base_currency='PEN',
            quote_currency='USD',
            rate_type='venta'
        ).order_by('-date').first()

        mid = FXRate.objects.filter(
            base_currency='PEN',
            quote_currency='USD',
            rate_type='mid'
        ).order_by('-date').first()

        return Response({
            'compra': {
                'rate': str(compra.rate) if compra else None,
                'date': compra.date if compra else None,
                'session': compra.session if compra else None,
            },
            'venta': {
                'rate': str(venta.rate) if venta else None,
                'date': venta.date if venta else None,
                'session': venta.session if venta else None,
            },
            'mid': {
                'rate': str(mid.rate) if mid else None,
                'date': mid.date if mid else None,
                'session': mid.session if mid else None,
            }
        }, status=status.HTTP_200_OK)
