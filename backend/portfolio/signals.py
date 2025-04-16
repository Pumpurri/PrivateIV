from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import CustomUser
from portfolio.models import Portfolio
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