import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from portfolio.tests.factories import TransactionFactory, PortfolioFactory
from portfolio.models import RealizedPNL

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

    def test_buy_transaction_no_pnl(self, portfolio, stock):
        transaction = TransactionFactory(
            portfolio=portfolio,
            transaction_type='BUY',
            stock=stock,
            quantity=10,
            executed_price=stock.current_price,
            amount=10 * stock.current_price
        )
        assert not hasattr(transaction, 'realized_pnl')

    def test_deposit_tracking(self, portfolio):
        initial_deposits = portfolio.performance.total_deposits
        deposit = TransactionFactory(
            portfolio=portfolio,
            transaction_type='DEPOSIT',
            amount=Decimal('5000.00')
        )

        portfolio.performance.refresh_from_db()
        assert portfolio.performance.total_deposits == initial_deposits + deposit.amount

    def test_sell_transaction_zero_pnl(self, portfolio, stock):
        TransactionFactory(
            portfolio=portfolio,
            transaction_type='BUY',
            stock=stock,
            quantity=10,
            executed_price=stock.current_price,
            amount=10 * stock.current_price
        )
        sell = TransactionFactory(
            portfolio=portfolio,
            transaction_type='SELL',
            stock=stock,
            quantity=10,
            executed_price=stock.current_price,
            amount=10 * stock.current_price
        )
        assert hasattr(sell, 'realized_pnl')
        assert sell.realized_pnl.pnl == Decimal('0.00')

    def test_partial_sell_pnl(self, portfolio, stock): 
        stock.current_price = Decimal('50.00')
        stock.save()

        buy = TransactionFactory.build(
            portfolio=portfolio,
            transaction_type='BUY',
            stock=stock,
            quantity=100,
        ).save()

        stock.current_price = Decimal('60.00')
        stock.save()

        sell = TransactionFactory.build(
            portfolio=portfolio,
            transaction_type='SELL',
            stock=stock,
            quantity=40,
        )
        sell.save()

        pnl = sell.realized_pnl
        expected = (Decimal('60.00') - Decimal('50.00')) * 40
        assert pnl.pnl == expected.quantize(Decimal('0.01'))

    def test_loss_on_sell_transaction(self, portfolio, stock):
        stock.current_price = Decimal('100.00')
        stock.save()

        TransactionFactory.build(
            portfolio=portfolio,
            transaction_type='BUY',
            stock=stock,
            quantity=50,
        ).save()

        stock.current_price = Decimal('90.00')
        stock.save()

        sell = TransactionFactory.build(
            portfolio=portfolio,
            transaction_type='SELL',
            stock=stock,
            quantity=50,
        )
        sell.save()

        pnl = sell.realized_pnl
        expected = (Decimal('90.00') - Decimal('100.00')) * 50
        assert pnl.pnl == expected.quantize(Decimal('0.01'))

    def test_no_pnl_on_invalid_sell(self, portfolio, stock):
        stock.current_price = Decimal('50.00')
        stock.save()

        TransactionFactory.build(
            portfolio=portfolio,
            transaction_type='BUY',
            stock=stock,
            quantity=10,
        ).save()

        stock.current_price = Decimal('60.00')
        stock.save()

        with pytest.raises(ValidationError):
            TransactionFactory.build(
                portfolio=portfolio,
                transaction_type='SELL',
                stock=stock,
                quantity=100, 
            ).save()

        assert not hasattr(portfolio.transactions.last(), 'realized_pnl')

    def test_pnl_uses_weighted_average_purchase_price(self, portfolio, stock):
        stock.current_price = Decimal('50.00')
        stock.save()

        TransactionFactory.build(
            portfolio=portfolio, 
            transaction_type='BUY', 
            stock=stock, 
            quantity=10
        ).save()

        stock.current_price = Decimal('100.00')
        stock.save()

        TransactionFactory.build(
            portfolio=portfolio, 
            transaction_type='BUY', 
            stock=stock, 
            quantity=10
        ).save()

        stock.current_price = Decimal('90.00')
        stock.save()

        sell = TransactionFactory.build(
            portfolio=portfolio, 
            transaction_type='SELL', 
            stock=stock, 
            quantity=10
        )
        sell.save()

        pnl = sell.realized_pnl
        expected = (Decimal('90.00') - Decimal('75.00')) * 10
        assert pnl.pnl == expected.quantize(Decimal('0.01'))

    def test_realized_pnl_is_immutable(self, sell_transaction):
        pnl = sell_transaction.realized_pnl
        pnl.pnl = Decimal('99999.99')
        with pytest.raises(ValidationError):
            pnl.save()
    
    def test_pnl_decimal_precision(self, portfolio, stock):
        stock.current_price = Decimal('100.1234')
        stock.save()

        TransactionFactory.build(
            portfolio=portfolio, 
            transaction_type='BUY', 
            stock=stock, 
            quantity=10
        ).save()

        stock.current_price = Decimal('150.5678')
        stock.save()

        sell = TransactionFactory.build(
            portfolio=portfolio, 
            transaction_type='SELL', 
            stock=stock, 
            quantity=10
        )
        sell.save()

        pnl = sell.realized_pnl
        expected = (stock.current_price - Decimal('100.12')) * 10
        assert pnl.pnl == expected.quantize(Decimal('0.01'))
    
    def test_pnl_deleted_with_transaction(self, sell_transaction):
        txn_id = sell_transaction.id
        sell_transaction.delete()
        assert not RealizedPNL.objects.filter(transaction_id=txn_id).exists()

    def test_partial_sell_leaves_holding(self, portfolio, stock):
        stock.current_price = Decimal('100.00')
        stock.save()

        TransactionFactory.build(
            portfolio=portfolio, 
            transaction_type='BUY', 
            stock=stock, 
            quantity=10
        ).save()

        stock.current_price = Decimal('110.00')
        stock.save()

        sell = TransactionFactory.build(
            portfolio=portfolio, 
            transaction_type='SELL', 
            stock=stock, 
            quantity=9
        )
        sell.save()

        assert portfolio.holdings.get(stock=stock).quantity == 1
        assert sell.realized_pnl.pnl == Decimal('90.00')

    def test_full_sell_removes_holding_and_creates_pnl(self, portfolio, stock):
        stock.current_price = Decimal('80.00')
        stock.save()
        TransactionFactory.build(
            portfolio=portfolio, 
            transaction_type='BUY',
            stock=stock,
            quantity=10
        ).save()

        stock.current_price = Decimal('100.00')
        stock.save()
        sell = TransactionFactory.build(
            portfolio=portfolio,
            transaction_type='SELL',
            stock=stock,
            quantity=10
        )
        sell.save()

        assert not portfolio.holdings.filter(stock=stock).exists()
        assert sell.realized_pnl.pnl == Decimal('200.00')