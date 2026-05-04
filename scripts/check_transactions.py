"""Check transaction date range in the database."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from kiwi_finance.database import init_db, get_connection

init_db()
conn = get_connection()
cur = conn.cursor()

# Overall stats
cur.execute("SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(*) as total FROM transactions")
row = cur.fetchone()
print(f"\n=== Transaction Database Stats ===")
print(f"Date range: {row[0]} to {row[1]}")
print(f"Total transactions: {row[2]}")

# Transactions in the requested date range
cur.execute("""
    SELECT date, COUNT(*) as count 
    FROM transactions 
    WHERE date >= '2026-04-26' AND date <= '2026-05-02' 
    GROUP BY date 
    ORDER BY date
""")
rows = cur.fetchall()

print(f"\n=== Transactions by Date (Apr 26 - May 2, 2026) ===")
if rows:
    for row in rows:
        print(f"  {row[0]}: {row[1]} transactions")
    
    total = sum(row[1] for row in rows)
    print(f"\nTotal in range: {total} transactions")
else:
    print("  No transactions found in this date range")

# Recent transactions
cur.execute("""
    SELECT date, COUNT(*) as count 
    FROM transactions 
    WHERE date >= '2026-04-14'
    GROUP BY date 
    ORDER BY date DESC
    LIMIT 20
""")
rows = cur.fetchall()

print(f"\n=== Recent Transactions (since Apr 14) ===")
for row in rows:
    print(f"  {row[0]}: {row[1]} transactions")

cur.close()
conn.close()
