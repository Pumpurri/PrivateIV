from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import CustomUser
from portfolio.models import Portfolio, PortfolioPerformance, Transaction
from decimal import Decimal
from django.conf import settings
from portfolio.services.transaction_service import TransactionService
from uuid import uuid4

@receiver(post_save, sender=CustomUser)
def create_default_portfolio(sender, instance, created, **kwargs):
    if getattr(settings, 'DISABLE_SIGNALS', False):
        return
    if created and not instance.portfolios.filter(is_default=True).exists():
        # Create portfolio with 0 cash (cash will be set via transaction)
        portfolio = Portfolio.objects.create(
            user=instance,
            is_default=True,
            cash_balance=Decimal('0.00')
        )
        # Create initial deposit transaction
        TransactionService.execute_transaction({
            'portfolio': portfolio,
            'transaction_type': Transaction.TransactionType.DEPOSIT,
            'amount': Decimal('10000.00'),
            'idempotency_key': uuid4(),
        })

@receiver(post_save, sender=Portfolio)
def create_performance_record(sender, instance, created, **kwargs):
    if created:
        PortfolioPerformance.objects.get_or_create(portfolio=instance)