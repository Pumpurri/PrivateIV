from django.core.management.base import BaseCommand
from stocks.models import Stock

class Command(BaseCommand):
    help = 'Populates the database with initial stocks'

    def handle(self, *args, **kwargs):
        initial_stocks = [
            # CHANGE FOR LOADING STOCKS MANUALLY

            # {'symbol': 'AAPL', 'name': 'Apple Inc.'},
            # {'symbol': 'MSFT', 'name': 'Microsoft Corp.'},
            # {'symbol': 'AMZN', 'name': 'Amazon.com Inc.'},
            # {'symbol': 'GOOGL', 'name': 'Alphabet Inc.'},
            # {'symbol': 'META', 'name': 'Meta Platforms Inc.'},
            # {'symbol': 'NFLX', 'name': 'Netflix Inc.'},
            # {'symbol': 'TSLA', 'name': 'Tesla Inc.'},
            # {'symbol': 'NVDA', 'name': 'NVIDIA Corp.'},
            # {'symbol': 'AMD', 'name': 'Advanced Micro Devices Inc.'},
            # {'symbol': 'INTC', 'name': 'Intel Corp.'}
        ]

        for stock_data in initial_stocks:
            Stock.objects.update_or_create(
                symbol=stock_data['symbol'],
                defaults={'name': stock_data['name']}
            )
        self.stdout.write(self.style.SUCCESS("Initial stocks added successfully."))