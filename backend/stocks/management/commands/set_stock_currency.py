from django.core.management.base import BaseCommand, CommandError
from stocks.models import Stock


class Command(BaseCommand):
    help = "Set currency for existing Stock records. Defaults to USD."

    def add_arguments(self, parser):
        parser.add_argument(
            "--currency",
            dest="currency",
            default="USD",
            help="ISO 4217 currency code to set (default: USD)",
        )
        parser.add_argument(
            "--all",
            dest="all_",
            action="store_true",
            help="Update all stocks (otherwise provide --symbols)",
        )
        parser.add_argument(
            "--symbols",
            dest="symbols",
            default="",
            help="Comma or space separated list of symbols to update (e.g., AAPL, TSLA, MSFT)",
        )
        parser.add_argument(
            "--dry-run",
            dest="dry",
            action="store_true",
            help="Do not write changes; just report what would change",
        )

    def handle(self, *args, **opts):
        currency = (opts.get("currency") or "").strip().upper()
        if not currency or len(currency) != 3:
            raise CommandError("--currency must be a 3-letter ISO code (e.g., USD, PEN)")

        all_ = opts.get("all_")
        symbols_arg = opts.get("symbols") or ""
        dry = opts.get("dry")

        if not all_ and not symbols_arg:
            raise CommandError("Provide --all or --symbols to select which stocks to update")

        qs = Stock.objects.all()
        if not all_:
            # Split symbols on comma/space
            raw = [s.strip().upper() for s in symbols_arg.replace(",", " ").split() if s.strip()]
            if not raw:
                raise CommandError("--symbols provided but no valid symbols parsed")
            qs = qs.filter(symbol__in=raw)

        to_change = qs.exclude(currency=currency)
        count = to_change.count()

        if dry:
            self.stdout.write(self.style.WARNING(f"[DRY-RUN] {count} stock(s) would be updated to {currency}"))
            sample = list(to_change.values_list('symbol', flat=True)[:10])
            if sample:
                self.stdout.write(f"Sample: {', '.join(sample)}")
            return

        updated = to_change.update(currency=currency)
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} stock(s) to currency {currency}"))

