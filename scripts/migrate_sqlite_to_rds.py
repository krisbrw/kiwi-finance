"""
Migrate Kiwi Finance data from local SQLite to PostgreSQL (RDS/Aurora).

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/migrate_sqlite_to_rds.py

What it does:
    1. Reads all data from the local SQLite file
    2. Connects to PostgreSQL via DATABASE_URL
    3. Runs alembic migrations to create the schema if needed
    4. Inserts all rows — skipping any that already exist (safe to re-run)
    5. Prints a summary

Requirements:
    - DATABASE_URL must be set in the environment or .env
    - Run from the project root
"""
import os
import sys
import sqlite3
from pathlib import Path

# ── Bootstrap paths ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# Resolve DATABASE_URL from either direct env var or AWS Secrets Manager
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_URL_SECRET_ARN = os.environ.get("DATABASE_URL_SECRET_ARN")

if not DATABASE_URL and DATABASE_URL_SECRET_ARN:
    print(f"Resolving DATABASE_URL from Secrets Manager: {DATABASE_URL_SECRET_ARN}")
    import boto3
    import json
    client = boto3.client("secretsmanager")
    
    # Get the connection info secret
    conn_secret = json.loads(client.get_secret_value(SecretId=DATABASE_URL_SECRET_ARN)["SecretString"])
    
    # Get the password from the master secret
    pw_secret = json.loads(client.get_secret_value(SecretId=conn_secret["master_secret_arn"])["SecretString"])
    password = pw_secret["password"]
    
    # Build the DATABASE_URL
    DATABASE_URL = f"postgresql://{conn_secret['username']}:{password}@{conn_secret['host']}:{conn_secret['port']}/{conn_secret['dbname']}"
    print("DATABASE_URL resolved from Secrets Manager.")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set. Export it before running this script.")
    print("  Example: set DATABASE_URL=postgresql://user:pass@host:5432/dbname")
    print("  Or set DATABASE_URL_SECRET_ARN to resolve from AWS Secrets Manager")
    sys.exit(1)

# ── Source: SQLite ────────────────────────────────────────────────────────────
sqlite_path = os.environ.get("DATABASE_PATH") or str(PROJECT_ROOT / "data" / "kiwi_finance.db")

# If running inside a container, download from S3
S3_SQLITE = os.environ.get("SQLITE_S3_URI")  # e.g. s3://bucket/migration/kiwi_finance.db
if S3_SQLITE and not Path(sqlite_path).exists():
    print(f"Downloading SQLite from {S3_SQLITE}...")
    import boto3
    s3 = boto3.client("s3")
    parts = S3_SQLITE.replace("s3://", "").split("/", 1)
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(parts[0], parts[1], sqlite_path)
    print("Downloaded.")

if not Path(sqlite_path).exists():
    print(f"ERROR: SQLite database not found at {sqlite_path}")
    sys.exit(1)

print(f"Source SQLite:  {sqlite_path}")
print(f"Target Postgres: {DATABASE_URL.split('@')[-1]}")  # hide credentials
print()

src = sqlite3.connect(sqlite_path)
src.row_factory = sqlite3.Row


def fetch_all(table: str):
    return [dict(r) for r in src.execute(f"SELECT * FROM {table}").fetchall()]


# ── Target: PostgreSQL ────────────────────────────────────────────────────────
import psycopg2
import psycopg2.extras

dst = psycopg2.connect(DATABASE_URL)
dst.autocommit = False
cur = dst.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def pg_exec(sql, params=None):
    cur.execute(sql, params or ())


# ── Run alembic migrations ────────────────────────────────────────────────────
print("Running alembic migrations on target database...")
import subprocess
result = subprocess.run(
    ["alembic", "upgrade", "head"],
    env={**os.environ, "DATABASE_URL": DATABASE_URL},
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    print("Alembic migration failed:")
    print(result.stdout)
    print(result.stderr)
    sys.exit(1)
print("Schema is up to date.\n")


# ── Migrate each table ────────────────────────────────────────────────────────

def migrate_users():
    rows = fetch_all("users")
    inserted = 0
    for r in rows:
        cur.execute("""
            INSERT INTO users (id, email, password_hash, created_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING
        """, (r["id"], r["email"], r["password_hash"], r["created_at"]))
        inserted += cur.rowcount
    # Keep the sequence in sync with the max id
    if rows:
        cur.execute("SELECT setval(pg_get_serial_sequence('users','id'), MAX(id)) FROM users")
    print(f"  users:          {inserted:>5} inserted  ({len(rows)} total in SQLite)")


def migrate_user_profiles():
    rows = fetch_all("user_profiles")
    inserted = 0
    for r in rows:
        cur.execute("""
            INSERT INTO user_profiles
              (user_id, first_name, last_name, monthly_income,
               savings_goal_amount, savings_goal_date, debt_payoff_goal,
               preferred_currency, profile_photo_url, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id) DO NOTHING
        """, (
            r["user_id"], r.get("first_name"), r.get("last_name"),
            r.get("monthly_income"), r.get("savings_goal_amount"),
            r.get("savings_goal_date"), r.get("debt_payoff_goal"),
            r.get("preferred_currency", "USD"), r.get("profile_photo_url"),
            r.get("updated_at"),
        ))
        inserted += cur.rowcount
    print(f"  user_profiles:  {inserted:>5} inserted  ({len(rows)} total in SQLite)")


def migrate_plaid_items():
    rows = fetch_all("plaid_items")
    inserted = 0
    for r in rows:
        cur.execute("""
            INSERT INTO plaid_items (user_id, item_id, access_token)
            VALUES (%s, %s, %s)
            ON CONFLICT (item_id) DO NOTHING
        """, (r["user_id"], r["item_id"], r["access_token"]))
        inserted += cur.rowcount
    print(f"  plaid_items:    {inserted:>5} inserted  ({len(rows)} total in SQLite)")


def migrate_accounts():
    rows = fetch_all("accounts")
    inserted = 0
    for r in rows:
        cur.execute("""
            INSERT INTO accounts
              (plaid_account_id, item_id, name, official_name, type, subtype,
               mask, current_balance, available_balance, iso_currency_code)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (plaid_account_id) DO NOTHING
        """, (
            r["plaid_account_id"], r["item_id"], r["name"],
            r.get("official_name"), r["type"], r.get("subtype"),
            r.get("mask"), r.get("current_balance"), r.get("available_balance"),
            r.get("iso_currency_code"),
        ))
        inserted += cur.rowcount
    print(f"  accounts:       {inserted:>5} inserted  ({len(rows)} total in SQLite)")


def migrate_transactions():
    rows = fetch_all("transactions")
    inserted = 0
    for r in rows:
        cur.execute("""
            INSERT INTO transactions
              (plaid_transaction_id, plaid_account_id, name, merchant_name,
               amount, date, pending, iso_currency_code, unofficial_currency_code)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (plaid_transaction_id) DO NOTHING
        """, (
            r["plaid_transaction_id"], r["plaid_account_id"], r["name"],
            r.get("merchant_name"), r["amount"], r["date"], r["pending"],
            r.get("iso_currency_code"), r.get("unofficial_currency_code"),
        ))
        inserted += cur.rowcount
    print(f"  transactions:   {inserted:>5} inserted  ({len(rows)} total in SQLite)")


def migrate_sync_state():
    rows = fetch_all("sync_state")
    inserted = 0
    for r in rows:
        cur.execute("""
            INSERT INTO sync_state (item_id, transactions_cursor)
            VALUES (%s, %s)
            ON CONFLICT (item_id) DO NOTHING
        """, (r["item_id"], r.get("transactions_cursor")))
        inserted += cur.rowcount
    print(f"  sync_state:     {inserted:>5} inserted  ({len(rows)} total in SQLite)")


# ── Run ───────────────────────────────────────────────────────────────────────
print("Migrating data...")
try:
    migrate_users()
    migrate_user_profiles()
    migrate_plaid_items()
    migrate_accounts()
    migrate_transactions()
    migrate_sync_state()
    dst.commit()
    print("\nMigration complete. All changes committed.")
except Exception as e:
    dst.rollback()
    print(f"\nERROR: {e}")
    print("All changes rolled back. Nothing was written to PostgreSQL.")
    sys.exit(1)
finally:
    src.close()
    cur.close()
    dst.close()
