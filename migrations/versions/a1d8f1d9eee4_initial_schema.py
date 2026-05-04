"""initial_schema

Revision ID: a1d8f1d9eee4
Revises:
Create Date: 2026-04-16

Full initial schema for Kiwi Finance.
Supports both PostgreSQL (production) and SQLite (local dev).
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1d8f1d9eee4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pg = op.get_bind().dialect.name == "postgresql"
    now_fn = sa.text("NOW()") if pg else sa.text("datetime('now')")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False, server_default=now_fn),
    )

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("first_name", sa.Text),
        sa.Column("last_name", sa.Text),
        sa.Column("monthly_income", sa.Float),
        sa.Column("savings_goal_amount", sa.Float),
        sa.Column("savings_goal_date", sa.Text),
        sa.Column("debt_payoff_goal", sa.Float),
        sa.Column("preferred_currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("profile_photo_url", sa.Text),
        sa.Column("updated_at", sa.Text, nullable=False, server_default=now_fn),
    )

    op.create_table(
        "plaid_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("item_id", sa.Text, nullable=False, unique=True),
        sa.Column("access_token", sa.Text, nullable=False),
    )

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("plaid_account_id", sa.Text, nullable=False, unique=True),
        sa.Column("item_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("official_name", sa.Text),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("subtype", sa.Text),
        sa.Column("mask", sa.Text),
        sa.Column("current_balance", sa.Float),
        sa.Column("available_balance", sa.Float),
        sa.Column("iso_currency_code", sa.Text),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("plaid_transaction_id", sa.Text, nullable=False, unique=True),
        sa.Column("plaid_account_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("merchant_name", sa.Text),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("date", sa.Text, nullable=False),
        sa.Column("pending", sa.Integer, nullable=False),
        sa.Column("iso_currency_code", sa.Text),
        sa.Column("unofficial_currency_code", sa.Text),
    )

    op.create_table(
        "sync_state",
        sa.Column("item_id", sa.Text, primary_key=True),
        sa.Column("transactions_cursor", sa.Text),
    )

    # Indexes for common query patterns
    op.create_index("ix_transactions_account", "transactions", ["plaid_account_id"])
    op.create_index("ix_transactions_date", "transactions", ["date"])
    op.create_index("ix_accounts_item", "accounts", ["item_id"])
    op.create_index("ix_plaid_items_user", "plaid_items", ["user_id"])


def downgrade():
    op.drop_index("ix_plaid_items_user", "plaid_items")
    op.drop_index("ix_accounts_item", "accounts")
    op.drop_index("ix_transactions_date", "transactions")
    op.drop_index("ix_transactions_account", "transactions")
    op.drop_table("sync_state")
    op.drop_table("transactions")
    op.drop_table("accounts")
    op.drop_table("plaid_items")
    op.drop_table("user_profiles")
    op.drop_table("users")
