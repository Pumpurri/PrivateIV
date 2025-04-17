# backend/portfolio/services/transaction_services.py
from django.db import transaction as db_transaction
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
import logging
from portfolio.models import Transaction, Holding, RealizedPNL, PortfolioPerformance

logger = logging.getLogger(__name__)

class TransactionService:
    @classmethod
    def execute_transaction(cls, transaction):
        try:
            with db_transaction.atomic(using='default'):
                cls._process_transaction_core(transaction)
        except ValidationError as e:
            cls._handle_failed_transaction(transaction, str(e))
            raise
        except Exception as e:
            logger.critical(f"Unexpected error in transaction {transaction.id}: {str(e)}")
            raise ValidationError("Transaction processing failed") from e
        finally:
            transaction.refresh_from_db()

    @classmethod
    def _process_transaction_core(cls, transaction):
        """Core processing logic with strict validation"""
        handler = cls._get_transaction_handler(transaction.transaction_type)
        handler(transaction)
        cls._finalize_transaction(transaction)

    @classmethod
    def _get_transaction_handler(cls, transaction_type):
        """Router for transaction type handlers with validation"""
        handlers = {
            Transaction.TransactionType.BUY: cls._process_buy,
            Transaction.TransactionType.SELL: cls._process_sell,
            Transaction.TransactionType.DEPOSIT: cls._process_deposit,
        }
        
        if transaction_type not in handlers:
            raise ValidationError(f"Unsupported transaction type: {transaction_type}")
            
        return handlers[transaction_type]

    @classmethod
    def _finalize_transaction(cls, transaction):
        """Persist transaction details with field-level precision"""
        transaction.save(update_fields=[
            'executed_price',
            'amount',
            'timestamp'
        ])
        logger.info(f"Processed {transaction.get_transaction_type_display()} "\
                    f"transaction {transaction.id}")

    @classmethod
    def _handle_failed_transaction(cls, transaction, error_msg):
        """Enhanced error logging with transaction context"""
        logger.error(f"Transaction {transaction.id} failed - Error: {error_msg}")
        try:
            transaction.error_message = error_msg[:255]
            transaction.save(update_fields=['error_message'])
        except Exception as e:
            logger.error(f"Failed to save error message: {str(e)}")

    @classmethod
    def _process_buy(cls, transaction):
        """SEC Rule 15c3-1 compliant buy processing"""
        portfolio = transaction.portfolio
        stock = cls._validate_stock(transaction.stock)
        quantity = cls._validate_quantity(transaction.quantity)
        
        current_price = cls._validate_price(stock.current_price)
        total_cost = (Decimal(quantity) * current_price).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        portfolio.adjust_cash(-total_cost)
        portfolio.holdings.process_purchase(
            portfolio=portfolio,
            stock=stock,
            quantity=quantity,
            price_per_share=current_price
        )
        
        transaction.executed_price = current_price
        transaction.amount = total_cost

    @classmethod
    def _process_sell(cls, transaction):
        """SEC Rule 15c3-1 compliant sell processing"""
        portfolio = transaction.portfolio
        stock = cls._validate_stock(transaction.stock)
        quantity = cls._validate_quantity(transaction.quantity)
        
        current_price = cls._validate_price(stock.current_price)
        total_revenue = (Decimal(quantity) * current_price).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        holding = portfolio.holdings.get(stock=stock)
        pnl_value = (current_price - holding.average_purchase_price) * quantity
        
        portfolio.holdings.process_sale(
            portfolio=portfolio,
            stock=stock,
            quantity=quantity
        )
        portfolio.adjust_cash(total_revenue)
        
        RealizedPNL.objects.create(
            portfolio=portfolio,
            transaction=transaction,
            stock=stock,
            quantity=quantity,
            purchase_price=holding.average_purchase_price,
            sell_price=current_price,
            pnl=pnl_value
        )
            
        transaction.executed_price = current_price
        transaction.amount = total_revenue


    @classmethod
    def _process_deposit(cls, transaction):
        """Regulation D compliant deposit processing"""
        amount = cls._validate_amount(transaction.amount)
        portfolio = transaction.portfolio
        
        # Ensure performance record exists
        performance, _ = PortfolioPerformance.objects.get_or_create(
            portfolio=portfolio
        )
        
        portfolio.adjust_cash(amount)
        performance.total_deposits += amount
        performance.save(update_fields=['total_deposits'])
        transaction.executed_price = None

    @classmethod
    def _validate_stock(cls, stock):
        """FINRA Rule 4210 validation"""
        if not stock or not stock.is_active:
            raise ValidationError("Invalid or inactive security")
        if not hasattr(stock, 'is_active'):
            raise ValidationError("Invalid stock structure")
        if not stock.is_active:
            raise ValidationError(f"Stock {stock.symbol} is not active")
        return stock

    @classmethod
    def _validate_price(cls, price):
        """Price validation per SEC Rule 612"""
        if not isinstance(price, Decimal):
            raise ValidationError("Price must be Decimal type")
        if price <= Decimal('0'):
            raise ValidationError(f"Invalid price: {price}")
        return price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def _validate_quantity(cls, quantity):
        """Quantity validation per SEC Rule 612"""
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError(f"Invalid quantity: {quantity}")
        return quantity

    @classmethod
    def _validate_amount(cls, amount):
        """Amount validation for cash transactions"""
        if not isinstance(amount, Decimal):
            raise ValidationError("Amount must be Decimal type")
        if amount <= Decimal('0'):
            raise ValidationError(f"Invalid amount: {amount}")
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def _notify_ops_team(cls, transaction, error_msg):
        """Hook for operational alerts (implement with Celery in production)"""
        # Placeholder for actual notification system
        pass