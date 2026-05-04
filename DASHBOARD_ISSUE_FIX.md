# Dashboard Issue Fix - PostgreSQL Cursor Compatibility

## Problem

After successfully logging in, the dashboard failed to load data with HTTP 400/500 errors. The browser console showed:

```
Status Code: 400 Reason: Bad Request
HTTP response headers: HTTPHeaderDict({'Server': 'nginx', 'Date': 'Sun, 03 May 2026 16:47:29 GMT', ...})
```

The server logs showed:

```
TypeError: cannot convert dictionary update sequence element #0 to a sequence
  File "/app/app/kiwi_finance/reports.py", line 29, in _fetch_one
    return dict(row) if row else None
```

## Root Cause

The `reports.py` file was not properly handling PostgreSQL cursor results:

1. **SQLite vs PostgreSQL Difference**: 
   - SQLite returns `Row` objects that can be converted to dicts with `dict(row)`
   - PostgreSQL with default cursor returns tuples, not dict-like objects

2. **Missing Cursor Factory**: The `_fetch_one()` and `_fetch_all()` functions in `reports.py` were creating cursors without specifying `RealDictCursor` for PostgreSQL

3. **Result**: When trying to convert a PostgreSQL tuple to a dict using `dict(row)`, Python raised a TypeError

## Solution

Updated `app/kiwi_finance/reports.py` to use `RealDictCursor` for PostgreSQL:

### Code Changes

**Before:**
```python
def _fetch_one(query: str, params: tuple = ()):
    conn = get_connection()
    cur = conn.cursor()  # Default cursor returns tuples for PostgreSQL
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None  # Fails on PostgreSQL tuples
    finally:
        cur.close()
        conn.close()
```

**After:**
```python
def _fetch_one(query: str, params: tuple = ()):
    conn = get_connection()
    if _is_postgres():
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None  # Now works for both databases
    finally:
        cur.close()
        conn.close()
```

The same fix was applied to `_fetch_all()`.

## Deployment

The fix was deployed using:

```powershell
# Build and push new Docker image
docker build -t 314171434946.dkr.ecr.us-east-1.amazonaws.com/kiwi-finance-app:latest .
docker push 314171434946.dkr.ecr.us-east-1.amazonaws.com/kiwi-finance-app:latest

# Update ECS service
.\update-ecs-service.ps1
```

## Verification

After deployment, verify the dashboard loads correctly:

1. **Visit the dashboard:**
   ```
   https://mykiwifinance.com/dashboard
   ```

2. **Check that all dashboard widgets load:**
   - Account summary
   - Transaction count
   - Spending charts
   - Recent transactions

3. **Monitor logs for errors:**
   ```powershell
   aws logs tail /ecs/kiwi-finance-app-app --region us-east-1 --follow
   ```

## Related Issues

This issue was related to the earlier login problem:
- **Login Issue**: Database password caching prevented authentication
- **Dashboard Issue**: PostgreSQL cursor compatibility prevented data queries

Both issues stemmed from the migration from SQLite (local dev) to PostgreSQL (production).

## Files Modified

- `app/kiwi_finance/reports.py` - Added RealDictCursor for PostgreSQL
- `DASHBOARD_ISSUE_FIX.md` - This documentation

## Prevention

To prevent similar issues in the future:

1. **Test with PostgreSQL locally** before deploying to production
2. **Use the same database backend** in dev and prod when possible
3. **Add integration tests** that run against both SQLite and PostgreSQL
4. **Use ORM** (like SQLAlchemy) to abstract database differences

## Technical Details

### Why RealDictCursor?

PostgreSQL's psycopg2 library offers different cursor types:

- **Default cursor**: Returns tuples (positional access only)
- **DictCursor**: Returns dict-like objects (deprecated)
- **RealDictCursor**: Returns actual dict objects (recommended)

Using `RealDictCursor` ensures that:
- `cur.fetchone()` returns a dict-like object
- `dict(row)` works correctly
- Column names are preserved as keys

### Database Abstraction Layer

The app uses a custom abstraction layer in `database.py`:
- `get_db()` context manager for transactions
- `_is_postgres()` to detect backend
- `_ph()` for placeholder syntax (`?` vs `%s`)
- `_now()` for current timestamp

The `reports.py` file uses a simpler pattern with `get_connection()` directly, which required manual cursor factory setup.
