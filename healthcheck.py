#!/usr/bin/env python3
"""
Health check for personal assistant infrastructure.
Verifies GCP credentials, BigQuery, GCS, and API tokens are all reachable.
Exits 0 on full pass, 1 if any check fails.
"""
import json
import sys
from pathlib import Path

CREDS_PATH  = Path(__file__).parent / "creds.json"
PROJECT_ID  = "eng-reactor-287421"
DATASET     = "personal_assistant"
BUCKET      = "jesse-personal-assistant"
CLUELY_SESSION_PATH   = Path.home() / "Library/Application Support/cluely/user.session"
GRANOLA_ACCOUNTS_PATH = Path.home() / "Library/Application Support/Granola/stored-accounts.json"

passed = []
failed = []


def ok(label: str) -> None:
    passed.append(label)
    print(f"  ✓  {label}")


def fail(label: str, reason: str) -> None:
    failed.append(label)
    print(f"  ✗  {label}: {reason}")


# ── 1. creds.json exists ───────────────────────────────────────────────────────
if CREDS_PATH.exists():
    ok("creds.json present")
else:
    fail("creds.json", "file not found")

# ── 2. BigQuery reachable ──────────────────────────────────────────────────────
try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    bq  = bigquery.Client(project=PROJECT_ID, credentials=creds)
    cnt = next(iter(bq.query(
        f"SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET}.conversations`"
    ).result()))[0]
    ok(f"BigQuery reachable ({cnt} conversations)")
except Exception as e:
    fail("BigQuery", str(e))

# ── 3. GCS bucket reachable ────────────────────────────────────────────────────
try:
    from google.cloud import storage
    creds_gcs = service_account.Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=["https://www.googleapis.com/auth/devstorage.read_only"],
    )
    gcs    = storage.Client(project=PROJECT_ID, credentials=creds_gcs)
    bucket = gcs.bucket(BUCKET)
    blobs  = list(bucket.list_blobs(max_results=1))
    ok(f"GCS bucket reachable (gs://{BUCKET})")
except Exception as e:
    fail("GCS", str(e))

# ── 4. Granola token loadable ──────────────────────────────────────────────────
try:
    data    = json.loads(GRANOLA_ACCOUNTS_PATH.read_text())
    account = json.loads(data["accounts"])[0]
    token   = json.loads(account["tokens"])["access_token"]
    if token:
        ok("Granola token loadable")
    else:
        fail("Granola token", "empty token")
except Exception as e:
    fail("Granola token", str(e))

# ── 5. Cluely token loadable (optional — skip if not installed) ───────────────
if not CLUELY_SESSION_PATH.exists():
    print(f"  -  Cluely token: session file not found (skipped)")
else:
    try:
        token = json.loads(CLUELY_SESSION_PATH.read_text())["accessToken"]
        if token:
            ok("Cluely token loadable")
        else:
            fail("Cluely token", "empty token")
    except Exception as e:
        fail("Cluely token", str(e))

# ── Summary ────────────────────────────────────────────────────────────────────
print()
if failed:
    print(f"FAILED ({len(failed)}/{len(passed)+len(failed)}): {', '.join(failed)}")
    sys.exit(1)
else:
    print(f"All {len(passed)} checks passed.")
