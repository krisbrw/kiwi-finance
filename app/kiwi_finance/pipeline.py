from datetime import date

from kiwi_finance.database import (
    get_access_token,
    get_transactions_cursor,
    remove_transactions,
    save_accounts,
    save_item,
    save_transactions,
    save_transactions_cursor,
)
from kiwi_finance.plaid_client import (
    create_sandbox_item,
    create_sandbox_transactions,
    exchange_public_token,
    get_accounts,
    get_transactions_sync,
)


def ensure_sandbox_item_connected(user_id: str):
    access_token = get_access_token(user_id)
    if access_token:
        return access_token

    sandbox = create_sandbox_item()
    exchange = exchange_public_token(sandbox["public_token"])

    save_item(
        user_id=user_id,
        item_id=exchange["item_id"],
        access_token=exchange["access_token"],
    )

    return exchange["access_token"]


def sync_transactions_for_user(user_id: str):
    access_token = get_access_token(user_id)
    if not access_token:
        raise ValueError("No access token found")

    cursor = get_transactions_cursor(user_id)
    total_added = 0
    total_modified = 0
    total_removed = 0
    latest_response = None

    while True:
        response = get_transactions_sync(access_token, cursor)
        latest_response = response

        added = response.get("added", [])
        modified = response.get("modified", [])
        removed = response.get("removed", [])

        if added:
            save_transactions(added)
        if modified:
            save_transactions(modified)
        if removed:
            remove_transactions([
                txn["transaction_id"]
                for txn in removed
                if txn.get("transaction_id")
            ])

        total_added += len(added)
        total_modified += len(modified)
        total_removed += len(removed)

        cursor = response.get("next_cursor", cursor)
        if not response.get("has_more"):
            break

    save_transactions_cursor(user_id, cursor)

    return {
        "status": "ok",
        "added_count": total_added,
        "modified_count": total_modified,
        "removed_count": total_removed,
        "next_cursor": cursor,
        "has_more": latest_response.get("has_more", False) if latest_response else False,
    }


def create_daily_sandbox_transactions(user_id: str, run_date: date | None = None):
    access_token = get_access_token(user_id)
    if not access_token:
        raise ValueError("No access token found")

    today = run_date or date.today()
    payload = [
        {
            "date_transacted": today,
            "date_posted": today,
            "amount": 8.75,
            "description": f"Kiwi Daily Coffee {today.isoformat()}",
            "iso_currency_code": "USD",
        },
        {
            "date_transacted": today,
            "date_posted": today,
            "amount": 24.10,
            "description": f"Kiwi Daily Lunch {today.isoformat()}",
            "iso_currency_code": "USD",
        },
    ]

    response = create_sandbox_transactions(access_token, payload)
    return {
        "status": "ok",
        "message": "Sandbox transactions created.",
        "transactions_created": len(payload),
        "response": response,
    }


def fetch_and_save_accounts(user_id: str):
    access_token = get_access_token(user_id)
    if not access_token:
        raise ValueError("No access token found")

    response = get_accounts(access_token)
    item_id = response["item"]["item_id"]
    save_accounts(item_id, response["accounts"])
    return response
