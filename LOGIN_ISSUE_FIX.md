# Login Issue Fix - Database Password Caching

## Problem

Users were unable to log in or register on the website, receiving HTTP 500 errors. The logs showed:

```
psycopg2.OperationalError: connection to server at "kiwi-finance-infra-auroracluster-..." 
failed: FATAL: password authentication failed for user "kiwidbadmin"
```

## Root Cause

The issue was caused by **password caching** combined with **automatic secret rotation**:

1. **RDS Secret Rotation**: The Aurora database has automatic password rotation enabled
   - Last rotation: May 1, 2026
   - The database password was changed automatically by AWS

2. **Password Caching Bug**: The `database.py` file cached the resolved DATABASE_URL in a global variable:
   ```python
   _resolved_url = None
   
   def _get_database_url():
       global _resolved_url
       if _resolved_url:
           return _resolved_url  # Returns cached URL with OLD password
   ```

3. **Result**: After the password was rotated, the app continued using the cached URL with the old password, causing all database connections to fail.

## Solution

**Removed the password caching** from `app/kiwi_finance/database.py`:

- The `_get_database_url()` function now fetches the password from AWS Secrets Manager on every call
- This ensures the app always uses the current password, even after rotation
- Trade-off: Slightly more API calls to Secrets Manager, but this is acceptable for the connection frequency

### Code Change

**Before:**
```python
_resolved_url = None

def _get_database_url():
    global _resolved_url
    if _resolved_url:
        return _resolved_url
    # ... fetch from secrets manager ...
    _resolved_url = url
    return _resolved_url
```

**After:**
```python
def _get_database_url():
    # ... fetch from secrets manager every time ...
    return url
```

## Deployment Steps

1. **Start Docker Desktop** (if not already running)

2. **Run the fix script:**
   ```powershell
   .\fix-login-and-deploy.ps1
   ```

   This will:
   - Build a new Docker image with the fix
   - Push it to ECR
   - Update the ECS service

3. **Wait 1-2 minutes** for the new container to start

4. **Test the fix:**
   - Visit https://mykiwifinance.com/register
   - Create a new account
   - Try logging in

## Verification

Check that the new container is running:
```powershell
aws ecs describe-services --cluster kiwi-finance-app-cluster --services kiwi-finance-app-app --region us-east-1 --query 'services[0].{runningCount:runningCount,desiredCount:desiredCount}'
```

Monitor logs for any errors:
```powershell
aws logs tail /ecs/kiwi-finance-app-app --region us-east-1 --follow
```

## Alternative Solutions (Not Implemented)

If you want to avoid the extra Secrets Manager API calls, you could:

1. **Disable automatic rotation** on the RDS secret:
   ```powershell
   aws secretsmanager cancel-rotate-secret --secret-id arn:aws:secretsmanager:us-east-1:314171434946:secret:rds!cluster-008dc46c-30f2-4c00-8d95-caf998a58cde-CqyvQr --region us-east-1
   ```

2. **Implement TTL-based caching**: Cache the password for 1 hour, then refresh

3. **Use connection pooling with retry logic**: Detect auth failures and refresh the password

For now, the simplest solution (no caching) is the most reliable.

## Files Modified

- `app/kiwi_finance/database.py` - Removed password caching
- `fix-login-and-deploy.ps1` - New deployment script
- `LOGIN_ISSUE_FIX.md` - This documentation

## Related Files

- `update-ecs-service.ps1` - ECS service update script (used by fix script)
- `infra/kiwi-finance-infra.yaml` - Aurora cluster configuration
- `infra/kiwi-finance-app.yaml` - Database secret configuration
