"""
Database layer — supports both SQLite (local dev) and PostgreSQL (production).

Set DATABASE_URL in .env to use PostgreSQL:
  DATABASE_URL=postgresql://user:password@host:5432/dbname

Leave DATABASE_URL unset to use the local SQLite file.
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from kiwi_finance.config import Config

# ── Backend detection ────────────────────────────────────────────────────────

def _get_database_url():
    """Resolve DATABASE_URL from env directly, or assemble from Secrets Manager ARNs."""
    direct = Config.DATABASE_URL
    if direct:
        return direct

    url_arn = Config.DATABASE_URL_SECRET_ARN
    if url_arn:
        import boto3, json
        client = boto3.client("secretsmanager")
        # DatabaseUrlSecret contains host/port/dbname/username/master_secret_arn
        conn = json.loads(client.get_secret_value(SecretId=url_arn)["SecretString"])
        pw   = json.loads(client.get_secret_value(SecretId=conn["master_secret_arn"])["SecretString"])["password"]
        return f"postgresql://{conn['username']}:{pw}@{conn['host']}:{conn['port']}/{conn['dbname']}"

    return None


def _is_postgres():
    return bool(_get_database_url())


def _pg_conn():
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(_get_database_url())
    conn.autocommit = False
    return conn


def _sqlite_conn():
    path = Path(Config.DATABASE_PATH) if Config.DATABASE_PATH else (
        Path(__file__).resolve().parents[2] / "data" / "kiwi_finance.db"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """Context manager that yields a (connection, cursor) and handles commit/close."""
    if _is_postgres():
        import psycopg2.extras
        conn = _pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn = _sqlite_conn()
        cur = conn.cursor()
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _row(cur):
    """Fetch one row as a plain dict, or None."""
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def _rows(cur):
    """Fetch all rows as plain dicts."""
    return [dict(r) for r in cur.fetchall()]


# ── SQL dialect helpers ──────────────────────────────────────────────────────

def _p(n=1):
    """Return n positional placeholders for the active backend."""
    ph = "%s" if _is_postgres() else "?"
    return ", ".join([ph] * n)


def _ph():
    return "%s" if _is_postgres() else "?"


def _now():
    return "NOW()" if _is_postgres() else "datetime('now')"


# ── Schema ───────────────────────────────────────────────────────────────────

def init_db():
    with get_db() as (conn, cur):
        if _is_postgres():
            _init_postgres(cur)
        else:
            _init_sqlite(cur)


def _init_postgres(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS plaid_items (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        item_id TEXT NOT NULL UNIQUE,
        access_token TEXT NOT NULL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id SERIAL PRIMARY KEY,
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
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        plaid_transaction_id TEXT NOT NULL UNIQUE,
        plaid_account_id TEXT NOT NULL,
        name TEXT NOT NULL,
        merchant_name TEXT,
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        pending INTEGER NOT NULL,
        iso_currency_code TEXT,
        unofficial_currency_code TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_state (
        item_id TEXT PRIMARY KEY,
        transactions_cursor TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        first_name TEXT,
        last_name TEXT,
        monthly_income REAL,
        savings_goal_amount REAL,
        savings_goal_date TEXT,
        debt_payoff_goal REAL,
        preferred_currency TEXT NOT NULL DEFAULT 'USD',
        profile_photo_url TEXT,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""")


def _init_sqlite(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS plaid_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        item_id TEXT NOT NULL UNIQUE,
        access_token TEXT NOT NULL
    )""")

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
    )""")

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
    )""")

    # Migrate sync_state key if needed
    cur.execute("PRAGMA table_info(sync_state)")
    cols = {row[1] for row in cur.fetchall()}
    if cols and "user_id" in cols and "item_id" not in cols:
        cur.execute("DROP TABLE sync_state")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sync_state (
        item_id TEXT PRIMARY KEY,
        transactions_cursor TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        first_name TEXT,
        last_name TEXT,
        monthly_income REAL,
        savings_goal_amount REAL,
        savings_goal_date TEXT,
        debt_payoff_goal REAL,
        preferred_currency TEXT NOT NULL DEFAULT 'USD',
        profile_photo_url TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""")


# ── Plaid items ──────────────────────────────────────────────────────────────

def save_item(user_id: str, item_id: str, access_token: str):
    ph = _ph()
    with get_db() as (conn, cur):
        if _is_postgres():
            cur.execute(f"""
            INSERT INTO plaid_items (user_id, item_id, access_token)
            VALUES ({ph}, {ph}, {ph})
            ON CONFLICT (item_id) DO UPDATE
              SET user_id = EXCLUDED.user_id, access_token = EXCLUDED.access_token
            """, (user_id, item_id, access_token))
        else:
            cur.execute(
                "INSERT OR REPLACE INTO plaid_items (user_id, item_id, access_token) VALUES (?, ?, ?)",
                (user_id, item_id, access_token),
            )


def get_all_items(user_id: str):
    with get_db() as (conn, cur):
        cur.execute(
            f"SELECT item_id, access_token FROM plaid_items WHERE user_id = {_ph()} ORDER BY id ASC",
            (user_id,),
        )
        return _rows(cur)


def get_access_token(user_id: str):
    with get_db() as (conn, cur):
        cur.execute(
            f"SELECT access_token FROM plaid_items WHERE user_id = {_ph()} ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = _row(cur)
        return row["access_token"] if row else None


# ── Sync state ───────────────────────────────────────────────────────────────

def save_transactions_cursor(item_id: str, cursor: str | None):
    ph = _ph()
    with get_db() as (conn, cur):
        if _is_postgres():
            cur.execute(f"""
            INSERT INTO sync_state (item_id, transactions_cursor) VALUES ({ph}, {ph})
            ON CONFLICT (item_id) DO UPDATE SET transactions_cursor = EXCLUDED.transactions_cursor
            """, (item_id, cursor))
        else:
            cur.execute("""
            INSERT INTO sync_state (item_id, transactions_cursor) VALUES (?, ?)
            ON CONFLICT(item_id) DO UPDATE SET transactions_cursor = excluded.transactions_cursor
            """, (item_id, cursor))


def get_transactions_cursor(item_id: str):
    with get_db() as (conn, cur):
        cur.execute(
            f"SELECT transactions_cursor FROM sync_state WHERE item_id = {_ph()}",
            (item_id,),
        )
        row = _row(cur)
        return row["transactions_cursor"] if row else None


# ── Accounts ─────────────────────────────────────────────────────────────────

def save_accounts(item_id: str, accounts: list):
    ph = _ph()
    with get_db() as (conn, cur):
        for account in accounts:
            balances = account.get("balances", {})
            vals = (
                account["account_id"], item_id, account["name"],
                account.get("official_name"), account["type"], account.get("subtype"),
                account.get("mask"), balances.get("current"), balances.get("available"),
                balances.get("iso_currency_code"),
            )
            if _is_postgres():
                cur.execute(f"""
                INSERT INTO accounts
                  (plaid_account_id, item_id, name, official_name, type, subtype,
                   mask, current_balance, available_balance, iso_currency_code)
                VALUES ({_p(10)})
                ON CONFLICT (plaid_account_id) DO UPDATE SET
                  item_id=EXCLUDED.item_id, name=EXCLUDED.name,
                  official_name=EXCLUDED.official_name, type=EXCLUDED.type,
                  subtype=EXCLUDED.subtype, mask=EXCLUDED.mask,
                  current_balance=EXCLUDED.current_balance,
                  available_balance=EXCLUDED.available_balance,
                  iso_currency_code=EXCLUDED.iso_currency_code
                """, vals)
            else:
                cur.execute("""
                INSERT OR REPLACE INTO accounts
                  (plaid_account_id, item_id, name, official_name, type, subtype,
                   mask, current_balance, available_balance, iso_currency_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, vals)


def get_accounts_local(user_id: str | None = None):
    with get_db() as (conn, cur):
        if user_id is not None:
            cur.execute(f"""
            SELECT a.* FROM accounts a
            JOIN plaid_items p ON a.item_id = p.item_id
            WHERE p.user_id = {_ph()}
            ORDER BY a.type, a.subtype, a.name
            """, (user_id,))
        else:
            cur.execute("SELECT * FROM accounts")
        return _rows(cur)


# ── Transactions ─────────────────────────────────────────────────────────────

def save_transactions(transactions: list):
    with get_db() as (conn, cur):
        for txn in transactions:
            vals = (
                txn["transaction_id"], txn["account_id"], txn["name"],
                txn.get("merchant_name"), txn["amount"], txn["date"],
                1 if txn.get("pending") else 0,
                txn.get("iso_currency_code"), txn.get("unofficial_currency_code"),
            )
            if _is_postgres():
                cur.execute(f"""
                INSERT INTO transactions
                  (plaid_transaction_id, plaid_account_id, name, merchant_name,
                   amount, date, pending, iso_currency_code, unofficial_currency_code)
                VALUES ({_p(9)})
                ON CONFLICT (plaid_transaction_id) DO UPDATE SET
                  plaid_account_id=EXCLUDED.plaid_account_id, name=EXCLUDED.name,
                  merchant_name=EXCLUDED.merchant_name, amount=EXCLUDED.amount,
                  date=EXCLUDED.date, pending=EXCLUDED.pending,
                  iso_currency_code=EXCLUDED.iso_currency_code,
                  unofficial_currency_code=EXCLUDED.unofficial_currency_code
                """, vals)
            else:
                cur.execute("""
                INSERT OR REPLACE INTO transactions
                  (plaid_transaction_id, plaid_account_id, name, merchant_name,
                   amount, date, pending, iso_currency_code, unofficial_currency_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, vals)


def remove_transactions(transaction_ids: list[str]):
    if not transaction_ids:
        return
    with get_db() as (conn, cur):
        for tid in transaction_ids:
            cur.execute(
                f"DELETE FROM transactions WHERE plaid_transaction_id = {_ph()}",
                (tid,),
            )


def get_transactions_local(user_id: str | None = None):
    with get_db() as (conn, cur):
        if user_id is not None:
            cur.execute(f"""
            SELECT t.* FROM transactions t
            JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
            JOIN plaid_items p ON a.item_id = p.item_id
            WHERE p.user_id = {_ph()}
            ORDER BY t.date DESC, t.id DESC
            """, (user_id,))
        else:
            cur.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC")
        return _rows(cur)


# ── Users ────────────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str):
    with get_db() as (conn, cur):
        if _is_postgres():
            cur.execute(
                f"INSERT INTO users (email, password_hash) VALUES ({_p(2)}) RETURNING id",
                (email.lower().strip(), password_hash),
            )
            return _row(cur)["id"]
        else:
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email.lower().strip(), password_hash),
            )
            return cur.lastrowid


def get_user_by_email(email: str):
    with get_db() as (conn, cur):
        cur.execute(
            f"SELECT * FROM users WHERE email = {_ph()}",
            (email.lower().strip(),),
        )
        return _row(cur)


def get_user_by_id(user_id: int):
    with get_db() as (conn, cur):
        cur.execute(f"SELECT * FROM users WHERE id = {_ph()}", (user_id,))
        return _row(cur)


# ── User profiles ────────────────────────────────────────────────────────────

def get_user_profile(user_id: int):
    with get_db() as (conn, cur):
        cur.execute(
            f"SELECT * FROM user_profiles WHERE user_id = {_ph()}",
            (user_id,),
        )
        return _row(cur) or {}


def save_user_profile(user_id: int, data: dict):
    fields = [
        "first_name", "last_name", "monthly_income",
        "savings_goal_amount", "savings_goal_date",
        "debt_payoff_goal", "preferred_currency", "profile_photo_url",
    ]
    filtered = {k: data[k] for k in fields if k in data}

    with get_db() as (conn, cur):
        ph = _ph()
        now = _now()
        if _is_postgres():
            cur.execute(
                f"INSERT INTO user_profiles (user_id) VALUES ({ph}) ON CONFLICT (user_id) DO NOTHING",
                (user_id,),
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)",
                (user_id,),
            )

        if filtered:
            set_clauses = ", ".join(f"{k} = {ph}" for k in filtered)
            values = list(filtered.values()) + [user_id]
            cur.execute(
                f"UPDATE user_profiles SET {set_clauses}, updated_at = {now} WHERE user_id = {ph}",
                values,
            )


# ── Legacy helper (used by reports.py) ───────────────────────────────────────

def get_connection():
    """
    Returns a raw connection for use by reports.py.
    For SQLite, sets row_factory. For Postgres, caller gets a plain psycopg2 conn.
    Kept for backward compatibility with reports.py _fetch_all/_fetch_one helpers.
    """
    if _is_postgres():
        return _pg_conn()
    return _sqlite_conn()
