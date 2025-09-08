from django.core.management.base import BaseCommand
from django.apps import apps
from stocks.services import fetch_data_for_companies
from math import ceil

class Command(BaseCommand):
    help = 'Updates stock prices'

    def handle(self, *args, **kwargs):
        Stock = apps.get_model('stocks', 'Stock')

        stocks = Stock.objects.all()
        if not stocks.exists():
            self.stdout.write(self.style.ERROR("No stocks found in the database."))
            return

        # Get all symbols and batch them
        symbols = [stock.symbol for stock in stocks]
        batch_size = 20
        num_batches = ceil(len(symbols) / batch_size)
        
        for i in range(num_batches):
            batch_symbols = symbols[i*batch_size:(i+1)*batch_size]
            symbols_str = ','.join(batch_symbols)
            
            self.stdout.write(f"Fetching prices for batch: {symbols_str}")
            data = fetch_data_for_companies(symbols_str)
            
            if data:
                for stock_info in data:
                    symbol = stock_info.get('symbol')
                    current_price = stock_info.get('price', 0.0)
                    
                    try:
                        stock = Stock.objects.get(symbol=symbol)
                        stock.current_price = current_price
                        stock.save()
                        self.stdout.write(self.style.SUCCESS(f"Updated {symbol} to {current_price}"))
                    except Stock.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Stock {symbol} not found in database"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to fetch prices for batch: {symbols_str}"))
