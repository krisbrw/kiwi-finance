import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
APP_DIR = PROJECT_ROOT / "app"
sys.path.insert(0, str(APP_DIR))

from kiwi_finance.config import Config
from kiwi_finance.database import get_db_path, init_db
from kiwi_finance.pipeline import (
    create_daily_sandbox_transactions,
    ensure_sandbox_item_connected,
    fetch_and_save_accounts,
    sync_transactions_for_user,
)
from kiwi_finance.s3_export import upload_accounts_to_s3, upload_transactions_to_s3
from kiwi_finance.state_store import download_file_if_present, upload_file


def run_daily_job():
    db_path = get_db_path()
    state_restored = False
    pending_error = None

    try:
        if Config.AWS_STATE_BUCKET and Config.AWS_STATE_KEY:
            state_restored = download_file_if_present(
                Config.AWS_STATE_BUCKET,
                Config.AWS_STATE_KEY,
                db_path,
            )

        init_db()
        ensure_sandbox_item_connected(Config.KIWI_USER_ID)

        accounts_response = fetch_and_save_accounts(Config.KIWI_USER_ID)
        simulation_response = create_daily_sandbox_transactions(Config.KIWI_USER_ID)
        transactions_response = sync_transactions_for_user(Config.KIWI_USER_ID)

        accounts_export = upload_accounts_to_s3()
        transactions_export = upload_transactions_to_s3()

        return {
            "status": "ok",
            "state_restored": state_restored,
            "database_path": str(db_path),
            "sandbox_profile": "user_transactions_dynamic",
            "accounts_fetched": len(accounts_response.get("accounts", [])),
            "simulation": simulation_response,
            "transactions_sync": transactions_response,
            "accounts_export": accounts_export,
            "transactions_export": transactions_export,
        }
    except Exception as exc:
        pending_error = exc
        raise
    finally:
        if Config.AWS_STATE_BUCKET and Config.AWS_STATE_KEY and db_path.exists():
            try:
                upload_file(Config.AWS_STATE_BUCKET, Config.AWS_STATE_KEY, db_path)
            except Exception:
                if pending_error is None:
                    raise


def lambda_handler(event, context):
    try:
        result = run_daily_job()
        return {
            "statusCode": 200,
            "body": json.dumps(result),
        }
    except Exception as exc:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "error": str(exc),
            }),
        }
