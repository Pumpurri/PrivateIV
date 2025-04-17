from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import CustomUser
from portfolio.models import Portfolio, PortfolioPerformance
from decimal import Decimal
from django.conf import settings

@receiver(post_save, sender=CustomUser)
def create_default_portfolio(sender, instance, created, **kwargs):
    if getattr(settings, 'DISABLE_SIGNALS', False):
        return
    if created and not instance.portfolios.filter(is_default=True).exists():
        Portfolio.objects.create(
            user=instance,
            is_default=True,
            cash_balance=Decimal('10000.00')
        )

@receiver(post_save, sender=Portfolio)
def create_portfolio_performance(sender, instance, created, **kwargs):
    """Create performance tracking model for each new portfolio"""
    if created and not hasattr(instance, 'performance'):
        PortfolioPerformance.objects.create(portfolio=instance)