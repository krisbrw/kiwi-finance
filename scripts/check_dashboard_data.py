"""Check what data the dashboard would show for a user."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from kiwi_finance.database import init_db
from kiwi_finance.reports import (
    get_dashboard_summary,
    get_spend_by_day,
    get_spend_by_merchant,
)

init_db()

user_id = "1"

print(f"\n=== Dashboard Data for User {user_id} ===\n")

# Summary
summary = get_dashboard_summary(user_id)
print("Summary:")
print(f"  Accounts: {summary['account_count']}")
print(f"  Transactions: {summary['transaction_count']}")
print(f"  Total Posted Spend: ${summary['total_posted_spend']:.2f}")
print(f"  Latest Transaction: {summary['latest_transaction_date']}")

# Recent spend by day
print("\n=== Spend by Day (Last 10 days) ===")
spend_by_day = get_spend_by_day(user_id, include_pending=False)
recent_days = spend_by_day['points'][-10:]
for day in recent_days:
    print(f"  {day['date']}: ${day['total_spend']:.2f} ({day['transaction_count']} txns)")

# Top merchants
print("\n=== Top 5 Merchants ===")
merchants = get_spend_by_merchant(user_id, include_pending=False, limit=5)
for merchant in merchants['points']:
    print(f"  {merchant['merchant']}: ${merchant['total_spend']:.2f}")

# Check specific date range
print("\n=== April 26 - May 2 Data ===")
april_data = get_spend_by_day(user_id, include_pending=False, start_date='2026-04-26', end_date='2026-05-02')
if april_data['points']:
    total = sum(float(d['total_spend']) for d in april_data['points'])
    count = sum(d['transaction_count'] for d in april_data['points'])
    print(f"  Total Spend: ${total:.2f}")
    print(f"  Total Transactions: {count}")
    print("\n  By Day:")
    for day in april_data['points']:
        print(f"    {day['date']}: ${day['total_spend']:.2f} ({day['transaction_count']} txns)")
else:
    print("  No data found!")
