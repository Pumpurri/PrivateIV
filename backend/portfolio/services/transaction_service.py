# backend/portfolio/services/transaction_services.py
from django.db import transaction as db_transaction
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
import logging
from portfolio.models import Transaction, Holding, RealizedPNL, PortfolioPerformance
from portfolio.services.tracing import span
from portfolio.services.fx_service import get_fx_rate
from django.utils import timezone
from django.utils.timezone import localtime
from datetime import time

logger = logging.getLogger(__name__)

class TransactionService:
    @classmethod
    def execute_transaction(cls, transaction_data):
        """Idempotent transaction processing with duplicate detection"""
        with span(
            "transaction.execute",
            resource=str(transaction_data.get('transaction_type')),
            tags={
                "portfolio.id": getattr(transaction_data.get('portfolio'), 'id', None),
            }
        ), db_transaction.atomic(using='default'):
            existing = Transaction.all_objects.filter(
                portfolio=transaction_data['portfolio'],
                idempotency_key=transaction_data['idempotency_key']
            ).first()
            
            if existing:
                logger.warning(f"Idempotency key collision: {transaction_data['idempotency_key']}")
                return existing

            transaction = Transaction(**transaction_data)
            transaction._created_by_service = True
            transaction.full_clean()

            handler = cls._get_transaction_handler(transaction.transaction_type)
            with span("transaction.process", resource=transaction.transaction_type):
                handler(transaction)
            transaction.save()
            
            # Post-save processing (like RealizedPNL creation)
            cls._post_process_transaction(transaction)
            
            return transaction


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
            Transaction.TransactionType.WITHDRAWAL: cls._process_withdrawal,
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
        total_cost_native = (Decimal(quantity) * current_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Determine FX session (intraday 11:05–13:29 America/Lima, else cierre)
        try:
            now_t = localtime().time()
        except Exception:
            now_t = timezone.now().time()
        cmp_t = now_t.replace(tzinfo=None) if getattr(now_t, 'tzinfo', None) else now_t
        session = 'intraday' if (cmp_t >= time(11, 5) and cmp_t < time(13, 30)) else 'cierre'

        # Apply FX only when stock currency differs from portfolio base
        if getattr(stock, 'currency', None) and stock.currency != portfolio.base_currency:
            # BUY (PEN -> USD): use 'venta' (bank sells USD)
            fx = get_fx_rate(timezone.now().date(), portfolio.base_currency, stock.currency, rate_type='venta', session=session)
            total_cost_base = (total_cost_native * fx).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            price_per_share_base = (current_price * fx).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            transaction.fx_rate = fx
            transaction.fx_rate_type = 'venta'
        else:
            total_cost_base = total_cost_native
            price_per_share_base = current_price
        with span("transaction.buy", resource=str(stock.symbol), tags={"quantity": quantity}):
            portfolio.adjust_cash(-total_cost_base)
            portfolio.holdings.process_purchase(
                portfolio=portfolio,
                stock=stock,
                quantity=quantity,
                price_per_share=price_per_share_base
            )
        
        transaction.executed_price = current_price  # native
        transaction.amount = total_cost_native      # keep amount in native for consistency with existing tests

    @classmethod
    def _process_sell(cls, transaction):
        """SEC Rule 15c3-1 compliant sell processing"""
        portfolio = transaction.portfolio
        stock = cls._validate_stock(transaction.stock)
        quantity = cls._validate_quantity(transaction.quantity)
        
        current_price = cls._validate_price(stock.current_price)
        total_revenue_native = (Decimal(quantity) * current_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        try:
            holding = portfolio.holdings.get(stock=stock)
        except Holding.DoesNotExist:
            raise ValidationError("Cannot sell stock not held in portfolio")
        pnl_value = (current_price - holding.average_purchase_price) * quantity
        
        # Determine FX session
        try:
            now_t = localtime().time()
        except Exception:
            now_t = timezone.now().time()
        cmp_t = now_t.replace(tzinfo=None) if getattr(now_t, 'tzinfo', None) else now_t
        session = 'intraday' if (cmp_t >= time(11, 5) and cmp_t < time(13, 30)) else 'cierre'
        if getattr(stock, 'currency', None) and stock.currency != portfolio.base_currency:
            # SELL (USD -> PEN): use 'compra' (bank buys USD)
            fx = get_fx_rate(timezone.now().date(), portfolio.base_currency, stock.currency, rate_type='compra', session=session)
            total_revenue_base = (total_revenue_native * fx).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            transaction.fx_rate = fx
            transaction.fx_rate_type = 'compra'
        else:
            total_revenue_base = total_revenue_native

        with span("transaction.sell", resource=str(stock.symbol), tags={"quantity": quantity}):
            portfolio.holdings.process_sale(
                portfolio=portfolio,
                stock=stock,
                quantity=quantity
            )
            portfolio.adjust_cash(total_revenue_base)

        # Store PNL data for post-processing
        transaction._pnl_data = {
            'holding_average_price': holding.average_purchase_price,
            'pnl_value': pnl_value,
            'acquisition_date': holding.created_at  # Track when shares were acquired
        }
            
        transaction.executed_price = current_price
        transaction.amount = total_revenue_native


    @classmethod
    def _process_deposit(cls, transaction):
        """Regulation D compliant deposit processing"""
        amount = cls._validate_amount(transaction.amount)
        portfolio = transaction.portfolio
        
        # Ensure performance record exists
        performance, _ = PortfolioPerformance.objects.get_or_create(
            portfolio=portfolio
        )
        
        with span("transaction.deposit", resource=str(portfolio.id), tags={"amount": str(amount)}):
            portfolio.adjust_cash(amount)
        performance.total_deposits += amount
        performance.save(update_fields=['total_deposits'])
        transaction.executed_price = None

    @classmethod
    def _process_withdrawal(cls, transaction):
        amount = cls._validate_amount(transaction.amount)
        portfolio = transaction.portfolio
        
        # Ensure performance record exists
        performance, _ = PortfolioPerformance.objects.get_or_create(
            portfolio=portfolio
        )
        
        with span("transaction.withdrawal", resource=str(portfolio.id), tags={"amount": str(amount)}):
            portfolio.adjust_cash(-amount)
        performance.total_withdrawals += amount
        performance.save(update_fields=['total_withdrawals'])
        transaction.executed_price = None

    @classmethod
    def _validate_stock(cls, stock):
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
    def _post_process_transaction(cls, transaction):
        """Post-save processing for transactions"""
        if transaction.transaction_type == Transaction.TransactionType.SELL and hasattr(transaction, '_pnl_data'):
            # Create RealizedPNL after transaction is saved
            pnl_data = transaction._pnl_data
            RealizedPNL.objects.create(
                portfolio=transaction.portfolio,
                transaction=transaction,
                stock=transaction.stock,
                quantity=transaction.quantity,
                purchase_price=pnl_data['holding_average_price'],
                sell_price=transaction.executed_price,
                pnl=pnl_data['pnl_value'],
                acquisition_date=pnl_data.get('acquisition_date')  # Save acquisition date for holding period
            )

    @classmethod
    def _notify_ops_team(cls, transaction, error_msg):
        """Hook for operational alerts (implement with Celery in production)"""
        # Placeholder for actual notification system
        pass
