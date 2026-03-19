#!/usr/bin/env python3
"""
Query helper for the personal assistant.

Usage:
  python query.py --sql "SELECT date, title, summary FROM ..."   # BigQuery query → JSON
  python query.py --gcs gs://jesse-personal-assistant/path.md    # Fetch GCS file as text
"""
import argparse
import json
import sys
from pathlib import Path

from google.cloud import bigquery, storage
from google.oauth2 import service_account

CREDS_PATH = Path(__file__).parent / "creds.json"
PROJECT_ID = "eng-reactor-287421"
BUCKET     = "jesse-personal-assistant"


def _creds() -> service_account.Credentials:
    return service_account.Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=[
            "https://www.googleapis.com/auth/bigquery.readonly",
            "https://www.googleapis.com/auth/devstorage.read_only",
        ],
    )


def run_sql(sql: str) -> None:
    bq   = bigquery.Client(project=PROJECT_ID, credentials=_creds())
    rows = list(bq.query(sql).result())
    if not rows:
        print("[]")
        return
    result = [dict(zip(row.keys(), row.values())) for row in rows]
    print(json.dumps(result, indent=2, default=str))


def fetch_gcs(uri: str) -> None:
    gcs = storage.Client(project=PROJECT_ID, credentials=_creds())
    if uri.startswith("gs://"):
        parts  = uri[5:].split("/", 1)
        bucket = parts[0]
        path   = parts[1] if len(parts) > 1 else ""
    else:
        bucket = BUCKET
        path   = uri
    print(gcs.bucket(bucket).blob(path).download_as_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="BigQuery/GCS query helper.")
    parser.add_argument("--sql", help="BigQuery SQL to run; outputs JSON array")
    parser.add_argument("--gcs", help="GCS URI to fetch as text (gs://bucket/path)")
    args = parser.parse_args()

    if args.sql:
        run_sql(args.sql)
    elif args.gcs:
        fetch_gcs(args.gcs)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
