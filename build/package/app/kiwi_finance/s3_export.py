import csv
from datetime import datetime
from io import StringIO

import boto3

from kiwi_finance.config import Config
from kiwi_finance.database import get_accounts_local, get_transactions_local


def _upload_rows_to_s3(
    rows: list[dict],
    *,
    bucket: str,
    prefix: str,
    filename_prefix: str,
    empty_message: str,
):
    if not rows:
        return {
            "status": "no_data",
            "message": empty_message,
        }

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    key = f"{prefix.strip('/')}/{filename_prefix}_{timestamp}.csv"

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )

    return {
        "status": "ok",
        "bucket": bucket,
        "key": key,
        "rows_uploaded": len(rows),
    }


def upload_transactions_to_s3(bucket: str | None = None, prefix: str | None = None):
    return _upload_rows_to_s3(
        get_transactions_local(),
        bucket=bucket or Config.AWS_S3_BUCKET,
        prefix=prefix or Config.AWS_S3_TRANSACTIONS_PREFIX,
        filename_prefix="transactions",
        empty_message="No local transactions found to upload.",
    )


def upload_accounts_to_s3(bucket: str | None = None, prefix: str | None = None):
    return _upload_rows_to_s3(
        get_accounts_local(),
        bucket=bucket or Config.AWS_S3_BUCKET,
        prefix=prefix or Config.AWS_S3_ACCOUNTS_PREFIX,
        filename_prefix="accounts",
        empty_message="No local accounts found to upload.",
    )
