# Production Database Backfill Instructions

## Problem
Your **local database** (SQLite) has the backfilled data, but your **production website** (AWS) uses a separate PostgreSQL database that doesn't have the backfilled data yet.

## Solution
I've added a **Bank Accounts** page where you can re-authenticate your Plaid connections on the production website, then the Lambda will automatically backfill the data.

## Steps to Backfill Production Data

### Step 1: Deploy the Updated Code

Deploy the changes that include:
- Fixed SQL queries for both SQLite and PostgreSQL
- New "Bank Accounts" page for re-authentication
- Plaid Link update mode support

```bash
# Deploy to production
.\deploy.ps1 -ArtifactBucket "kiwi-finance-data-krisbro-314171434946"
```

### Step 2: Re-authenticate on Production Website

1. Go to your production website: **https://mykiwifinance.com**

2. Log in with your credentials

3. Navigate to **Tools → Bank Accounts** (in the dropdown menu)

4. Click **"Re-authenticate"** on each bank account that needs updating

5. Complete the Plaid Link flow to re-authenticate

### Step 3: Trigger the Backfill

After re-authenticating, manually trigger the Lambda to backfill:

```bash
# Invoke the Lambda function
aws lambda invoke --function-name kiwi-finance-app-daily-job --region us-east-1 response.json

# Check the response
cat response.json
```

The Lambda will:
- Reset transaction cursors
- Fetch all historical transactions from Plaid
- Save them to the production PostgreSQL database
- Export to S3

### Step 4: Verify the Data

1. Go back to your dashboard: **https://mykiwifinance.com/dashboard**

2. You should now see all the backfilled data from April 26 - May 2

3. Check the transaction counts and date ranges

## Alternative: Manual Production Backfill Script

If you prefer to run a backfill script directly against production:

```bash
# Set production database URL
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# Run the backfill
python scripts/production_backfill.py --user-id 1
```

**Note:** You'll need the production database credentials from AWS Secrets Manager.

## What Was Changed

### 1. Fixed SQL Compatibility (`app/kiwi_finance/reports.py`)
- Added database-specific SQL syntax
- PostgreSQL uses `::numeric` casting
- SQLite uses simple `ROUND()` function

### 2. Added Plaid Update Mode (`app/kiwi_finance/plaid_client.py`)
- `create_link_token()` now supports `access_token` parameter
- Enables re-authentication without creating new items

### 3. New Bank Accounts Page (`app/kiwi_finance/templates/accounts.html`)
- Lists all connected Plaid items
- "Re-authenticate" button for each account
- "Add Account" button for new connections

### 4. New API Endpoints (`app/kiwi_finance/main.py`)
- `GET /accounts-settings` - Bank accounts management page
- `GET /get_items` - List all Plaid items for current user
- `POST /create_link_token` - Now supports update mode

## Automated Daily Sync

Once re-authenticated, the Lambda will automatically sync new transactions:
- **Schedule**: Daily at 1 PM UTC (8 AM EST)
- **Function**: `kiwi-finance-app-daily-job`
- **Status**: ✅ Operational

## Troubleshooting

### If Lambda still shows errors:
1. Check CloudWatch logs:
   ```bash
   aws logs tail /aws/lambda/kiwi-finance-app-daily-job --follow --region us-east-1
   ```

2. Verify Plaid items are re-authenticated:
   - Go to Bank Accounts page
   - Re-authenticate any accounts showing errors

### If data still doesn't appear:
1. Clear browser cache and refresh
2. Check that you're logged in as the correct user
3. Verify the Lambda executed successfully (check response.json)

## Summary

✅ **Local database**: Has all backfilled data (April 26 - May 2)
⏳ **Production database**: Needs re-authentication → backfill
🔧 **Solution**: Deploy code → Re-auth on website → Trigger Lambda

After completing these steps, your production website will have all the historical transaction data!
