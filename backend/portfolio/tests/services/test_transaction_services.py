import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from portfolio.tests.factories import TransactionFactory

@pytest.mark.django_db
class TestTransactionProcessor:
    def test_deposit_processing(self, portfolio):
        """Test cash deposit transaction processing"""
        initial_balance = portfolio.cash_balance
        amount = Decimal('5000.00')
        
        portfolio.adjust_cash(amount)
        
        assert portfolio.cash_balance == initial_balance + amount

    def test_invalid_transaction_rollback(self, portfolio):
        """Test transaction rollback on validation failure"""
        initial_balance = portfolio.cash_balance
        try:
            with transaction.atomic():
                portfolio.adjust_cash(Decimal('5000.00'))
                portfolio.adjust_cash(Decimal('-20000.00'))
        except ValidationError:
            pass
        
        portfolio.refresh_from_db()
        assert portfolio.cash_balance == initial_balance