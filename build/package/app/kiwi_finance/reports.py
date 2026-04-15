from kiwi_finance.database import get_connection


def _fetch_all(query: str, params: tuple = ()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def _fetch_one(query: str, params: tuple = ()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _build_date_filters(start_date: str | None = None, end_date: str | None = None):
    clauses = []
    params = []

    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)

    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)

    return clauses, params


def get_dashboard_summary():
    summary = _fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM accounts) AS account_count,
            (SELECT COUNT(*) FROM transactions) AS transaction_count,
            (
                SELECT ROUND(COALESCE(SUM(amount), 0), 2)
                FROM transactions
                WHERE pending = 0 AND amount > 0
            ) AS total_posted_spend,
            (
                SELECT ROUND(COALESCE(SUM(amount), 0), 2)
                FROM transactions
                WHERE pending = 1 AND amount > 0
            ) AS total_pending_spend,
            (SELECT MAX(date) FROM transactions) AS latest_transaction_date
        """
    ) or {}

    return {
        "account_count": summary.get("account_count", 0),
        "transaction_count": summary.get("transaction_count", 0),
        "total_posted_spend": summary.get("total_posted_spend", 0),
        "total_pending_spend": summary.get("total_pending_spend", 0),
        "latest_transaction_date": summary.get("latest_transaction_date"),
    }


def get_spend_by_month(
    include_pending: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
):
    conditions = ["amount > 0"]
    params = []

    if not include_pending:
        conditions.append("pending = 0")

    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)
    where_clause = f"WHERE {' AND '.join(conditions)}"
    rows = _fetch_all(
        """
        SELECT
            substr(date, 1, 7) AS month,
            ROUND(SUM(amount), 2) AS total_spend,
            COUNT(*) AS transaction_count
        FROM transactions
        {where_clause}
        GROUP BY substr(date, 1, 7)
        ORDER BY month
        """.format(where_clause=where_clause),
        tuple(params),
    )

    return {
        "points": rows,
        "include_pending": include_pending,
        "start_date": start_date,
        "end_date": end_date,
    }


def get_top_merchants(
    limit: int = 10,
    include_pending: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
):
    conditions = [
        "COALESCE(NULLIF(merchant_name, ''), name) IS NOT NULL",
        "amount > 0",
    ]
    params = []

    if not include_pending:
        conditions.append("pending = 0")

    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)
    params.append(limit)
    rows = _fetch_all(
        """
        SELECT
            COALESCE(NULLIF(merchant_name, ''), name) AS merchant,
            ROUND(SUM(amount), 2) AS total_spend,
            COUNT(*) AS transaction_count
        FROM transactions
        WHERE {where_clause}
        GROUP BY COALESCE(NULLIF(merchant_name, ''), name)
        ORDER BY total_spend DESC, transaction_count DESC, merchant ASC
        LIMIT ?
        """.format(where_clause=" AND ".join(conditions)),
        tuple(params),
    )

    return {
        "merchants": rows,
        "limit": limit,
        "include_pending": include_pending,
        "start_date": start_date,
        "end_date": end_date,
    }


def get_spend_by_day(
    include_pending: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
):
    conditions = ["amount > 0"]
    params = []

    if not include_pending:
        conditions.append("pending = 0")

    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)
    rows = _fetch_all(
        """
        SELECT
            date,
            ROUND(SUM(amount), 2) AS total_spend,
            COUNT(*) AS transaction_count
        FROM transactions
        WHERE {where_clause}
        GROUP BY date
        ORDER BY date
        """.format(where_clause=" AND ".join(conditions)),
        tuple(params),
    )

    return {
        "points": rows,
        "include_pending": include_pending,
        "start_date": start_date,
        "end_date": end_date,
    }


def get_spend_by_merchant(
    include_pending: bool = False,
    limit: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    conditions = [
        "COALESCE(NULLIF(merchant_name, ''), name) IS NOT NULL",
        "amount > 0",
    ]
    params = []

    if not include_pending:
        conditions.append("pending = 0")

    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)
    limit_clause = "LIMIT ?" if limit is not None else ""
    if limit is not None:
        params.append(limit)
    rows = _fetch_all(
        """
        SELECT
            COALESCE(NULLIF(merchant_name, ''), name) AS merchant,
            ROUND(SUM(amount), 2) AS total_spend,
            COUNT(*) AS transaction_count
        FROM transactions
        WHERE {where_clause}
        GROUP BY COALESCE(NULLIF(merchant_name, ''), name)
        ORDER BY total_spend DESC, transaction_count DESC, merchant ASC
        {limit_clause}
        """.format(where_clause=" AND ".join(conditions), limit_clause=limit_clause),
        tuple(params),
    )

    return {
        "points": rows,
        "include_pending": include_pending,
        "limit": limit,
        "start_date": start_date,
        "end_date": end_date,
    }


def get_spend_by_amount_bucket(
    include_pending: bool = False,
    bucket_size: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
):
    bucket_size = max(1, bucket_size)
    conditions = ["amount > 0"]

    if not include_pending:
        conditions.append("pending = 0")

    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    rows = _fetch_all(
        """
        SELECT
            CAST(amount / ? AS INTEGER) * ? AS bucket_start,
            CAST(amount / ? AS INTEGER) * ? + ? AS bucket_end,
            ROUND(SUM(amount), 2) AS total_spend,
            COUNT(*) AS transaction_count
        FROM transactions
        WHERE {where_clause}
        GROUP BY CAST(amount / ? AS INTEGER)
        ORDER BY bucket_start
        """.format(where_clause=" AND ".join(conditions)),
        (
            bucket_size,
            bucket_size,
            bucket_size,
            bucket_size,
            bucket_size,
            *date_params,
            bucket_size,
        ),
    )

    for row in rows:
        row["bucket_label"] = f"${int(row['bucket_start'])}-${int(row['bucket_end'] - 0.01)}"

    return {
        "points": rows,
        "include_pending": include_pending,
        "bucket_size": bucket_size,
        "start_date": start_date,
        "end_date": end_date,
    }


def get_recent_transactions(limit: int = 25):
    rows = _fetch_all(
        """
        SELECT
            plaid_transaction_id,
            plaid_account_id,
            name,
            merchant_name,
            amount,
            date,
            pending,
            iso_currency_code,
            unofficial_currency_code
        FROM transactions
        ORDER BY date DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )

    return {
        "transactions": rows,
        "limit": limit,
    }


def get_account_balances():
    rows = _fetch_all(
        """
        SELECT
            plaid_account_id,
            name,
            official_name,
            type,
            subtype,
            mask,
            current_balance,
            available_balance,
            iso_currency_code
        FROM accounts
        ORDER BY type, subtype, name
        """
    )

    return {
        "accounts": rows,
    }
