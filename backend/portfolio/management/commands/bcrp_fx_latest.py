from decimal import Decimal, InvalidOperation, DivisionByZero
from django.core.management.base import BaseCommand, CommandError
from portfolio.integrations import bcrp_client as bcrp


class Command(BaseCommand):
    help = (
        "Fetch the latest USD<->PEN exchange rate from BCRPData and print it. "
        "Auto-selects intraday/cierre compra/venta series unless --series is provided."
    )

    def add_arguments(self, parser):
        parser.add_argument("--series", dest="series", default=None, help="Explicit BCRP series code (overrides auto)")
        parser.add_argument("--mode", dest="mode", choices=["auto", "intraday", "cierre"], default="auto",
                            help="In auto: cierre by default; intraday only 11:05–13:29 America/Lima")
        parser.add_argument("--direction", dest="direction", choices=["both", "pen2usd", "usd2pen"], default="both",
                            help="pen2usd uses venta; usd2pen uses compra")

    def handle(self, *args, **opts):
        series = opts["series"]
        mode = opts.get("mode")
        direction = opts.get("direction")

        if series:
            d, v = bcrp.get_latest(series)
            self._print_rate(series, d, v)
            return

        results = []
        if direction in ("both", "usd2pen"):
            used, d, v = bcrp.resolve_latest_auto(mode=mode, direction='compra')
            results.append(("USD->PEN (compra)", used, d, v))
        if direction in ("both", "pen2usd"):
            used, d, v = bcrp.resolve_latest_auto(mode=mode, direction='venta')
            results.append(("PEN->USD (venta)", used, d, v))

        self.stdout.write(self.style.SUCCESS("BCRP latest FX (auto):"))
        for label, used, d, v in results:
            try:
                rate_pen_per_usd = Decimal(str(v))
                inv = Decimal('1') / rate_pen_per_usd if rate_pen_per_usd != 0 else Decimal('0')
                disp = self._disp_date(d)
                self.stdout.write(f"{label}: {rate_pen_per_usd:.3f} S/ por USD (series {used}, date {disp}); inverse {inv:.3f} USD por S/")
            except (InvalidOperation, DivisionByZero):
                raise CommandError(f"Invalid numeric rate from series {used}: {v}")

    def _disp_date(self, iso: str) -> str:
        try:
            y, m, d = map(int, str(iso).split('-'))
            return f"{d:02d}-{m:02d}-{y:04d}"
        except Exception:
            return str(iso)

    def _print_rate(self, series: str, obs_date, obs_value):
        try:
            rate_pen_per_usd = Decimal(str(obs_value))
            inv = Decimal('1') / rate_pen_per_usd
        except (InvalidOperation, DivisionByZero):
            raise CommandError(f"Invalid numeric rate in observation: {obs_value}")
        self.stdout.write(self.style.SUCCESS("BCRP latest FX"))
        self.stdout.write(f"Series: {series}")
        self.stdout.write(f"Date:   {self._disp_date(obs_date)}")
        self.stdout.write(f"USD->PEN: {rate_pen_per_usd:.3f}  S/ por USD")
        self.stdout.write(f"PEN->USD: {inv:.3f}    USD por S/")

