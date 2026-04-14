from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def download_file_if_present(bucket: str, key: str, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    s3 = boto3.client("s3")

    try:
        s3.download_file(bucket, key, str(destination))
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey"}:
            return False
        raise


def upload_file(bucket: str, key: str, source: Path):
    s3 = boto3.client("s3")
    s3.upload_file(str(source), bucket, key)
