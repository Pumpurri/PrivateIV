from django.core.management.base import BaseCommand, CommandError
from portfolio.services.fx_ingest_service import upsert_latest_from_bcrp


class Command(BaseCommand):
    help = "Fetch latest BCRP FX (compra/venta) and upsert into FXRate for the current session."

    def add_arguments(self, parser):
        parser.add_argument("--mode", dest="mode", choices=["auto", "intraday", "cierre"], default="auto",
                            help="auto (default), intraday, cierre")

    def handle(self, *args, **opts):
        mode = opts.get("mode")
        try:
            result = upsert_latest_from_bcrp(mode=mode)
            self.stdout.write(self.style.SUCCESS("FX ingest complete:"))
            self.stdout.write(str(result))
        except Exception as e:
            raise CommandError(str(e))

