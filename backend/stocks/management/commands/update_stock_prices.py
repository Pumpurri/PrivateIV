from django.core.management.base import BaseCommand
from django.apps import apps
from stocks.services import fetch_data_for_companies

class Command(BaseCommand):
    help = 'Updates stock prices'

    def handle(self, *args, **kwargs):
        Stock = apps.get_model('stocks', 'Stock')

        stocks = Stock.objects.all()
        if not stocks.exists():
            self.stdout.write(self.style.ERROR("No stocks found in the database."))
            return

        symbols = [stock.symbol for stock in stocks]

        for symbol in symbols:
            self.stdout.write(f"Fetching price for {symbol}")
            try:
                data = fetch_data_for_companies(symbol)
            except RuntimeError as exc:
                self.stdout.write(self.style.ERROR(f"Failed to fetch price for {symbol}: {exc}"))
                continue

            if data:
                for stock_info in data:
                    fetched_symbol = stock_info.get('symbol')
                    current_price = stock_info.get('price', 0.0)

                    try:
                        stock = Stock.objects.get(symbol=fetched_symbol)
                        stock.current_price = current_price
                        stock.save()
                        self.stdout.write(self.style.SUCCESS(f"Updated {fetched_symbol} to {current_price}"))
                    except Stock.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Stock {fetched_symbol} not found in database"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to fetch price for {symbol}"))
