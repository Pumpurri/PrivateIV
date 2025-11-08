# Daily Variation Bug Fix

## Problem Summary

The daily variation was showing **S/. 2,166.89 (-17.70%)** when it should have been showing **S/. 0.66 (+0.01%)**.

### Root Cause

The `_get_historical_cash()` method in `portfolio/services/snapshot_service.py` was not properly calculating cash balances for BUY/SELL transactions with FX conversions.

**The bug:**
- BUY transactions store `amount` in the stock's native currency (USD)
- The old code used a filter `Q(transaction_type='BUY', amount__lt=0)` which didn't match because amounts were positive
- This caused BUY transactions to be ignored in cash calculations
- Result: Snapshots showed S/. 10,000 (only deposit) instead of S/. 7,739.58 (after purchases)

## What Was Fixed

### File: `portfolio/services/snapshot_service.py`

**Before:**
```python
def _get_historical_cash(cls, portfolio, snapshot_date):
    cash_data = Transaction.objects.filter(
        portfolio=portfolio,
        timestamp__date__lte=snapshot_date
    ).aggregate(
        total_cash=Sum(
            'amount',
            filter=Q(transaction_type__in=['DEPOSIT', 'WITHDRAWAL']) |
                   Q(transaction_type='BUY', amount__lt=0) |
                   Q(transaction_type='SELL', amount__gt=0)
        )
    )
    return cash_data['total_cash'] or Decimal('0.00')
```

**After:**
```python
def _get_historical_cash(cls, portfolio, snapshot_date):
    transactions = Transaction.objects.filter(
        portfolio=portfolio,
        timestamp__date__lte=snapshot_date
    ).select_related('stock').order_by('timestamp')

    cash_balance = Decimal('0.00')

    for txn in transactions:
        amount = Decimal(str(txn.amount)) if txn.amount else Decimal('0.00')
        fx_rate = Decimal(str(txn.fx_rate)) if txn.fx_rate else Decimal('1.00')

        if txn.transaction_type == Transaction.TransactionType.DEPOSIT:
            cash_balance += amount
        elif txn.transaction_type == Transaction.TransactionType.WITHDRAWAL:
            cash_balance -= amount
        elif txn.transaction_type == Transaction.TransactionType.BUY:
            cash_in_base = amount * fx_rate
            cash_balance -= cash_in_base
        elif txn.transaction_type == Transaction.TransactionType.SELL:
            cash_in_base = amount * fx_rate
            cash_balance += cash_in_base

    return cash_balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

## How to Apply the Fix

### Step 1: Verify the Fix is in Place

The fix has already been applied to `portfolio/services/snapshot_service.py`.

### Step 2: Regenerate Snapshots

Run the management command to regenerate all snapshots with the corrected calculations:

```bash
# Regenerate last 30 days for all portfolios
python manage.py regenerate_snapshots

# Regenerate all historical snapshots (recommended)
python manage.py regenerate_snapshots --all --delete-existing

# Regenerate for a specific portfolio
python manage.py regenerate_snapshots --portfolio-id 1 --all --delete-existing
```

### Step 3: Verify the Results

After regenerating snapshots, the daily variation should now show correct values:

**Expected Results:**
- Latest snapshot cash: S/. 7,739.58 (not S/. 10,000.00)
- Latest snapshot total: ~S/. 10,077.59 (not S/. 12,245.17)
- Daily variation: ~S/. 0.66 (not S/. 2,166.89)

## Example Output

### Before Fix:
```
Snapshot Date: 2025-10-29
Cash Balance:  PEN 10,000.00  ← WRONG (missing purchases)
Investment:    PEN 2,245.17
Total Value:   PEN 12,245.17

Daily Variation: PEN 2,166.89 (-17.70%)  ← WRONG
```

### After Fix:
```
Snapshot Date: 2025-10-29
Cash Balance:  PEN 7,739.58   ← CORRECT
Investment:    PEN 2,338.01
Total Value:   PEN 10,077.59

Daily Variation: PEN 0.66 (+0.01%)  ← CORRECT
```

## Transaction Verification

User sjjs0805@gmail.com transactions:
1. **DEPOSIT**: +10,000.00 PEN
2. **BUY 1 AMZN**: 221.09 USD × 3.4080 = -753.47 PEN
3. **BUY 2 AMZN**: 442.18 USD × 3.4080 = -1,506.95 PEN

**Final Cash**: 10,000.00 - 753.47 - 1,506.95 = **7,739.58 PEN** ✓

## Testing

To verify the fix is working, you can check the database directly:

```bash
python analyze_cash_discrepancy.py
```

This will show:
- Calculated cash using the old method: S/. 10,000.00
- Calculated cash using the new method: S/. 7,739.58
- Actual portfolio cash balance: S/. 7,739.58

## Additional Notes

- The fix applies FX rates correctly when converting native currency amounts to base currency
- All transaction types (DEPOSIT, WITHDRAWAL, BUY, SELL) are now handled properly
- The fix is backward compatible and will work with existing data
- Snapshots must be regenerated to reflect the corrected calculations
