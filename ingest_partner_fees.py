"""One-off script to ingest Partner Fee Structure spreadsheet into BigQuery."""
import argparse
import datetime
import os
import openpyxl
from pathlib import Path
from google.cloud import bigquery

os.environ.setdefault(
    "GOOGLE_APPLICATION_CREDENTIALS",
    str(Path(__file__).parent / "creds.json"),
)

client = bigquery.Client()
project = "eng-reactor-287421"
dataset = "personal_assistant"
table_id = f"{project}.{dataset}.partner_fees"

schema = [
    bigquery.SchemaField("effective_from", "DATE"),
    bigquery.SchemaField("effective_to", "DATE"),
    bigquery.SchemaField("partner", "STRING"),
    bigquery.SchemaField("partner_channel", "STRING"),
    bigquery.SchemaField("destination", "STRING"),
    bigquery.SchemaField("receive_country_code", "STRING"),
    bigquery.SchemaField("currency_symbol", "STRING"),
    bigquery.SchemaField("cost_currency", "STRING"),
    bigquery.SchemaField("fee_type", "STRING"),
    bigquery.SchemaField("group_by", "STRING"),
    bigquery.SchemaField("tier_start", "FLOAT64"),
    bigquery.SchemaField("tier_end", "FLOAT64"),
    bigquery.SchemaField("per_transaction_fee", "FLOAT64"),
    bigquery.SchemaField("percent_amount_rate", "FLOAT64"),
    bigquery.SchemaField("send_limit_per_txn", "FLOAT64"),
    bigquery.SchemaField("send_limit_fee_multiplier", "FLOAT64"),
    bigquery.SchemaField("tax_rate", "FLOAT64"),
    bigquery.SchemaField("partner_fee_id", "FLOAT64"),
]


def to_date(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date().isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    return None


def to_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Partner Fee Structure spreadsheet into BigQuery."
    )
    parser.add_argument("xlsx_path", help="Path to the Partner Fee Structure .xlsx file")
    args = parser.parse_args()

    wb        = openpyxl.load_workbook(args.xlsx_path, data_only=True)
    ws        = wb["data"]
    rows      = list(ws.iter_rows(values_only=True))
    data_rows = rows[1:]

    records = []
    for r in data_rows:
        if all(v is None for v in r[:18]):
            continue
        records.append({
            "effective_from":           to_date(r[0]),
            "effective_to":             to_date(r[1]),
            "partner":                  str(r[2]).strip() if r[2] else None,
            "partner_channel":          str(r[3]).strip() if r[3] else None,
            "destination":              str(r[4]).strip() if r[4] else None,
            "receive_country_code":     str(r[5]).strip() if r[5] else None,
            "currency_symbol":          str(r[6]).strip() if r[6] else None,
            "cost_currency":            str(r[7]).strip() if r[7] else None,
            "fee_type":                 str(r[8]).strip() if r[8] else None,
            "group_by":                 str(r[9]).strip() if r[9] else None,
            "tier_start":               to_float(r[10]),
            "tier_end":                 to_float(r[11]),
            "per_transaction_fee":      to_float(r[12]),
            "percent_amount_rate":      to_float(r[13]),
            "send_limit_per_txn":       to_float(r[14]),
            "send_limit_fee_multiplier": to_float(r[15]),
            "tax_rate":                 to_float(r[16]),
            "partner_fee_id":           to_float(r[17]),
        })

    print(f"Records to load: {len(records)}")

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition="WRITE_TRUNCATE",
    )

    job = client.load_table_from_json(records, table_id, job_config=job_config)
    job.result()
    print(f"Loaded {job.output_rows} rows into {table_id}")


if __name__ == "__main__":
    main()
