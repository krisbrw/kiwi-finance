from flask import Flask, jsonify, render_template, request

from kiwi_finance.config import Config
from kiwi_finance.database import (
    init_db,
    get_access_token,
    get_accounts_local,
    get_transactions_local,
    save_item,
)
from kiwi_finance.pipeline import (
    create_daily_sandbox_transactions,
    ensure_sandbox_item_connected,
    fetch_and_save_accounts,
    sync_transactions_for_user,
)
from kiwi_finance.plaid_client import (
    create_link_token,
    exchange_public_token,
)
from kiwi_finance.reports import (
    get_account_balances,
    get_dashboard_summary,
    get_spend_by_amount_bucket,
    get_spend_by_day,
    get_spend_by_merchant,
    get_recent_transactions,
    get_spend_by_month,
    get_top_merchants,
)
from kiwi_finance.s3_export import upload_accounts_to_s3, upload_transactions_to_s3

app = Flask(__name__)
USER_ID = Config.KIWI_USER_ID


def _get_dashboard_date_filters():
    return (
        request.args.get("start_date") or None,
        request.args.get("end_date") or None,
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/budget")
def budget():
    return render_template("budget.html")


@app.route("/view")
def view():
    return render_template("view.html")


@app.route("/education")
def education():
    return render_template("education.html")


@app.route("/credit")
def credit():
    return render_template("credit.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/create_link_token", methods=["POST"])
def create_link_token_route():
    response = create_link_token(USER_ID)
    return jsonify(response)


@app.route("/exchange_public_token", methods=["POST"])
def exchange_public_token_route():
    data = request.get_json()
    public_token = data["public_token"]

    response = exchange_public_token(public_token)

    save_item(
        user_id=USER_ID,
        item_id=response["item_id"],
        access_token=response["access_token"],
    )

    return jsonify({
        "status": "ok",
        "item_id": response["item_id"],
    })


@app.route("/accounts", methods=["GET"])
def accounts_route():
    if not get_access_token(USER_ID):
        return jsonify({"error": "No access token found"}), 400

    response = fetch_and_save_accounts(USER_ID)
    return jsonify(response)


@app.route("/local_accounts", methods=["GET"])
def local_accounts_route():
    accounts = get_accounts_local()
    return jsonify(accounts)


@app.route("/transactions", methods=["GET"])
def transactions_route():
    try:
        response = sync_transactions_for_user(USER_ID)
        return jsonify(response), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/sandbox_connect", methods=["GET", "POST"])
def sandbox_connect():
    access_token = get_access_token(USER_ID)
    if access_token:
        return jsonify({
            "status": "sandbox account already connected",
        })

    access_token = ensure_sandbox_item_connected(USER_ID)

    return jsonify({
        "status": "sandbox account connected",
        "access_token_saved": bool(access_token),
        "sandbox_profile": "user_transactions_dynamic",
    })

@app.route("/local_transactions", methods=["GET"])
def local_transactions_route():
    transactions = get_transactions_local()
    return jsonify(transactions)


@app.route("/export_transactions_to_s3", methods=["POST", "GET"])
def export_transactions_to_s3_route():
    result = upload_transactions_to_s3()
    status_code = 200 if result["status"] == "ok" else 400
    return jsonify(result), status_code


@app.route("/export_accounts_to_s3", methods=["POST", "GET"])
def export_accounts_to_s3_route():
    result = upload_accounts_to_s3()
    status_code = 200 if result["status"] == "ok" else 400
    return jsonify(result), status_code


@app.route("/simulate_daily_transactions", methods=["POST", "GET"])
def simulate_daily_transactions_route():
    try:
        response = create_daily_sandbox_transactions(USER_ID)
        return jsonify(response), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/run_daily_sandbox_pipeline", methods=["POST", "GET"])
def run_daily_sandbox_pipeline_route():
    ensure_sandbox_item_connected(USER_ID)
    accounts_response = fetch_and_save_accounts(USER_ID)

    try:
        simulation_response = create_daily_sandbox_transactions(USER_ID)
        transactions_response = sync_transactions_for_user(USER_ID)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    accounts_export = upload_accounts_to_s3()
    transactions_export = upload_transactions_to_s3()

    return jsonify({
        "status": "ok",
        "message": "Daily sandbox pipeline completed.",
        "sandbox_profile": "user_transactions_dynamic",
        "simulation": simulation_response,
        "transactions_sync": transactions_response,
        "accounts_export": accounts_export,
        "transactions_export": transactions_export,
    })


@app.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary_route():
    return jsonify({
        "status": "ok",
        **get_dashboard_summary(),
    })


@app.route("/api/dashboard/spend-by-month", methods=["GET"])
def dashboard_spend_by_month_route():
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    return jsonify({
        "status": "ok",
        **get_spend_by_month(
            include_pending=include_pending,
            start_date=start_date,
            end_date=end_date,
        ),
    })


@app.route("/api/dashboard/top-merchants", methods=["GET"])
def dashboard_top_merchants_route():
    limit = request.args.get("limit", default=10, type=int) or 10
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    return jsonify({
        "status": "ok",
        **get_top_merchants(
            limit=max(1, limit),
            include_pending=include_pending,
            start_date=start_date,
            end_date=end_date,
        ),
    })


@app.route("/api/dashboard/spend-by-day", methods=["GET"])
def dashboard_spend_by_day_route():
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    return jsonify({
        "status": "ok",
        **get_spend_by_day(
            include_pending=include_pending,
            start_date=start_date,
            end_date=end_date,
        ),
    })


@app.route("/api/dashboard/spend-by-merchant", methods=["GET"])
def dashboard_spend_by_merchant_route():
    limit = request.args.get("limit", type=int)
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    normalized_limit = max(1, limit) if limit is not None else None
    return jsonify({
        "status": "ok",
        **get_spend_by_merchant(
            include_pending=include_pending,
            limit=normalized_limit,
            start_date=start_date,
            end_date=end_date,
        ),
    })


@app.route("/api/dashboard/spend-by-amount", methods=["GET"])
def dashboard_spend_by_amount_route():
    bucket_size = request.args.get("bucket_size", default=10, type=int) or 10
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    return jsonify({
        "status": "ok",
        **get_spend_by_amount_bucket(
            include_pending=include_pending,
            bucket_size=max(1, bucket_size),
            start_date=start_date,
            end_date=end_date,
        ),
    })


@app.route("/api/dashboard/recent-transactions", methods=["GET"])
def dashboard_recent_transactions_route():
    limit = request.args.get("limit", default=25, type=int) or 25
    return jsonify({
        "status": "ok",
        **get_recent_transactions(limit=max(1, limit)),
    })


@app.route("/api/dashboard/account-balances", methods=["GET"])
def dashboard_account_balances_route():
    return jsonify({
        "status": "ok",
        **get_account_balances(),
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
