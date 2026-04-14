import sqlite3
from pathlib import Path

from kiwi_finance.config import Config


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "kiwi_finance.db"


def get_db_path():
    configured_path = Config.DATABASE_PATH
    if configured_path:
        return Path(configured_path)

    return DEFAULT_DB_PATH


def get_connection():
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Existing table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS plaid_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        item_id TEXT NOT NULL UNIQUE,
        access_token TEXT NOT NULL
    )
    """)

    # NEW TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plaid_account_id TEXT NOT NULL UNIQUE,
        item_id TEXT NOT NULL,
        name TEXT NOT NULL,
        official_name TEXT,
        type TEXT NOT NULL,
        subtype TEXT,
        mask TEXT,
        current_balance REAL,
        available_balance REAL,
        iso_currency_code TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plaid_transaction_id TEXT NOT NULL UNIQUE,
        plaid_account_id TEXT NOT NULL,
        name TEXT NOT NULL,
        merchant_name TEXT,
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        pending INTEGER NOT NULL,
        iso_currency_code TEXT,
        unofficial_currency_code TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_state (
        user_id TEXT PRIMARY KEY,
        transactions_cursor TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_item(user_id: str, item_id: str, access_token: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT OR REPLACE INTO plaid_items (user_id, item_id, access_token)
    VALUES (?, ?, ?)
    """, (user_id, item_id, access_token))

    conn.commit()
    conn.close()


def get_access_token(user_id: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT access_token
    FROM plaid_items
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT 1
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    return row["access_token"] if row else None


def save_transactions_cursor(user_id: str, cursor: str | None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO sync_state (user_id, transactions_cursor)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET transactions_cursor = excluded.transactions_cursor
    """, (user_id, cursor))

    conn.commit()
    conn.close()


def get_transactions_cursor(user_id: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT transactions_cursor
    FROM sync_state
    WHERE user_id = ?
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    return row["transactions_cursor"] if row else None

def save_accounts(item_id: str, accounts: list):

    conn = get_connection()
    cur = conn.cursor()

    for account in accounts:

        balances = account.get("balances", {})

        cur.execute("""
        INSERT OR REPLACE INTO accounts (
            plaid_account_id,
            item_id,
            name,
            official_name,
            type,
            subtype,
            mask,
            current_balance,
            available_balance,
            iso_currency_code
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account["account_id"],
            item_id,
            account["name"],
            account.get("official_name"),
            account["type"],
            account.get("subtype"),
            account.get("mask"),
            balances.get("current"),
            balances.get("available"),
            balances.get("iso_currency_code"),
        ))

    conn.commit()
    conn.close()

def get_accounts_local():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM accounts
    """)

    rows = cur.fetchall()

    conn.close()

    return [dict(row) for row in rows]

def save_transactions(transactions: list):
    conn = get_connection()
    cur = conn.cursor()

    for txn in transactions:
        cur.execute("""
        INSERT OR REPLACE INTO transactions (
            plaid_transaction_id,
            plaid_account_id,
            name,
            merchant_name,
            amount,
            date,
            pending,
            iso_currency_code,
            unofficial_currency_code
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            txn["transaction_id"],
            txn["account_id"],
            txn["name"],
            txn.get("merchant_name"),
            txn["amount"],
            txn["date"],
            1 if txn.get("pending") else 0,
            txn.get("iso_currency_code"),
            txn.get("unofficial_currency_code"),
        ))

    conn.commit()
    conn.close()


def remove_transactions(transaction_ids: list[str]):
    if not transaction_ids:
        return

    conn = get_connection()
    cur = conn.cursor()

    cur.executemany("""
    DELETE FROM transactions
    WHERE plaid_transaction_id = ?
    """, [(transaction_id,) for transaction_id in transaction_ids])

    conn.commit()
    conn.close()

def get_transactions_local():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM transactions
    ORDER BY date DESC, id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]
