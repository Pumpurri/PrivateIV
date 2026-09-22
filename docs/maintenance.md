# Maintenance and relaunch checks

The hosted backend and background workers are intentionally paused. These steps do not require turning them on.

## Audit older cost basis

Trades made before the base-currency cost-basis fix may have incorrect holdings, realized P&L, or historical holding snapshot basis. Back up the database and audit one portfolio at a time, preferably on a restored copy first:

```bash
cd backend
python manage.py repair_trade_basis --portfolio-id 123
```

The default is a read-only dry run. Review every proposed change, including the stock's historical currency and recorded transaction FX rates, before applying:

```bash
python manage.py repair_trade_basis --portfolio-id 123 --apply
```

The command rejects missing FX rates, incomplete trades, and quantity mismatches; it never guesses a rate or edits cash balances. It cannot prove whether a stock's currency changed after an old trade, so verify that history independently before applying. Keep the backup until the corrected holdings, realized P&L, and historical snapshots have been checked.

## Before any relaunch

1. Restore a database backup into an isolated PostgreSQL environment, not the hosted production database. Run migrations and the dry-run audit there first; investigate any inconsistent trades before an apply.
2. Smoke-test registration/login, portfolio creation, PEN and USD settlement, history and performance endpoints against the isolated environment. Verify scheduled tasks and provider access with separate test credentials if needed.
3. Check the frontend API URL, allowed hosts, CORS/CSRF origins, secret configuration, and worker/beat queues. Only restart hosted services after explicitly deciding to resume them and accepting the associated hosting cost.
