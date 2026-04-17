# backend/portfolio/services/transaction_services.py
from django.db import transaction as db_transaction
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
import logging
from portfolio.models import Transaction, Holding, RealizedPNL, PortfolioPerformance
from portfolio.services.currency_service import convert_with_pen_per_usd_rate, normalize_currency
from portfolio.services.tracing import span
from portfolio.services.fx_service import get_current_fx_context, get_fx_rate
from uuid import uuid4

logger = logging.getLogger(__name__)

class TransactionService:
    @classmethod
    def execute_transaction(cls, transaction_data):
        """Idempotent transaction processing with duplicate detection"""
        transaction_data = dict(transaction_data)
        transaction_data['idempotency_key'] = transaction_data.get('idempotency_key') or uuid4()

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
            Transaction.TransactionType.CONVERT: cls._process_convert,
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
        original_currency = normalize_currency(getattr(stock, 'currency', None) or portfolio.base_currency)
        settlement_currency = cls._resolve_settlement_currency(transaction, default_currency=portfolio.base_currency)
        current_price = cls._validate_price(stock.current_price)
        total_cost_native = (Decimal(quantity) * current_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        fx_date, session = get_current_fx_context()
        pen_per_usd_rate, fx_rate_type = cls._get_pen_per_usd_rate_for_settlement(
            fx_date=fx_date,
            session=session,
            original_currency=original_currency,
            settlement_currency=settlement_currency,
            trade_direction='BUY',
        )
        settlement_amount = cls._convert_original_to_settlement_amount(
            total_cost_native,
            original_currency=original_currency,
            settlement_currency=settlement_currency,
            pen_per_usd_rate=pen_per_usd_rate,
        )
        price_per_share_base = cls._convert_original_to_pen_amount(
            current_price,
            original_currency=original_currency,
            pen_per_usd_rate=pen_per_usd_rate,
        )
        transaction.cash_currency = settlement_currency
        transaction.fx_rate = pen_per_usd_rate
        transaction.fx_rate_type = fx_rate_type
        with span("transaction.buy", resource=str(stock.symbol), tags={"quantity": quantity}):
            portfolio.adjust_cash(-settlement_amount, currency=settlement_currency)
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
        original_currency = normalize_currency(getattr(stock, 'currency', None) or portfolio.base_currency)
        settlement_currency = cls._resolve_settlement_currency(transaction, default_currency=portfolio.base_currency)
        current_price = cls._validate_price(stock.current_price)
        total_revenue_native = (Decimal(quantity) * current_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        try:
            holding = portfolio.holdings.get(stock=stock)
        except Holding.DoesNotExist:
            raise ValidationError("Cannot sell stock not held in portfolio")
        purchase_price_base = holding.average_purchase_price
        
        fx_date, session = get_current_fx_context()
        pen_per_usd_rate, fx_rate_type = cls._get_pen_per_usd_rate_for_settlement(
            fx_date=fx_date,
            session=session,
            original_currency=original_currency,
            settlement_currency=settlement_currency,
            trade_direction='SELL',
        )
        settlement_amount = cls._convert_original_to_settlement_amount(
            total_revenue_native,
            original_currency=original_currency,
            settlement_currency=settlement_currency,
            pen_per_usd_rate=pen_per_usd_rate,
        )
        sell_price_base = cls._convert_original_to_pen_amount(
            current_price,
            original_currency=original_currency,
            pen_per_usd_rate=pen_per_usd_rate,
        )
        transaction.cash_currency = settlement_currency
        transaction.fx_rate = pen_per_usd_rate
        transaction.fx_rate_type = fx_rate_type

        pnl_value = ((sell_price_base - purchase_price_base) * Decimal(quantity)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        with span("transaction.sell", resource=str(stock.symbol), tags={"quantity": quantity}):
            portfolio.holdings.process_sale(
                portfolio=portfolio,
                stock=stock,
                quantity=quantity
            )
            portfolio.adjust_cash(settlement_amount, currency=settlement_currency)

        # Store PNL data for post-processing
        transaction._pnl_data = {
            'purchase_price': purchase_price_base,
            'sell_price': sell_price_base,
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
        cash_currency = cls._resolve_settlement_currency(transaction, default_currency=portfolio.base_currency)
        fx_date, session = get_current_fx_context()
        mid_rate = cls._get_mid_pen_per_usd_rate(fx_date, session)
        
        # Ensure performance record exists
        performance, _ = PortfolioPerformance.objects.get_or_create(
            portfolio=portfolio
        )
        
        with span("transaction.deposit", resource=str(portfolio.id), tags={"amount": str(amount)}):
            portfolio.adjust_cash(amount, currency=cash_currency)
        performance.total_deposits += cls._convert_original_to_pen_amount(amount, cash_currency, mid_rate)
        performance.save(update_fields=['total_deposits'])
        transaction.cash_currency = cash_currency
        transaction.fx_rate = mid_rate
        transaction.fx_rate_type = 'mid'
        transaction.executed_price = None

    @classmethod
    def _process_withdrawal(cls, transaction):
        amount = cls._validate_amount(transaction.amount)
        portfolio = transaction.portfolio
        cash_currency = cls._resolve_settlement_currency(transaction, default_currency=portfolio.base_currency)
        fx_date, session = get_current_fx_context()
        mid_rate = cls._get_mid_pen_per_usd_rate(fx_date, session)
        
        # Ensure performance record exists
        performance, _ = PortfolioPerformance.objects.get_or_create(
            portfolio=portfolio
        )
        
        with span("transaction.withdrawal", resource=str(portfolio.id), tags={"amount": str(amount)}):
            portfolio.adjust_cash(-amount, currency=cash_currency)
        performance.total_withdrawals += cls._convert_original_to_pen_amount(amount, cash_currency, mid_rate)
        performance.save(update_fields=['total_withdrawals'])
        transaction.cash_currency = cash_currency
        transaction.fx_rate = mid_rate
        transaction.fx_rate_type = 'mid'
        transaction.executed_price = None

    @classmethod
    def _process_convert(cls, transaction):
        amount = cls._validate_amount(transaction.amount)
        portfolio = transaction.portfolio
        source_currency = cls._resolve_settlement_currency(transaction, default_currency=portfolio.base_currency)
        target_currency = normalize_currency(transaction.counter_currency)
        if source_currency == target_currency:
            raise ValidationError("FX conversion requires different source and target currencies")

        fx_date, session = get_current_fx_context()
        pen_per_usd_rate, fx_rate_type = cls._get_pen_per_usd_rate_for_settlement(
            fx_date=fx_date,
            session=session,
            original_currency=source_currency,
            settlement_currency=target_currency,
            trade_direction='CONVERT',
        )
        converted_amount = cls._convert_original_to_settlement_amount(
            amount,
            original_currency=source_currency,
            settlement_currency=target_currency,
            pen_per_usd_rate=pen_per_usd_rate,
        )

        with span("transaction.convert", resource=str(portfolio.id), tags={"amount": str(amount)}):
            portfolio.adjust_cash(-amount, currency=source_currency)
            portfolio.adjust_cash(converted_amount, currency=target_currency)

        transaction.cash_currency = source_currency
        transaction.counter_currency = target_currency
        transaction.counter_amount = converted_amount
        transaction.fx_rate = pen_per_usd_rate
        transaction.fx_rate_type = fx_rate_type
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
    def _resolve_settlement_currency(cls, transaction, *, default_currency):
        requested_currency = transaction.cash_currency or default_currency
        return normalize_currency(requested_currency, default=default_currency)

    @classmethod
    def _get_mid_pen_per_usd_rate(cls, fx_date, session):
        return get_fx_rate(
            fx_date,
            'PEN',
            'USD',
            rate_type='mid',
            session=session,
        )

    @classmethod
    def _get_pen_per_usd_rate_for_settlement(cls, *, fx_date, session, original_currency, settlement_currency, trade_direction):
        original_currency = normalize_currency(original_currency)
        settlement_currency = normalize_currency(settlement_currency)

        if original_currency == settlement_currency:
            return cls._get_mid_pen_per_usd_rate(fx_date, session), 'mid'

        if original_currency == 'USD' and settlement_currency == 'PEN':
            rate_type = 'venta' if trade_direction == Transaction.TransactionType.BUY else 'compra'
            return get_fx_rate(
                fx_date,
                'PEN',
                'USD',
                rate_type=rate_type,
                session=session,
                require_rate=True,
            ), rate_type

        if original_currency == 'PEN' and settlement_currency == 'USD':
            rate_type = 'compra' if trade_direction == Transaction.TransactionType.BUY else 'venta'
            return get_fx_rate(
                fx_date,
                'PEN',
                'USD',
                rate_type=rate_type,
                session=session,
                require_rate=True,
            ), rate_type

        return cls._get_mid_pen_per_usd_rate(fx_date, session), 'mid'

    @classmethod
    def _convert_original_to_settlement_amount(cls, amount, *, original_currency, settlement_currency, pen_per_usd_rate):
        return convert_with_pen_per_usd_rate(
            amount,
            original_currency,
            settlement_currency,
            pen_per_usd_rate,
        )

    @classmethod
    def _convert_original_to_pen_amount(cls, amount, original_currency, pen_per_usd_rate):
        return convert_with_pen_per_usd_rate(
            amount,
            original_currency,
            'PEN',
            pen_per_usd_rate,
        )

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
                purchase_price=pnl_data['purchase_price'],
                sell_price=pnl_data['sell_price'],
                pnl=pnl_data['pnl_value'],
                acquisition_date=pnl_data.get('acquisition_date')  # Save acquisition date for holding period
            )

    @classmethod
    def _notify_ops_team(cls, transaction, error_msg):
        """Hook for operational alerts (implement with Celery in production)"""
        # Placeholder for actual notification system
        pass
