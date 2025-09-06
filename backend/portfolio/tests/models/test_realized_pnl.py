import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from portfolio.models import RealizedPNL, Portfolio
from portfolio.tests.conftest import portfolio_with_holding
from portfolio.tests.factories import TransactionFactory

@pytest.mark.django_db
class TestRealizedPNLModel:
    def test_pnl_calculation(self, sell_transaction):
        """Test accurate P&L calculation including decimal precision"""
        pnl = RealizedPNL.objects.get(transaction=sell_transaction)
        expected = (sell_transaction.executed_price - pnl.purchase_price) * pnl.quantity
        assert pnl.pnl == expected.quantize(Decimal('0.01'))
        assert abs(pnl.pnl) > Decimal('0')  # Sanity check

    def test_negative_pnl(self, portfolio_with_holding):
        """Test loss scenario recording"""
        portfolio = portfolio_with_holding['portfolio']
        holding = portfolio_with_holding['holding']
        stock = holding.stock
        stock.current_price = Decimal('40.00')  # Below purchase price
        stock.save()

        # Create sell transaction
        t = TransactionFactory(
            portfolio=portfolio,
            transaction_type='SELL',
            stock=stock,
            quantity=50
        )
        
        pnl = RealizedPNL.objects.get(transaction=t)
        assert pnl.pnl == (40 - 50) * 50  # -500.00
        assert pnl.pnl < Decimal('0')

    def test_immutable_relationship(self, sell_transaction):
        """Ensure P&L records cannot be modified post-creation"""
        pnl = RealizedPNL.objects.get(transaction=sell_transaction)
        pnl.quantity = 100  # Change field
        with pytest.raises(ValidationError):
            pnl.save()

    def test_cascade_deletion(self):
        """Test proper deletion constraints"""
        # Create a non-default portfolio for testing
        from users.tests.factories import UserFactory
        from stocks.tests.factories import StockFactory
        from portfolio.tests.factories import PortfolioFactory, HoldingFactory
        
        user = UserFactory()
        test_portfolio = PortfolioFactory(
            user=user,
            is_default=False,
            cash_balance=Decimal('10000.00')
        )
        stock = StockFactory(current_price=Decimal('100.00'))
        
        # Create holding and sell transaction on non-default portfolio
        holding = HoldingFactory(
            portfolio=test_portfolio,
            stock=stock,
            quantity=100,
            average_purchase_price=Decimal('50.00')
        )
        
        sell_transaction = TransactionFactory(
            portfolio=test_portfolio,
            transaction_type='SELL',
            stock=stock,
            quantity=5,
        )
        
        # Verify PNL was created
        assert RealizedPNL.objects.filter(transaction=sell_transaction).exists()
        
        # Delete portfolio and check cascade
        test_portfolio.delete()
        assert not RealizedPNL.objects.exists()

    def test_field_validation_quantity_zero(self, sell_transaction):
        pnl = RealizedPNL.objects.get(transaction=sell_transaction)
        pnl.quantity = 0
        with pytest.raises(ValidationError):
            pnl.save()

    def save(self, *args, **kwargs):
        if self.pk is not None:
            original = RealizedPNL.objects.get(pk=self.pk)
            if any(
                getattr(self, field) != getattr(original, field)
                for field in ['portfolio', 'transaction', 'stock', 'quantity', 
                             'purchase_price', 'sell_price', 'pnl']
            ):
                raise ValidationError("RealizedPNL records cannot be modified after creation.")
        super().save(*args, **kwargs)

    def clean(self):
        if self.pk:
            raise ValidationError("RealizedPNL records are immutable.")