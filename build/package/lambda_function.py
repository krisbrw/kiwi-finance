"""
Kiwi Finance — Lambda entry point.

Fetches DATABASE_URL from Secrets Manager at cold start, then runs the daily
Plaid sync pipeline and exports data to S3.

The old SQLite state_store pattern is no longer needed — Aurora persists state.
"""
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

# ── Resolve DATABASE_URL from Secrets Manager before importing app code ──────
_db_url_cache = None


def _get_database_url():
    global _db_url_cache
    if _db_url_cache:
        return _db_url_cache

    import boto3, json
    client = boto3.client("secretsmanager")
    url_secret_arn = os.environ.get("DATABASE_URL_SECRET_ARN")
    if not url_secret_arn:
        raise RuntimeError("DATABASE_URL_SECRET_ARN must be set")
    conn = json.loads(client.get_secret_value(SecretId=url_secret_arn)["SecretString"])
    pw   = json.loads(client.get_secret_value(SecretId=conn["master_secret_arn"])["SecretString"])["password"]
    _db_url_cache = f"postgresql://{conn['username']}:{pw}@{conn['host']}:{conn['port']}/{conn['dbname']}"
    return _db_url_cache


# Inject into environment so Config picks it up before any app module loads
os.environ["DATABASE_URL"] = _get_database_url()

# ── Now safe to import app code ───────────────────────────────────────────────
from kiwi_finance.config import Config
from kiwi_finance.database import init_db
from kiwi_finance.pipeline import fetch_and_save_accounts, sync_transactions_for_user
from kiwi_finance.s3_export import upload_accounts_to_s3, upload_transactions_to_s3


def run_daily_job():
    init_db()

    from kiwi_finance.database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users")
    user_ids = [str(row[0]) for row in cur.fetchall()]
    cur.close()
    conn.close()

    results = []
    for user_id in user_ids:
        try:
            accounts = fetch_and_save_accounts(user_id)
            transactions = sync_transactions_for_user(user_id)
            accounts_export = upload_accounts_to_s3(user_id=user_id)
            transactions_export = upload_transactions_to_s3(user_id=user_id)
            results.append({
                "user_id": user_id,
                "accounts_fetched": len(accounts.get("accounts", [])),
                "transactions_sync": transactions,
                "accounts_export": accounts_export,
                "transactions_export": transactions_export,
            })
        except Exception as exc:
            results.append({"user_id": user_id, "error": str(exc)})

    return {
        "status": "ok",
        "users_processed": len(results),
        "user_results": results,
    }


def lambda_handler(event, context):
    try:
        result = run_daily_job()
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as exc:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "error": str(exc)}),
        }
