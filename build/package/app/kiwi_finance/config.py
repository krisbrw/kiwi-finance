import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    APP_NAME = "Kiwi Finance"
    KIWI_USER_ID = os.getenv("KIWI_USER_ID", "local-dev-user")
    DATABASE_PATH = os.getenv("DATABASE_PATH")

    PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
    PLAID_SECRET = os.getenv("PLAID_SECRET")
    PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgresql://user:pass@host:5432/dbname
    DATABASE_URL_SECRET_ARN = os.getenv("DATABASE_URL_SECRET_ARN")
    AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "kiwi-finance-data-krisbro-314171434946")
    AWS_S3_TRANSACTIONS_PREFIX = os.getenv(
        "AWS_S3_TRANSACTIONS_PREFIX",
        "transactions",
    )
    AWS_S3_ACCOUNTS_PREFIX = os.getenv(
        "AWS_S3_ACCOUNTS_PREFIX",
        "accounts",
    )
    AWS_STATE_BUCKET = os.getenv("AWS_STATE_BUCKET", AWS_S3_BUCKET)
    AWS_STATE_KEY = os.getenv("AWS_STATE_KEY", "state/kiwi_finance.db")

    # For local testing only
    PLAID_PRODUCTS = os.getenv("PLAID_PRODUCTS", "transactions")
    PLAID_COUNTRY_CODES = os.getenv("PLAID_COUNTRY_CODES", "US")

    if not PLAID_CLIENT_ID or not PLAID_SECRET:
        raise ValueError("Missing Plaid credentials in .env")
