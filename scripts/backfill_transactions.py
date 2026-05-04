"""
Backfill transactions for a specific date range.

This script will:
1. Reset the transaction cursor for all items (forcing a full re-sync)
2. Run the transaction sync to pull all historical data
3. Export the updated data to S3

Usage:
    python scripts/backfill_transactions.py --user-id 1
    python scripts/backfill_transactions.py --user-id 1 --reset-cursor
"""
import argparse
import sys
from pathlib import Path

# Add app to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from kiwi_finance.database import init_db, get_connection, get_all_items
from kiwi_finance.pipeline import sync_transactions_for_user, fetch_and_save_accounts
from kiwi_finance.s3_export import upload_transactions_to_s3, upload_accounts_to_s3


def reset_cursor_for_user(user_id: str):
    """Reset transaction cursor for all items belonging to a user."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Get all items for the user
    items = get_all_items(user_id)
    
    if not items:
        print(f"No items found for user {user_id}")
        return
    
    # Reset cursor for each item
    for item in items:
        item_id = item["item_id"]
        cur.execute(
            "UPDATE items SET transactions_cursor = NULL WHERE item_id = %s",
            (item_id,)
        )
        print(f"Reset cursor for item: {item_id}")
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"Successfully reset cursors for {len(items)} item(s)")


def backfill_transactions(user_id: str, reset_cursor: bool = False):
    """Backfill transactions for a user."""
    init_db()
    
    print(f"\n=== Backfilling transactions for user {user_id} ===\n")
    
    if reset_cursor:
        print("Step 1: Resetting transaction cursor...")
        reset_cursor_for_user(user_id)
        print()
    
    print("Step 2: Fetching accounts...")
    try:
        accounts_result = fetch_and_save_accounts(user_id)
        print(f"✓ Fetched {len(accounts_result.get('accounts', []))} account(s)")
    except Exception as e:
        print(f"✗ Error fetching accounts: {e}")
        return
    
    print("\nStep 3: Syncing transactions...")
    try:
        sync_result = sync_transactions_for_user(user_id)
        print(f"✓ Added: {sync_result['added_count']} transactions")
        print(f"✓ Modified: {sync_result['modified_count']} transactions")
        print(f"✓ Removed: {sync_result['removed_count']} transactions")
    except Exception as e:
        print(f"✗ Error syncing transactions: {e}")
        if "ITEM_LOGIN_REQUIRED" in str(e):
            print("\n⚠️  Your Plaid connection needs re-authentication!")
            print("Please log into your Kiwi Finance website and re-link your bank account.")
        return
    
    print("\nStep 4: Exporting to S3...")
    try:
        accounts_export = upload_accounts_to_s3(user_id=user_id)
        print(f"✓ Accounts exported: {accounts_export}")
        
        transactions_export = upload_transactions_to_s3(user_id=user_id)
        print(f"✓ Transactions exported: {transactions_export}")
    except Exception as e:
        print(f"✗ Error exporting to S3: {e}")
        return
    
    print("\n=== Backfill complete! ===\n")


def main():
    parser = argparse.ArgumentParser(description="Backfill transactions for a user")
    parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="User ID to backfill transactions for"
    )
    parser.add_argument(
        "--reset-cursor",
        action="store_true",
        help="Reset the transaction cursor to fetch all historical transactions"
    )
    
    args = parser.parse_args()
    
    backfill_transactions(args.user_id, args.reset_cursor)


if __name__ == "__main__":
    main()
