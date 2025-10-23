from django.contrib.auth import get_user_model
from portfolio.models import Portfolio, Transaction

User = get_user_model()
user = User.objects.filter(email='sjjs0805@gmail.com').first()

if user:
    print(f'User found: {user.email} (ID: {user.id})')
    portfolio = Portfolio.objects.filter(id=2, user=user).first()
    if portfolio:
        print(f'\nPortfolio: {portfolio.name} (ID: {portfolio.id})')
        print(f'Cash Balance: {portfolio.cash_balance}')
        print(f'Total Value: {portfolio.total_value}')
        print(f'\nTransactions:')
        print('-' * 120)
        print(f'{"Date":<20} | {"Type":4} | {"Symbol":6} | {"Quantity":>8} | {"Price":>12} | {"Total":>14}')
        print('-' * 120)
        txs = Transaction.objects.filter(portfolio=portfolio).select_related('stock').order_by('-timestamp')
        for tx in txs:
            price = tx.executed_price or 0
            qty = tx.quantity or 0
            total = qty * price
            symbol = tx.stock.symbol if tx.stock else 'N/A'
            print(f'{str(tx.timestamp):<20} | {tx.transaction_type:4} | {symbol:6} | {qty:8} | ${price:11.2f} | ${total:13.2f}')
        print('-' * 120)
        print(f'Total transactions: {txs.count()}')

        # Show holdings
        print(f'\nCurrent Holdings:')
        print('-' * 100)
        print(f'{"Symbol":6} | {"Quantity":>8} | {"Avg Price":>12} | {"Current Price":>14} | {"Market Value":>14}')
        print('-' * 100)
        from portfolio.models import Holding
        holdings = Holding.objects.filter(portfolio=portfolio, quantity__gt=0)
        for h in holdings:
            print(f'{h.stock.symbol:6} | {h.quantity:8} | ${h.average_purchase_price:11.2f} | ${h.stock.current_price:13.2f} | ${h.current_value:13.2f}')
        print('-' * 100)

        # Calculate the math
        print(f'\n=== PORTFOLIO MATH ===')
        total_spent = sum((tx.executed_price or 0) * (tx.quantity or 0) for tx in txs if tx.transaction_type == 'BUY')
        total_holdings_value = sum(h.current_value for h in holdings)

        print(f'Total spent on stocks: ${total_spent:.2f}')
        print(f'Current holdings value: ${total_holdings_value:.2f}')
        print(f'Cash balance: ${portfolio.cash_balance:.2f}')
        print(f'Expected total: ${total_holdings_value + portfolio.cash_balance:.2f}')
        print(f'Reported total: ${portfolio.total_value:.2f}')
        print(f'')
        print(f'Unrealized P&L: ${total_holdings_value - total_spent:.2f}')
        print(f'')

        # Check deposits
        deposits = Transaction.objects.filter(portfolio=portfolio, transaction_type='DEPOSIT')
        total_deposits = sum((tx.amount or 0) for tx in deposits)
        print(f'Total deposits: ${total_deposits:.2f}')

        # What should the cash be?
        withdrawals = Transaction.objects.filter(portfolio=portfolio, transaction_type='WITHDRAWAL')
        total_withdrawals = sum((tx.amount or 0) for tx in withdrawals)
        print(f'Total withdrawals: ${total_withdrawals:.2f}')
        print(f'Expected cash: ${total_deposits - total_withdrawals - total_spent:.2f}')

    else:
        print(f'Portfolio with ID 2 not found for user {user.email}')
else:
    print('User not found')
