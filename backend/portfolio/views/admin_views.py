from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.utils import timezone
from datetime import timedelta
from portfolio.models import Portfolio
from portfolio.models.daily_snapshot import DailyPortfolioSnapshot
from portfolio.services.snapshot_service import SnapshotService
import logging

logger = logging.getLogger(__name__)


class RegenerateSnapshotsView(APIView):
    """Admin endpoint to regenerate portfolio snapshots with corrected cash calculations"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Only allow staff/superuser to run this
        if not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {'error': 'Only staff users can regenerate snapshots'},
                status=status.HTTP_403_FORBIDDEN
            )

        portfolio_id = request.data.get('portfolio_id')
        days_back = request.data.get('days', 90)  # Default 90 days
        delete_existing = request.data.get('delete_existing', True)

        try:
            # Get the portfolio
            if portfolio_id:
                portfolio = Portfolio.objects.get(id=portfolio_id, user=request.user)
            else:
                portfolio = Portfolio.objects.filter(user=request.user).first()
                if not portfolio:
                    return Response(
                        {'error': 'No portfolio found'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Delete existing snapshots if requested
            deleted_count = 0
            if delete_existing:
                deleted_count = DailyPortfolioSnapshot.objects.filter(portfolio=portfolio).count()
                DailyPortfolioSnapshot.objects.filter(portfolio=portfolio).delete()
                logger.info(f'Deleted {deleted_count} existing snapshots for portfolio {portfolio.id}')

            # Determine date range
            today = timezone.now().date()
            start_date = today - timedelta(days=days_back)

            # Generate snapshots
            current_date = start_date
            success_count = 0
            errors = []

            while current_date <= today:
                try:
                    snapshot = SnapshotService.create_daily_snapshot(portfolio, current_date)
                    success_count += 1
                except Exception as e:
                    errors.append({
                        'date': str(current_date),
                        'error': str(e)
                    })
                    logger.error(f'Error creating snapshot for {current_date}: {e}')

                current_date += timedelta(days=1)

            return Response({
                'success': True,
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'deleted_count': deleted_count,
                'created_count': success_count,
                'errors': errors,
                'date_range': {
                    'start': str(start_date),
                    'end': str(today)
                },
                'current_state': {
                    'cash_balance': str(portfolio.cash_balance),
                    'total_value': str(portfolio.total_value),
                    'base_currency': portfolio.base_currency
                }
            }, status=status.HTTP_200_OK)

        except Portfolio.DoesNotExist:
            return Response(
                {'error': 'Portfolio not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f'Error regenerating snapshots: {e}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
