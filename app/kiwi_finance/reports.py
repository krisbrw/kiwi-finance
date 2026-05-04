from kiwi_finance.database import get_connection, _is_postgres


def _ph():
    return "%s" if _is_postgres() else "?"


def _fetch_all(query: str, params: tuple = ()):
    conn = get_connection()
    if _is_postgres():
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()
    try:
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        cur.close()
        conn.close()


def _fetch_one(query: str, params: tuple = ()):
    conn = get_connection()
    if _is_postgres():
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()
        conn.close()


def _build_date_filters(start_date=None, end_date=None):
    clauses, params = [], []
    ph = _ph()
    if start_date:
        clauses.append(f"t.date >= {ph}")
        params.append(start_date)
    if end_date:
        clauses.append(f"t.date <= {ph}")
        params.append(end_date)
    return clauses, params


_USER_JOIN = """
    JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
    JOIN plaid_items p ON a.item_id = p.item_id
"""


def get_dashboard_summary(user_id: str):
    ph = _ph()
    
    if _is_postgres():
        summary = _fetch_one(
            f"""
            SELECT
                (SELECT COUNT(*) FROM accounts a2
                 JOIN plaid_items p2 ON a2.item_id = p2.item_id
                 WHERE p2.user_id = {ph}) AS account_count,
                (SELECT COUNT(*) FROM transactions t
                 JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
                 JOIN plaid_items p ON a.item_id = p.item_id
                 WHERE p.user_id = {ph}) AS transaction_count,
                (SELECT ROUND(COALESCE(SUM(t.amount), 0)::numeric, 2) FROM transactions t
                 JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
                 JOIN plaid_items p ON a.item_id = p.item_id
                 WHERE p.user_id = {ph} AND t.pending = 0 AND t.amount > 0) AS total_posted_spend,
                (SELECT ROUND(COALESCE(SUM(t.amount), 0)::numeric, 2) FROM transactions t
                 JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
                 JOIN plaid_items p ON a.item_id = p.item_id
                 WHERE p.user_id = {ph} AND t.pending = 1 AND t.amount > 0) AS total_pending_spend,
                (SELECT MAX(t.date) FROM transactions t
                 JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
                 JOIN plaid_items p ON a.item_id = p.item_id
                 WHERE p.user_id = {ph}) AS latest_transaction_date
            """,
            (user_id, user_id, user_id, user_id, user_id),
        ) or {}
    else:
        summary = _fetch_one(
            f"""
            SELECT
                (SELECT COUNT(*) FROM accounts a2
                 JOIN plaid_items p2 ON a2.item_id = p2.item_id
                 WHERE p2.user_id = {ph}) AS account_count,
                (SELECT COUNT(*) FROM transactions t
                 JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
                 JOIN plaid_items p ON a.item_id = p.item_id
                 WHERE p.user_id = {ph}) AS transaction_count,
                (SELECT ROUND(COALESCE(SUM(t.amount), 0), 2) FROM transactions t
                 JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
                 JOIN plaid_items p ON a.item_id = p.item_id
                 WHERE p.user_id = {ph} AND t.pending = 0 AND t.amount > 0) AS total_posted_spend,
                (SELECT ROUND(COALESCE(SUM(t.amount), 0), 2) FROM transactions t
                 JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
                 JOIN plaid_items p ON a.item_id = p.item_id
                 WHERE p.user_id = {ph} AND t.pending = 1 AND t.amount > 0) AS total_pending_spend,
                (SELECT MAX(t.date) FROM transactions t
                 JOIN accounts a ON t.plaid_account_id = a.plaid_account_id
                 JOIN plaid_items p ON a.item_id = p.item_id
                 WHERE p.user_id = {ph}) AS latest_transaction_date
            """,
            (user_id, user_id, user_id, user_id, user_id),
        ) or {}

    # SQLite uses ROUND() which returns float; Postgres returns Decimal — normalise
    return {
        "account_count": summary.get("account_count", 0),
        "transaction_count": summary.get("transaction_count", 0),
        "total_posted_spend": float(summary.get("total_posted_spend") or 0),
        "total_pending_spend": float(summary.get("total_pending_spend") or 0),
        "latest_transaction_date": summary.get("latest_transaction_date"),
    }


def get_spend_by_month(user_id: str, include_pending=False, start_date=None, end_date=None):
    ph = _ph()
    conditions = ["t.amount > 0", f"p.user_id = {ph}"]
    params = [user_id]
    if not include_pending:
        conditions.append("t.pending = 0")
    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)

    rows = _fetch_all(
        f"""
        SELECT substr(t.date, 1, 7) AS month,
               ROUND(SUM(t.amount)::numeric, 2) AS total_spend,
               COUNT(*) AS transaction_count
        FROM transactions t {_USER_JOIN}
        WHERE {' AND '.join(conditions)}
        GROUP BY substr(t.date, 1, 7)
        ORDER BY month
        """ if _is_postgres() else f"""
        SELECT substr(t.date, 1, 7) AS month,
               ROUND(SUM(t.amount), 2) AS total_spend,
               COUNT(*) AS transaction_count
        FROM transactions t {_USER_JOIN}
        WHERE {' AND '.join(conditions)}
        GROUP BY substr(t.date, 1, 7)
        ORDER BY month
        """,
        tuple(params),
    )
    return {"points": rows, "include_pending": include_pending, "start_date": start_date, "end_date": end_date}


def get_top_merchants(user_id: str, limit=10, include_pending=False, start_date=None, end_date=None):
    ph = _ph()
    conditions = ["COALESCE(NULLIF(t.merchant_name,''),t.name) IS NOT NULL", "t.amount > 0", f"p.user_id = {ph}"]
    params = [user_id]
    if not include_pending:
        conditions.append("t.pending = 0")
    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)
    params.append(limit)

    rows = _fetch_all(
        f"""
        SELECT COALESCE(NULLIF(t.merchant_name,''),t.name) AS merchant,
               ROUND(SUM(t.amount)::numeric, 2) AS total_spend,
               COUNT(*) AS transaction_count
        FROM transactions t {_USER_JOIN}
        WHERE {' AND '.join(conditions)}
        GROUP BY COALESCE(NULLIF(t.merchant_name,''),t.name)
        ORDER BY total_spend DESC, transaction_count DESC, merchant ASC
        LIMIT {ph}
        """ if _is_postgres() else f"""
        SELECT COALESCE(NULLIF(t.merchant_name,''),t.name) AS merchant,
               ROUND(SUM(t.amount), 2) AS total_spend,
               COUNT(*) AS transaction_count
        FROM transactions t {_USER_JOIN}
        WHERE {' AND '.join(conditions)}
        GROUP BY COALESCE(NULLIF(t.merchant_name,''),t.name)
        ORDER BY total_spend DESC, transaction_count DESC, merchant ASC
        LIMIT {ph}
        """,
        tuple(params),
    )
    return {"merchants": rows, "limit": limit, "include_pending": include_pending, "start_date": start_date, "end_date": end_date}


def get_spend_by_day(user_id: str, include_pending=False, start_date=None, end_date=None):
    ph = _ph()
    conditions = ["t.amount > 0", f"p.user_id = {ph}"]
    params = [user_id]
    if not include_pending:
        conditions.append("t.pending = 0")
    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)

    rows = _fetch_all(
        f"""
        SELECT t.date, ROUND(SUM(t.amount)::numeric, 2) AS total_spend, COUNT(*) AS transaction_count
        FROM transactions t {_USER_JOIN}
        WHERE {' AND '.join(conditions)}
        GROUP BY t.date ORDER BY t.date
        """ if _is_postgres() else f"""
        SELECT t.date, ROUND(SUM(t.amount), 2) AS total_spend, COUNT(*) AS transaction_count
        FROM transactions t {_USER_JOIN}
        WHERE {' AND '.join(conditions)}
        GROUP BY t.date ORDER BY t.date
        """,
        tuple(params),
    )
    return {"points": rows, "include_pending": include_pending, "start_date": start_date, "end_date": end_date}


def get_spend_by_merchant(user_id: str, include_pending=False, limit=None, start_date=None, end_date=None):
    ph = _ph()
    conditions = ["COALESCE(NULLIF(t.merchant_name,''),t.name) IS NOT NULL", "t.amount > 0", f"p.user_id = {ph}"]
    params = [user_id]
    if not include_pending:
        conditions.append("t.pending = 0")
    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)
    limit_clause = f"LIMIT {ph}" if limit is not None else ""
    if limit is not None:
        params.append(limit)

    rows = _fetch_all(
        f"""
        SELECT COALESCE(NULLIF(t.merchant_name,''),t.name) AS merchant,
               ROUND(SUM(t.amount)::numeric, 2) AS total_spend,
               COUNT(*) AS transaction_count
        FROM transactions t {_USER_JOIN}
        WHERE {' AND '.join(conditions)}
        GROUP BY COALESCE(NULLIF(t.merchant_name,''),t.name)
        ORDER BY total_spend DESC, transaction_count DESC, merchant ASC
        {limit_clause}
        """ if _is_postgres() else f"""
        SELECT COALESCE(NULLIF(t.merchant_name,''),t.name) AS merchant,
               ROUND(SUM(t.amount), 2) AS total_spend,
               COUNT(*) AS transaction_count
        FROM transactions t {_USER_JOIN}
        WHERE {' AND '.join(conditions)}
        GROUP BY COALESCE(NULLIF(t.merchant_name,''),t.name)
        ORDER BY total_spend DESC, transaction_count DESC, merchant ASC
        {limit_clause}
        """,
        tuple(params),
    )
    return {"points": rows, "include_pending": include_pending, "limit": limit, "start_date": start_date, "end_date": end_date}


def get_spend_by_amount_bucket(user_id: str, include_pending=False, bucket_size=10, start_date=None, end_date=None):
    bucket_size = max(1, bucket_size)
    ph = _ph()
    conditions = ["t.amount > 0", f"p.user_id = {ph}"]
    params = [user_id]
    if not include_pending:
        conditions.append("t.pending = 0")
    date_clauses, date_params = _build_date_filters(start_date, end_date)
    conditions.extend(date_clauses)
    params.extend(date_params)

    if _is_postgres():
        rows = _fetch_all(
            f"""
            SELECT
                FLOOR(t.amount / {ph}) * {ph} AS bucket_start,
                FLOOR(t.amount / {ph}) * {ph} + {ph} AS bucket_end,
                ROUND(SUM(t.amount)::numeric, 2) AS total_spend,
                COUNT(*) AS transaction_count
            FROM transactions t {_USER_JOIN}
            WHERE {' AND '.join(conditions)}
            GROUP BY FLOOR(t.amount / {ph})
            ORDER BY bucket_start
            """,
            (bucket_size, bucket_size, bucket_size, bucket_size, bucket_size, *params, bucket_size),
        )
    else:
        rows = _fetch_all(
            f"""
            SELECT
                CAST(t.amount / ? AS INTEGER) * ? AS bucket_start,
                CAST(t.amount / ? AS INTEGER) * ? + ? AS bucket_end,
                ROUND(SUM(t.amount), 2) AS total_spend,
                COUNT(*) AS transaction_count
            FROM transactions t {_USER_JOIN}
            WHERE {' AND '.join(conditions)}
            GROUP BY CAST(t.amount / ? AS INTEGER)
            ORDER BY bucket_start
            """,
            (bucket_size, bucket_size, bucket_size, bucket_size, bucket_size, *params, bucket_size),
        )

    for row in rows:
        row["bucket_label"] = f"${int(row['bucket_start'])}-${int(float(row['bucket_end']) - 0.01)}"

    return {"points": rows, "include_pending": include_pending, "bucket_size": bucket_size, "start_date": start_date, "end_date": end_date}


def get_recent_transactions(user_id: str, limit=25):
    ph = _ph()
    rows = _fetch_all(
        f"""
        SELECT t.plaid_transaction_id, t.plaid_account_id, t.name, t.merchant_name,
               t.amount, t.date, t.pending, t.iso_currency_code, t.unofficial_currency_code
        FROM transactions t {_USER_JOIN}
        WHERE p.user_id = {ph}
        ORDER BY t.date DESC, t.id DESC
        LIMIT {ph}
        """,
        (user_id, limit),
    )
    return {"transactions": rows, "limit": limit}


def get_account_balances(user_id: str):
    ph = _ph()
    rows = _fetch_all(
        f"""
        SELECT a.plaid_account_id, a.name, a.official_name, a.type, a.subtype,
               a.mask, a.current_balance, a.available_balance, a.iso_currency_code
        FROM accounts a
        JOIN plaid_items p ON a.item_id = p.item_id
        WHERE p.user_id = {ph}
        ORDER BY a.type, a.subtype, a.name
        """,
        (user_id,),
    )
    return {"accounts": rows}
