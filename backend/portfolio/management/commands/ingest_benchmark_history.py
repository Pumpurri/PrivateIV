import os
from datetime import timedelta
from decimal import Decimal

import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from portfolio.models import BenchmarkPrice, BenchmarkSeries


DEFAULT_BENCHMARKS = {
    'djia': {
        'name': 'Dow Jones Industrial Average (DJIA)',
        'provider_symbol': '^DJI',
        'currency': 'USD',
    },
    'nasdaq': {
        'name': 'NASDAQ Composite',
        'provider_symbol': '^IXIC',
        'currency': 'USD',
    },
    'sp500': {
        'name': 'S&P 500',
        'provider_symbol': '^GSPC',
        'currency': 'USD',
    },
    'r2k': {
        'name': 'Russell 2000',
        'provider_symbol': '^RUT',
        'currency': 'USD',
    },
}


class Command(BaseCommand):
    help = 'Fetch benchmark index history from FMP and store it in the DB.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='How many calendar days back to request.',
        )
        parser.add_argument(
            '--benchmarks',
            nargs='*',
            default=list(DEFAULT_BENCHMARKS.keys()),
            help='Subset of benchmark codes to ingest.',
        )

    def handle(self, *args, **options):
        api_key = (os.getenv('FMP_API') or '').strip()
        if not api_key:
            raise CommandError('FMP_API environment variable is required.')

        days = max(1, int(options['days']))
        requested_codes = options['benchmarks'] or list(DEFAULT_BENCHMARKS.keys())
        invalid_codes = [code for code in requested_codes if code not in DEFAULT_BENCHMARKS]
        if invalid_codes:
            raise CommandError(f'Unknown benchmark code(s): {", ".join(sorted(invalid_codes))}')

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        for code in requested_codes:
            config = DEFAULT_BENCHMARKS[code]
            series, _ = BenchmarkSeries.objects.update_or_create(
                code=code,
                defaults={
                    'name': config['name'],
                    'provider': 'fmp',
                    'provider_symbol': config['provider_symbol'],
                    'currency': config['currency'],
                    'is_active': True,
                },
            )

            payload = self._fetch_fmp_history(
                provider_symbol=config['provider_symbol'],
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                api_key=api_key,
            )

            upserts = 0
            for item in payload:
                close_value = item.get('close')
                date_value = item.get('date')
                if close_value in (None, '') or not date_value:
                    continue
                BenchmarkPrice.objects.update_or_create(
                    series=series,
                    date=date_value,
                    defaults={'close': Decimal(str(close_value))},
                )
                upserts += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'Ingested {upserts} rows for {series.name} ({series.provider_symbol})'
                )
            )

    def _fetch_fmp_history(self, *, provider_symbol, start_date, end_date, api_key):
        url = 'https://financialmodelingprep.com/stable/historical-price-eod/full'
        response = requests.get(
            url,
            params={
                'symbol': provider_symbol,
                'from': start_date,
                'to': end_date,
                'apikey': api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict):
            if isinstance(data.get('historical'), list):
                return data['historical']
            if isinstance(data.get('data'), list):
                return data['data']

        if isinstance(data, list):
            return data

        raise CommandError(f'Unexpected FMP response shape for {provider_symbol}')
