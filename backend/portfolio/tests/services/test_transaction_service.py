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

@pytest.mark.django_db
class TestTransactionPNLHandling:
    def test_sell_transaction_pnl_creation(self, sell_transaction):
        assert hasattr(sell_transaction, 'realized_pnl')
        assert sell_transaction.realized_pnl.pnl != Decimal('0.00')

    def test_pnl_calculation_accuracy(self, sell_transaction):
        pnl = sell_transaction.realized_pnl
        expected = (pnl.sell_price - pnl.purchase_price) * pnl.quantity
        assert pnl.pnl == expected.quantize(Decimal('0.01'))

    def test_buy_transaction_no_pnl(self, buy_transaction):
        assert not hasattr(buy_transaction, 'realized_pnl')

    def test_deposit_tracking(self, funded_portfolio):
        initial_deposits = funded_portfolio.performance.total_deposits
        deposit = TransactionFactory(
            portfolio=funded_portfolio,
            transaction_type='DEPOSIT',
            amount=Decimal('5000.00')
        )
        
        deposit.refresh_from_db()
        funded_portfolio.performance.refresh_from_db()
        
        assert funded_portfolio.performance.total_deposits == (
            initial_deposits + deposit.amount
        )