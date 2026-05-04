from flask import Flask, jsonify, render_template, request, session, redirect, url_for

from kiwi_finance.auth import authenticate_user, login_required, register_user
from kiwi_finance.config import Config
from kiwi_finance.database import (
    init_db,
    get_access_token,
    get_accounts_local,
    get_all_items,
    get_transactions_local,
    get_user_by_id,
    get_user_profile,
    save_item,
    save_user_profile,
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
    get_transactions_sync,
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
app.secret_key = Config.SECRET_KEY


def _current_user_id():
    return str(session["user_id"])


def _get_dashboard_date_filters():
    return (
        request.args.get("start_date") or None,
        request.args.get("end_date") or None,
    )


# ── Public routes ────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ── Auth routes ──────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        next_url = request.form.get("next") or "/dashboard"

        user, error = authenticate_user(email, password)
        if error:
            return render_template("login.html", error=error, email=email, next=next_url)

        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        return redirect(next_url)

    return render_template("login.html", next=request.args.get("next", "/dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if password != password2:
            return render_template("register.html", error="Passwords do not match.", email=email)

        user_id, error = register_user(email, password)
        if error:
            return render_template("register.html", error=error, email=email)

        session["user_id"] = user_id
        session["user_email"] = email.lower().strip()
        return redirect("/dashboard")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ── Protected routes ─────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/budget")
@login_required
def budget():
    return render_template("budget.html")


@app.route("/view")
@login_required
def view():
    return render_template("view.html")


@app.route("/education")
@login_required
def education():
    return render_template("education.html")


@app.route("/credit")
@login_required
def credit():
    return render_template("credit.html")


@app.route("/accounts-settings")
@login_required
def accounts_settings():
    return render_template("accounts.html")


@app.route("/create_link_token", methods=["POST"])
@login_required
def create_link_token_route():
    data = request.get_json() or {}
    access_token = data.get("access_token")  # For update mode
    response = create_link_token(_current_user_id(), access_token=access_token)
    return jsonify(response)


@app.route("/get_items", methods=["GET"])
@login_required
def get_items_route():
    """Get all Plaid items for the current user."""
    items = get_all_items(_current_user_id())
    return jsonify({"items": items})


@app.route("/exchange_public_token", methods=["POST"])
@login_required
def exchange_public_token_route():
    data = request.get_json()
    public_token = data["public_token"]
    response = exchange_public_token(public_token)
    save_item(
        user_id=_current_user_id(),
        item_id=response["item_id"],
        access_token=response["access_token"],
    )
    return jsonify({"status": "ok", "item_id": response["item_id"]})


@app.route("/accounts", methods=["GET"])
@login_required
def accounts_route():
    if not get_access_token(_current_user_id()):
        return jsonify({"error": "No access token found"}), 400
    response = fetch_and_save_accounts(_current_user_id())
    return jsonify(response)


@app.route("/local_accounts", methods=["GET"])
@login_required
def local_accounts_route():
    return jsonify(get_accounts_local(user_id=_current_user_id()))


@app.route("/transactions", methods=["GET"])
@login_required
def transactions_route():
    try:
        response = sync_transactions_for_user(_current_user_id())
        return jsonify(response), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/sandbox_connect", methods=["GET", "POST"])
@login_required
def sandbox_connect():
    access_token = get_access_token(_current_user_id())
    if access_token:
        return jsonify({"status": "sandbox account already connected"})
    access_token = ensure_sandbox_item_connected(_current_user_id())
    return jsonify({
        "status": "sandbox account connected",
        "access_token_saved": bool(access_token),
        "sandbox_profile": "user_transactions_dynamic",
    })


@app.route("/local_transactions", methods=["GET"])
@login_required
def local_transactions_route():
    return jsonify(get_transactions_local(user_id=_current_user_id()))


@app.route("/export_transactions_to_s3", methods=["POST", "GET"])
@login_required
def export_transactions_to_s3_route():
    result = upload_transactions_to_s3(user_id=_current_user_id())
    return jsonify(result), 200 if result["status"] == "ok" else 400


@app.route("/export_accounts_to_s3", methods=["POST", "GET"])
@login_required
def export_accounts_to_s3_route():
    result = upload_accounts_to_s3(user_id=_current_user_id())
    return jsonify(result), 200 if result["status"] == "ok" else 400


@app.route("/simulate_daily_transactions", methods=["POST", "GET"])
@login_required
def simulate_daily_transactions_route():
    try:
        response = create_daily_sandbox_transactions(_current_user_id())
        return jsonify(response), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/run_daily_sandbox_pipeline", methods=["POST", "GET"])
@login_required
def run_daily_sandbox_pipeline_route():
    user_id = _current_user_id()
    try:
        is_sandbox = Config.PLAID_ENV == "sandbox"
        ensure_sandbox_item_connected(user_id) if is_sandbox else None
        fetch_and_save_accounts(user_id)
        simulation_response = create_daily_sandbox_transactions(user_id) if is_sandbox else None
        transactions_response = sync_transactions_for_user(user_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        accounts_export = upload_accounts_to_s3()
    except Exception as exc:
        accounts_export = {"status": "error", "message": str(exc)}

    try:
        transactions_export = upload_transactions_to_s3()
    except Exception as exc:
        transactions_export = {"status": "error", "message": str(exc)}

    return jsonify({
        "status": "ok",
        "message": "Daily sandbox pipeline completed.",
        "simulation": simulation_response,
        "transactions_sync": transactions_response,
        "accounts_export": accounts_export,
        "transactions_export": transactions_export,
    })


@app.route("/api/dashboard/summary", methods=["GET"])
@login_required
def dashboard_summary_route():
    return jsonify({"status": "ok", **get_dashboard_summary(_current_user_id())})


@app.route("/api/dashboard/spend-by-month", methods=["GET"])
@login_required
def dashboard_spend_by_month_route():
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    return jsonify({"status": "ok", **get_spend_by_month(_current_user_id(), include_pending=include_pending, start_date=start_date, end_date=end_date)})


@app.route("/api/dashboard/top-merchants", methods=["GET"])
@login_required
def dashboard_top_merchants_route():
    limit = request.args.get("limit", default=10, type=int) or 10
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    return jsonify({"status": "ok", **get_top_merchants(_current_user_id(), limit=max(1, limit), include_pending=include_pending, start_date=start_date, end_date=end_date)})


@app.route("/api/dashboard/spend-by-day", methods=["GET"])
@login_required
def dashboard_spend_by_day_route():
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    return jsonify({"status": "ok", **get_spend_by_day(_current_user_id(), include_pending=include_pending, start_date=start_date, end_date=end_date)})


@app.route("/api/dashboard/spend-by-merchant", methods=["GET"])
@login_required
def dashboard_spend_by_merchant_route():
    limit = request.args.get("limit", type=int)
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    normalized_limit = max(1, limit) if limit is not None else None
    return jsonify({"status": "ok", **get_spend_by_merchant(_current_user_id(), include_pending=include_pending, limit=normalized_limit, start_date=start_date, end_date=end_date)})


@app.route("/api/dashboard/spend-by-amount", methods=["GET"])
@login_required
def dashboard_spend_by_amount_route():
    bucket_size = request.args.get("bucket_size", default=10, type=int) or 10
    include_pending = request.args.get("include_pending", "").lower() == "true"
    start_date, end_date = _get_dashboard_date_filters()
    return jsonify({"status": "ok", **get_spend_by_amount_bucket(_current_user_id(), include_pending=include_pending, bucket_size=max(1, bucket_size), start_date=start_date, end_date=end_date)})


@app.route("/api/dashboard/recent-transactions", methods=["GET"])
@login_required
def dashboard_recent_transactions_route():
    limit = request.args.get("limit", default=25, type=int) or 25
    return jsonify({"status": "ok", **get_recent_transactions(_current_user_id(), limit=max(1, limit))})


@app.route("/api/dashboard/account-balances", methods=["GET"])
@login_required
def dashboard_account_balances_route():
    return jsonify({"status": "ok", **get_account_balances(_current_user_id())})


@app.route("/profile", methods=["GET"])
@login_required
def profile_page():
    user = get_user_by_id(session["user_id"])
    profile = get_user_profile(session["user_id"])
    return render_template("profile.html", user=user, profile=profile)


@app.route("/profile", methods=["POST"])
@login_required
def profile_save():
    data = {
        "first_name": request.form.get("first_name", "").strip() or None,
        "last_name": request.form.get("last_name", "").strip() or None,
        "monthly_income": _parse_float(request.form.get("monthly_income")),
        "savings_goal_amount": _parse_float(request.form.get("savings_goal_amount")),
        "savings_goal_date": request.form.get("savings_goal_date") or None,
        "debt_payoff_goal": _parse_float(request.form.get("debt_payoff_goal")),
        "preferred_currency": request.form.get("preferred_currency", "USD") or "USD",
    }
    save_user_profile(session["user_id"], data)
    user = get_user_by_id(session["user_id"])
    profile = get_user_profile(session["user_id"])
    return render_template("profile.html", user=user, profile=profile, saved=True)


def _parse_float(value):
    try:
        return float(value) if value else None
    except (ValueError, TypeError):
        return None


@app.route("/debug/plaid_transactions", methods=["GET"])
@login_required
def debug_plaid_transactions():
    items = get_all_items(_current_user_id())
    if not items:
        return jsonify({"error": "no items"}), 400
    response = get_transactions_sync(items[0]["access_token"])
    return jsonify(response)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
