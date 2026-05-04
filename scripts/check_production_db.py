"""Check production database status."""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

# Force production database
os.environ["DATABASE_URL"] = "PRODUCTION"  # Will trigger Secrets Manager lookup

from kiwi_finance.database import init_db, get_connection

try:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n=== Production Database Status ===\n")
    
    # Check users
    cur.execute("SELECT id, email FROM users")
    users = cur.fetchall()
    print(f"Users: {len(users)}")
    for user in users:
        print(f"  - User {user[0]}: {user[1]}")
    
    # Check transactions
    cur.execute("SELECT COUNT(*) FROM transactions")
    tx_count = cur.fetchone()[0]
    print(f"\nTotal Transactions: {tx_count}")
    
    if tx_count > 0:
        cur.execute("SELECT MIN(date), MAX(date) FROM transactions")
        date_range = cur.fetchone()
        print(f"Date Range: {date_range[0]} to {date_range[1]}")
        
        # Check recent transactions
        cur.execute("""
            SELECT date, COUNT(*) 
            FROM transactions 
            WHERE date >= '2026-04-26' AND date <= '2026-05-02'
            GROUP BY date 
            ORDER BY date
        """)
        april_data = cur.fetchall()
        if april_data:
            print(f"\nApril 26 - May 2 Data:")
            for row in april_data:
                print(f"  {row[0]}: {row[1]} transactions")
        else:
            print(f"\nNo transactions found for April 26 - May 2")
    
    # Check Plaid items
    cur.execute("SELECT COUNT(*) FROM plaid_items")
    items_count = cur.fetchone()[0]
    print(f"\nPlaid Items: {items_count}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error connecting to production database: {e}")
    print("\nThis script needs to run in an environment with access to AWS Secrets Manager")
    print("and the DATABASE_URL_SECRET_ARN environment variable set.")
