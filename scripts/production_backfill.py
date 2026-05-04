"""
Production Database Backfill Script

This script resets transaction cursors and syncs all historical data
from Plaid to the production Aurora database.

Can be run as:
1. An ECS task
2. A one-time Lambda invocation
3. Locally with production DATABASE_URL set

Usage:
    # Set DATABASE_URL to production
    export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
    python scripts/production_backfill.py --user-id 1
"""
import argparse
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from kiwi_finance.database import init_db, get_connection, get_all_items, save_transactions_cursor
from kiwi_finance.pipeline import sync_transactions_for_user, fetch_and_save_accounts
from kiwi_finance.s3_export import upload_transactions_to_s3, upload_accounts_to_s3


def reset_cursors(user_id: str):
    """Reset transaction cursors for all items."""
    print(f"Resetting cursors for user {user_id}...")
    items = get_all_items(user_id)
    
    if not items:
        print(f"  No items found for user {user_id}")
        return 0
    
    for item in items:
        save_transactions_cursor(item["item_id"], None)
        print(f"  ✓ Reset cursor for item: {item['item_id']}")
    
    return len(items)


def backfill_production(user_id: str, reset_cursor: bool = True):
    """Backfill production database."""
    print(f"\n{'='*60}")
    print(f"Production Database Backfill - User {user_id}")
    print(f"{'='*60}\n")
    
    init_db()
    
    if reset_cursor:
        print("Step 1: Resetting transaction cursors...")
        count = reset_cursors(user_id)
        if count == 0:
            print("  ✗ No items to backfill")
            return False
        print(f"  ✓ Reset {count} cursor(s)\n")
    
    print("Step 2: Syncing transactions from Plaid...")
    try:
        result = sync_transactions_for_user(user_id)
        print(f"  ✓ Added: {result['added_count']} transactions")
        print(f"  ✓ Modified: {result['modified_count']} transactions")
        print(f"  ✓ Removed: {result['removed_count']} transactions")
        
        if result['added_count'] == 0 and result['modified_count'] == 0:
            print("\n  ⚠️  No new transactions synced")
            print("  This could mean:")
            print("    - All transactions are already up to date")
            print("    - Plaid items need re-authentication")
    except Exception as e:
        error_str = str(e)
        if "ITEM_LOGIN_REQUIRED" in error_str:
            print(f"  ⚠️  Some items need re-authentication")
            print(f"  Error: {e}")
            print("\n  To fix:")
            print("  1. Go to your website")
            print("  2. Log in and re-link your bank accounts")
            print("  3. Run this script again")
            return False
        else:
            print(f"  ✗ Error: {e}")
            return False
    
    print("\nStep 3: Fetching account information...")
    try:
        accounts = fetch_and_save_accounts(user_id)
        print(f"  ✓ Fetched {len(accounts.get('accounts', []))} account(s)")
    except Exception as e:
        print(f"  ⚠️  Error fetching accounts: {e}")
    
    print("\nStep 4: Exporting to S3...")
    try:
        accounts_export = upload_accounts_to_s3(user_id=user_id)
        print(f"  ✓ Accounts: {accounts_export['key']}")
        
        transactions_export = upload_transactions_to_s3(user_id=user_id)
        print(f"  ✓ Transactions: {transactions_export['key']}")
    except Exception as e:
        print(f"  ⚠️  Error exporting to S3: {e}")
    
    print(f"\n{'='*60}")
    print("✅ Backfill Complete!")
    print(f"{'='*60}\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Backfill production database with historical Plaid transactions"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="User ID to backfill"
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Don't reset cursors (only sync new transactions)"
    )
    
    args = parser.parse_args()
    
    # Check if we're configured for production
    db_url = os.getenv("DATABASE_URL")
    db_secret = os.getenv("DATABASE_URL_SECRET_ARN")
    
    if not db_url and not db_secret:
        print("⚠️  WARNING: No production database configured!")
        print("This will run against the local SQLite database.")
        print("\nTo run against production:")
        print("  export DATABASE_URL='postgresql://...'")
        print("  OR")
        print("  export DATABASE_URL_SECRET_ARN='arn:aws:secretsmanager:...'")
        print()
        response = input("Continue with local database? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    success = backfill_production(args.user_id, reset_cursor=not args.no_reset)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
