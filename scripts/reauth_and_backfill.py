"""
Re-authenticate Plaid connection and backfill transactions.

This script will guide you through:
1. Checking your current Plaid connection status
2. Providing instructions to re-authenticate via the web UI
3. Running the backfill after re-authentication

Usage:
    python scripts/reauth_and_backfill.py --user-id 1
"""
import argparse
import sys
import time
from pathlib import Path

# Add app to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from kiwi_finance.database import init_db, get_connection, get_all_items
from kiwi_finance.plaid_client import get_accounts
from kiwi_finance.pipeline import sync_transactions_for_user, fetch_and_save_accounts
from kiwi_finance.s3_export import upload_transactions_to_s3, upload_accounts_to_s3


def check_plaid_status(user_id: str):
    """Check if Plaid connection is working."""
    print(f"\n=== Checking Plaid connection status for user {user_id} ===\n")
    
    items = get_all_items(user_id)
    
    if not items:
        print("❌ No Plaid items found for this user.")
        print("\nYou need to connect a bank account first:")
        print("1. Start your local server: python run.py")
        print("2. Go to http://localhost:5000")
        print("3. Log in and connect your bank account via Plaid Link")
        return False
    
    print(f"Found {len(items)} Plaid item(s):")
    for item in items:
        print(f"  - Item ID: {item['item_id']}")
    
    print("\nTesting connections...")
    
    working_items = []
    broken_items = []
    
    for item in items:
        try:
            response = get_accounts(item["access_token"])
            print(f"✅ Item {item['item_id']}: Connection OK ({len(response.get('accounts', []))} accounts)")
            working_items.append(item)
        except Exception as e:
            error_str = str(e)
            if "ITEM_LOGIN_REQUIRED" in error_str:
                print(f"❌ Item {item['item_id']}: Re-authentication required")
                broken_items.append(item)
            else:
                print(f"❌ Item {item['item_id']}: Error - {error_str}")
                broken_items.append(item)
    
    if broken_items:
        print(f"\n⚠️  {len(broken_items)} item(s) need re-authentication!")
        print("\nTo re-authenticate:")
        print("1. Start your local server: python run.py")
        print("2. Go to http://localhost:5000")
        print("3. Log in to your account")
        print("4. Look for an option to re-link or update your bank connection")
        print("\nNote: You can still backfill data from the working items.")
        
        if working_items:
            print(f"\n{len(working_items)} item(s) are working and can be backfilled.")
            return "partial"
        return False
    
    print(f"\n✅ All {len(working_items)} item(s) are working!")
    return True


def reset_cursor_for_user(user_id: str):
    """Reset transaction cursor for all items belonging to a user."""
    from kiwi_finance.database import save_transactions_cursor
    
    items = get_all_items(user_id)
    
    if not items:
        print(f"No items found for user {user_id}")
        return
    
    for item in items:
        item_id = item["item_id"]
        save_transactions_cursor(item_id, None)
        print(f"  ✓ Reset cursor for item: {item_id}")


def backfill_transactions(user_id: str):
    """Backfill transactions after re-authentication."""
    print(f"\n=== Backfilling transactions for user {user_id} ===\n")
    
    print("Step 1: Resetting transaction cursor to fetch all historical data...")
    reset_cursor_for_user(user_id)
    
    print("\nStep 2: Syncing transactions (this may take a moment)...")
    print("Note: Items that need re-authentication will be skipped.\n")
    
    try:
        sync_result = sync_transactions_for_user(user_id)
        print(f"  ✓ Added: {sync_result['added_count']} transactions")
        print(f"  ✓ Modified: {sync_result['modified_count']} transactions")
        print(f"  ✓ Removed: {sync_result['removed_count']} transactions")
        
        if sync_result['added_count'] == 0:
            print("\n⚠️  No new transactions were added.")
            print("This could mean:")
            print("  - All transactions are already synced")
            print("  - All items need re-authentication")
            print("  - There are no transactions in the date range")
    except Exception as e:
        error_str = str(e)
        if "ITEM_LOGIN_REQUIRED" in error_str:
            print(f"  ⚠️  Some items need re-authentication (skipped)")
        elif "No items found" in error_str:
            print(f"  ✗ Error: {e}")
            return False
        else:
            print(f"  ✗ Error syncing transactions: {e}")
            return False
    
    print("\nStep 3: Fetching and saving account information...")
    try:
        accounts_result = fetch_and_save_accounts(user_id)
        print(f"  ✓ Fetched {len(accounts_result.get('accounts', []))} account(s)")
    except Exception as e:
        print(f"  ⚠️  Some accounts couldn't be fetched: {e}")
    
    print("\nStep 4: Exporting to S3...")
    try:
        accounts_export = upload_accounts_to_s3(user_id=user_id)
        print(f"  ✓ Accounts exported: {accounts_export}")
        
        transactions_export = upload_transactions_to_s3(user_id=user_id)
        print(f"  ✓ Transactions exported: {transactions_export}")
    except Exception as e:
        print(f"  ✗ Error exporting to S3: {e}")
        print("  Note: Data is still saved locally in the database")
    
    print("\n✅ Backfill complete!")
    print("\nYour data has been updated with all available historical transactions.")
    print("The daily Lambda job will continue to sync new transactions automatically.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Re-authenticate Plaid and backfill transactions"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="User ID to check and backfill"
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip the connection check and go straight to backfill"
    )
    
    args = parser.parse_args()
    
    init_db()
    
    if not args.skip_check:
        is_connected = check_plaid_status(args.user_id)
        
        if is_connected == False:
            print("\n" + "="*60)
            print("Please re-authenticate your Plaid connection first.")
            print("After re-authenticating, run this script again with:")
            print(f"  python scripts/reauth_and_backfill.py --user-id {args.user_id}")
            print("="*60 + "\n")
            sys.exit(1)
        elif is_connected == "partial":
            print("\n" + "="*60)
            response = input("Some items need re-auth. Continue with working items? (y/n): ")
            if response.lower() != 'y':
                print("Exiting. Please re-authenticate and try again.")
                sys.exit(1)
            print("="*60 + "\n")
    
    # Connection is good, proceed with backfill
    success = backfill_transactions(args.user_id)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
