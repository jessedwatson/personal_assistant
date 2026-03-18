#!/usr/bin/env python3
"""
Conversation ingestion pipeline.

Sources:
  - Cluely  : platform.cluely.com API (live, uses session token from local app)
  - Granola : api.granola.ai API (live, uses WorkOS token from local app)

BigQuery schema:
  conversations  : ~30-column dimension table, one row per session
  messages       : fact table, one row per utterance

GCS:
  raw transcripts stored as JSON at gs://{BUCKET}/transcripts/{source}/{id}.json

Re-enrichment note:
  BQ streaming buffer blocks UPDATE/DELETE for ~90 minutes after insert.
  We avoid this by using batch load (load_table_from_json with WRITE_TRUNCATE)
  for the full re-enrich pass instead of per-row UPDATEs.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from anthropic import Anthropic
from google.cloud import bigquery, storage
from google.oauth2 import service_account

# ── Config ─────────────────────────────────────────────────────────────────────
CREDS_PATH   = Path(__file__).parent / "creds.json"
PROJECT_ID   = "eng-reactor-287421"
DATASET      = "personal_assistant"
BUCKET       = "jesse-personal-assistant"
CLUELY_SESSION_PATH  = Path.home() / "Library/Application Support/cluely/user.session"
GRANOLA_ACCOUNTS_PATH = Path.home() / "Library/Application Support/Granola/stored-accounts.json"
ANTHROPIC_MODEL      = "claude-sonnet-4-6"

# ── GCP clients ────────────────────────────────────────────────────────────────

def _creds():
    return service_account.Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=[
            "https://www.googleapis.com/auth/bigquery",
            "https://www.googleapis.com/auth/devstorage.read_write",
        ],
    )

def get_bq():  return bigquery.Client(project=PROJECT_ID, credentials=_creds())
def get_gcs(): return storage.Client(project=PROJECT_ID, credentials=_creds())

# ── BigQuery schema ─────────────────────────────────────────────────────────────
# S = STRING convenience alias
S = lambda name, **kw: bigquery.SchemaField(name, "STRING",  **kw)
T = lambda name, **kw: bigquery.SchemaField(name, "TIMESTAMP", **kw)
F = lambda name, **kw: bigquery.SchemaField(name, "FLOAT",   **kw)
I = lambda name, **kw: bigquery.SchemaField(name, "INTEGER", **kw)
B = lambda name, **kw: bigquery.SchemaField(name, "BOOLEAN", **kw)

CONVERSATIONS_SCHEMA = [
    # ── Identity ──────────────────────────────────────────────────────────────
    S("conversation_id",     mode="REQUIRED"),  # stable UUID from source
    T("date"),                                   # start time
    S("source"),             # cluely | claude | zoom | email | slack
    S("title"),              # original title from source
    F("duration_minutes"),   # end - start in minutes

    # ── People & orgs ─────────────────────────────────────────────────────────
    S("participants"),        # people actively in the conversation, comma-sep
    S("people_mentioned"),    # names mentioned but not necessarily speaking
    S("companies"),           # companies / orgs referenced
    S("roles_mentioned"),     # job titles that came up (VP Pricing, CTO, ...)

    # ── Content classification ─────────────────────────────────────────────────
    S("category"),    # interview | strategy | coaching | technical | social | admin
    S("subcategory"), # e.g. "salary negotiation" or "system design"
    S("domain"),      # finance | technology | career | personal | product | legal

    # ── Narrative ──────────────────────────────────────────────────────────────
    S("topic"),       # one-sentence subject line
    S("summary"),     # 2-3 sentence narrative of what happened and what was decided

    # ── Key content extracted ──────────────────────────────────────────────────
    S("action_items"),     # things someone committed to do, semicolon-sep
    S("decisions_made"),   # conclusions reached, semicolon-sep
    S("open_questions"),   # unresolved issues left hanging, semicolon-sep
    S("key_quotes"),       # verbatim standout lines, semicolon-sep

    # ── Strategy & tech ───────────────────────────────────────────────────────
    S("strategies"),           # high-level strategic moves discussed
    S("projects_mentioned"),   # named projects (Warm Fuzzies, pricing ML, ...)
    S("technologies_mentioned"),# tools / languages / platforms (Python, BigQuery, Claude, ...)
    S("products_mentioned"),   # commercial products or services (Wise, Remitly, ...)

    # ── Sentiment & tone ──────────────────────────────────────────────────────
    S("sentiment"),   # positive | neutral | negative | mixed
    S("urgency"),     # low | medium | high
    S("formality"),   # casual | professional | formal

    # ── Hiring context ────────────────────────────────────────────────────────
    B("hiring_related"),   # true if this is about a job
    S("hiring_company"),   # company being discussed for hire
    S("hiring_role"),      # role title
    S("hiring_stage"),     # screening | interview | offer | negotiation | rejected | accepted

    # ── Follow-up & relationships ─────────────────────────────────────────────
    B("follow_up_required"),
    S("follow_up_items"),    # specific next steps, semicolon-sep
    S("relationship_context"), # recruiter | colleague | manager | friend | client | vendor

    # ── Geography & finance ───────────────────────────────────────────────────
    S("locations_mentioned"),   # cities, countries, offices
    S("financial_context"),     # salary figures, deal sizes, cost topics mentioned

    # ── Retrieval pointer ─────────────────────────────────────────────────────
    S("raw_gcs_path"),  # gs://bucket/path/to/raw.json

    # ── Computed at ingest ────────────────────────────────────────────────────
    I("message_count"),  # number of utterances in messages table
    I("word_count"),     # total words across all messages
]

MESSAGES_SCHEMA = [
    S("conversation_id", mode="REQUIRED"),
    T("timestamp"),
    S("role"),      # Jesse | other | system (normalised from mic/system)
    S("content"),   # raw utterance text
    I("sequence"),  # 0-indexed order within conversation
    I("word_count"),# words in this utterance
]


def ensure_dataset_and_tables(bq: bigquery.Client):
    ds_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET}")
    ds_ref.location = "US"
    bq.create_dataset(ds_ref, exists_ok=True)
    for table_id, schema in [("conversations", CONVERSATIONS_SCHEMA), ("messages", MESSAGES_SCHEMA)]:
        ref = bq.dataset(DATASET).table(table_id)
        bq.create_table(bigquery.Table(ref, schema=schema), exists_ok=True)
    print(f"[BQ] Schema ready ({DATASET}.conversations, {DATASET}.messages)")


# ── Claude enrichment ──────────────────────────────────────────────────────────

ENRICHMENT_SCHEMA = """{
  "topic":                "one-sentence subject",
  "summary":              "2-3 sentence narrative of what happened and decisions made",
  "participants":         ["names of people actively speaking or mentioned as present"],
  "people_mentioned":     ["other names referenced but not present"],
  "companies":            ["companies, organisations, institutions"],
  "roles_mentioned":      ["job titles that came up"],
  "category":             "interview | strategy | coaching | technical | social | admin",
  "subcategory":          "finer label e.g. salary negotiation, system design, onboarding",
  "domain":               "finance | technology | career | personal | product | legal",
  "action_items":         ["things someone committed to do"],
  "decisions_made":       ["conclusions or choices that were reached"],
  "open_questions":       ["unresolved issues left for later"],
  "key_quotes":           ["verbatim standout lines worth remembering"],
  "strategies":           ["strategic moves or approaches discussed"],
  "projects_mentioned":   ["named projects or initiatives"],
  "technologies_mentioned": ["tools, languages, platforms"],
  "products_mentioned":   ["commercial products or services"],
  "sentiment":            "positive | neutral | negative | mixed",
  "urgency":              "low | medium | high",
  "formality":            "casual | professional | formal",
  "hiring_related":       true,
  "hiring_company":       "company name or empty string",
  "hiring_role":          "role title or empty string",
  "hiring_stage":         "screening | interview | offer | negotiation | rejected | accepted | empty",
  "follow_up_required":   true,
  "follow_up_items":      ["specific next steps"],
  "relationship_context": "recruiter | colleague | manager | friend | client | vendor | unknown",
  "locations_mentioned":  ["cities, countries, offices"],
  "financial_context":    "salary figures, deal sizes, or budget topics mentioned, or empty"
}"""


def enrich(transcript_text: str, title: str) -> dict:
    client = Anthropic()
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=(
            "You are a conversation analyst. Extract structured metadata from transcripts.\n"
            "The transcript uses [mic] for the local speaker (Jesse Watson) and [system] for other speakers.\n"
            "Extract proper names, companies, and all other fields from the text content itself.\n\n"
            "Return ONLY valid JSON matching this exact schema — no markdown, no explanation:\n"
            + ENRICHMENT_SCHEMA
        ),
        messages=[{"role": "user", "content": f"Title: {title}\n\nTranscript:\n{transcript_text[:14000]}"}],
    )
    raw = resp.content[0].text.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [warn] JSON parse failed, using defaults")
        return {}


def _str(meta: dict, key: str) -> str:
    val = meta.get(key, "")
    if isinstance(val, list):
        return "; ".join(str(v) for v in val)
    return str(val) if val else ""

def _bool(meta: dict, key: str) -> bool:
    return bool(meta.get(key, False))


def build_conv_row(sid: str, session: dict, meta: dict, gcs_path: str,
                   msg_count: int, word_count: int) -> dict:
    started_at = session.get("startedAt")
    ended_at   = session.get("endedAt")
    duration   = None
    if started_at and ended_at:
        s = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        e = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        duration = round((e - s).total_seconds() / 60, 1)

    return {
        "conversation_id":      sid,
        "date":                 started_at,
        "source":               "cluely",
        "title":                session.get("title", ""),
        "duration_minutes":     duration,
        "participants":         _str(meta, "participants"),
        "people_mentioned":     _str(meta, "people_mentioned"),
        "companies":            _str(meta, "companies"),
        "roles_mentioned":      _str(meta, "roles_mentioned"),
        "category":             _str(meta, "category"),
        "subcategory":          _str(meta, "subcategory"),
        "domain":               _str(meta, "domain"),
        "topic":                _str(meta, "topic") or session.get("title", ""),
        "summary":              _str(meta, "summary"),
        "action_items":         _str(meta, "action_items"),
        "decisions_made":       _str(meta, "decisions_made"),
        "open_questions":       _str(meta, "open_questions"),
        "key_quotes":           _str(meta, "key_quotes"),
        "strategies":           _str(meta, "strategies"),
        "projects_mentioned":   _str(meta, "projects_mentioned"),
        "technologies_mentioned": _str(meta, "technologies_mentioned"),
        "products_mentioned":   _str(meta, "products_mentioned"),
        "sentiment":            _str(meta, "sentiment"),
        "urgency":              _str(meta, "urgency"),
        "formality":            _str(meta, "formality"),
        "hiring_related":       _bool(meta, "hiring_related"),
        "hiring_company":       _str(meta, "hiring_company"),
        "hiring_role":          _str(meta, "hiring_role"),
        "hiring_stage":         _str(meta, "hiring_stage"),
        "follow_up_required":   _bool(meta, "follow_up_required"),
        "follow_up_items":      _str(meta, "follow_up_items"),
        "relationship_context": _str(meta, "relationship_context"),
        "locations_mentioned":  _str(meta, "locations_mentioned"),
        "financial_context":    _str(meta, "financial_context"),
        "raw_gcs_path":         gcs_path,
        "message_count":        msg_count,
        "word_count":           word_count,
    }


# ── GCS ────────────────────────────────────────────────────────────────────────

def upload_raw(gcs: storage.Client, data: dict, source: str, sid: str) -> str:
    bucket = gcs.bucket(BUCKET)
    if not bucket.exists():
        bucket = gcs.create_bucket(BUCKET, location="US")
        print(f"[GCS] Created bucket {BUCKET}")
    path = f"transcripts/{source}/{sid}.json"
    bucket.blob(path).upload_from_string(json.dumps(data, indent=2), content_type="application/json")
    gcs_path = f"gs://{BUCKET}/{path}"
    print(f"[GCS] {gcs_path}")
    return gcs_path


# ── BQ batch load (avoids streaming buffer limitations) ────────────────────────

def batch_load(bq: bigquery.Client, table_id: str, rows: list[dict],
               disposition=bigquery.WriteDisposition.WRITE_APPEND):
    if not rows:
        return
    table_ref = f"{PROJECT_ID}.{DATASET}.{table_id}"
    job_config = bigquery.LoadJobConfig(
        schema=CONVERSATIONS_SCHEMA if table_id == "conversations" else MESSAGES_SCHEMA,
        write_disposition=disposition,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    ndjson = "\n".join(json.dumps(r) for r in rows)
    job = bq.load_table_from_json(
        [json.loads(line) for line in ndjson.strip().split("\n")],
        table_ref,
        job_config=job_config,
    )
    job.result()
    if job.errors:
        print(f"[BQ] load errors for {table_id}: {job.errors}")
    else:
        print(f"[BQ] Loaded {len(rows)} rows → {table_id}")


# ── Cluely ingestion ───────────────────────────────────────────────────────────

def normalise_role(raw: str) -> str:
    return "Jesse" if raw == "mic" else ("other" if raw == "system" else raw)


def load_cluely_token() -> str:
    return json.loads(CLUELY_SESSION_PATH.read_text())["accessToken"]


def fetch_sessions(token: str) -> list[dict]:
    r = requests.get(
        "https://platform.cluely.com/v2/sessions",
        params={"page": 1, "size": 50},
        headers={"Authorization": f"Bearer {token}", "Origin": "https://desktop.cluely.com"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_transcript(token: str, sid: str) -> list[dict]:
    r = requests.get(
        f"https://platform.cluely.com/v2/sessions/{sid}/transcript",
        headers={"Authorization": f"Bearer {token}", "Origin": "https://desktop.cluely.com"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def get_ingested_ids(bq: bigquery.Client) -> set:
    try:
        return {r.conversation_id for r in
                bq.query(f"SELECT conversation_id FROM `{PROJECT_ID}.{DATASET}.conversations`").result()}
    except Exception:
        return set()


def ingest_cluely(bq: bigquery.Client, gcs: storage.Client, ingested: set):
    print("\n[Cluely] Starting ingestion...")
    if not CLUELY_SESSION_PATH.exists():
        print("[Cluely] Session file not found, skipping.")
        return
    token    = load_cluely_token()
    sessions = fetch_sessions(token)
    print(f"[Cluely] Found {len(sessions)} sessions, {len(ingested)} already ingested")

    for session in sessions:
        sid   = session["id"]
        title = session.get("title", "")

        if sid in ingested:
            print(f"  skip {title or sid} — already ingested")
            continue
        if not title:
            print(f"  skip {sid} — no title")
            continue

        print(f"\n  Processing: {title}")

        segments = fetch_transcript(token, sid)
        if not segments:
            print("  empty transcript, skipping")
            continue

        transcript_text = "\n".join(
            f"[{s.get('role','')}]: {s.get('text','').strip()}"
            for s in segments if s.get("text", "").strip()
        )

        print("  [Claude] enriching...")
        meta = enrich(transcript_text, title)
        print(f"    topic:        {meta.get('topic','')[:80]}")
        print(f"    participants: {meta.get('participants')}")
        print(f"    companies:    {meta.get('companies')}")
        print(f"    category:     {meta.get('category')} / {meta.get('subcategory')}")
        print(f"    hiring:       {meta.get('hiring_related')} — {meta.get('hiring_company')}")
        print(f"    follow_up:    {meta.get('follow_up_required')}")

        gcs_path = upload_raw(gcs, {"session": session, "transcript": segments}, "cluely", sid)

        # Build message rows
        msg_rows = []
        for i, seg in enumerate(segments):
            text = seg.get("text", "").strip()
            if not text:
                continue
            msg_rows.append({
                "conversation_id": sid,
                "timestamp":       seg.get("createdAt"),
                "role":            normalise_role(seg.get("role", "")),
                "content":         text,
                "sequence":        i,
                "word_count":      len(text.split()),
            })

        total_words = sum(r["word_count"] for r in msg_rows)
        conv_row = build_conv_row(sid, session, meta, gcs_path, len(msg_rows), total_words)

        batch_load(bq, "conversations", [conv_row])
        batch_load(bq, "messages", msg_rows)

    print("\n[Cluely] Done.")


# ── Re-enrich (rebuild conversations table from GCS raw files) ─────────────────

def re_enrich(bq: bigquery.Client, gcs: storage.Client):
    """Re-extract all metadata. Truncates and reloads conversations table."""
    print("\n[Re-enrich] Loading existing conversation IDs...")
    rows = list(bq.query(
        f"SELECT conversation_id, title FROM `{PROJECT_ID}.{DATASET}.conversations`"
    ).result())
    print(f"[Re-enrich] {len(rows)} conversations to re-enrich")

    bucket = gcs.bucket(BUCKET)
    new_conv_rows = []

    for row in rows:
        sid   = row.conversation_id
        title = row.title or ""
        print(f"\n  Re-enriching: {title or sid}")

        blob = bucket.blob(f"transcripts/cluely/{sid}.json")
        raw  = json.loads(blob.download_as_text())
        session   = raw.get("session", {})
        segments  = raw.get("transcript", [])

        transcript_text = "\n".join(
            f"[{s.get('role','')}]: {s.get('text','').strip()}"
            for s in segments if s.get("text","").strip()
        )

        meta = enrich(transcript_text, title)
        print(f"    participants: {meta.get('participants')}")
        print(f"    companies:    {meta.get('companies')}")

        msg_count   = sum(1 for s in segments if s.get("text","").strip())
        word_count  = sum(len(s.get("text","").split()) for s in segments if s.get("text","").strip())
        gcs_path    = f"gs://{BUCKET}/transcripts/cluely/{sid}.json"

        new_conv_rows.append(build_conv_row(sid, session, meta, gcs_path, msg_count, word_count))

    # Truncate and reload conversations table (avoids streaming buffer issue)
    print(f"\n[Re-enrich] Truncating conversations table and reloading {len(new_conv_rows)} rows...")
    batch_load(bq, "conversations", new_conv_rows, bigquery.WriteDisposition.WRITE_TRUNCATE)
    print("[Re-enrich] Done.")


# ── Granola ingestion ──────────────────────────────────────────────────────────

def load_granola_token() -> str:
    data = json.loads(GRANOLA_ACCOUNTS_PATH.read_text())
    account = json.loads(data["accounts"])[0]
    return json.loads(account["tokens"])["access_token"]


def granola_post(token: str, endpoint: str, payload: dict) -> any:
    r = requests.post(
        f"https://api.granola.ai/v1/{endpoint}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_granola_documents(token: str) -> list[dict]:
    """Return all documents (owned + shared) using document-set + batch fetch."""
    doc_set = granola_post(token, "get-document-set", {})
    all_ids = list(doc_set["documents"].keys())
    if not all_ids:
        return []
    data = granola_post(token, "get-documents-batch", {"document_ids": all_ids})
    return [d for d in data.get("docs", []) if isinstance(d, dict)]


def fetch_granola_transcript(token: str, doc_id: str) -> list[dict]:
    result = granola_post(token, "get-document-transcript", {"document_id": doc_id})
    if isinstance(result, list):
        return result
    return []


def ingest_granola(bq: bigquery.Client, gcs: storage.Client, ingested: set):
    print("\n[Granola] Starting ingestion...")
    token = load_granola_token()
    docs  = fetch_granola_documents(token)
    print(f"[Granola] Found {len(docs)} documents, {len(ingested)} already ingested")

    for doc in docs:
        did   = doc["id"]
        title = doc.get("title") or ""

        if did in ingested:
            print(f"  skip {title or did} — already ingested")
            continue

        # Pull calendar event title as fallback
        if not title:
            cal = doc.get("google_calendar_event") or {}
            title = cal.get("summary", "") if isinstance(cal, dict) else ""
        if not title:
            print(f"  skip {did} — no title")
            continue

        print(f"\n  Processing: {title}")

        segments = fetch_granola_transcript(token, did)
        if not segments:
            print("  empty transcript, skipping")
            continue

        # Granola uses source="microphone" for Jesse, "system" for others
        transcript_text = "\n".join(
            f"[{'mic' if s.get('source') == 'microphone' else 'system'}]: {s.get('text','').strip()}"
            for s in segments if s.get("text", "").strip()
        )

        print("  [Claude] enriching...")
        meta = enrich(transcript_text, title)
        print(f"    topic:        {meta.get('topic','')[:80]}")
        print(f"    participants: {meta.get('participants')}")
        print(f"    companies:    {meta.get('companies')}")
        print(f"    category:     {meta.get('category')} / {meta.get('subcategory')}")
        print(f"    hiring:       {meta.get('hiring_related')} — {meta.get('hiring_company')}")
        print(f"    follow_up:    {meta.get('follow_up_required')}")

        gcs_path = upload_raw(gcs, {"document": doc, "transcript": segments}, "granola", did)

        # Duration from first/last segment timestamps
        started_at = doc.get("created_at")
        ended_at   = doc.get("updated_at")
        if segments:
            started_at = segments[0].get("start_timestamp") or started_at
            ended_at   = segments[-1].get("end_timestamp") or ended_at

        duration = None
        if started_at and ended_at:
            try:
                s = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                e = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                duration = round((e - s).total_seconds() / 60, 1)
            except ValueError:
                pass

        msg_rows = []
        for i, seg in enumerate(segments):
            text = seg.get("text", "").strip()
            if not text:
                continue
            role = "Jesse" if seg.get("source") == "microphone" else "other"
            msg_rows.append({
                "conversation_id": did,
                "timestamp":       seg.get("start_timestamp"),
                "role":            role,
                "content":         text,
                "sequence":        i,
                "word_count":      len(text.split()),
            })

        total_words = sum(r["word_count"] for r in msg_rows)

        # Reuse build_conv_row via a compatible session dict
        session = {"startedAt": started_at, "endedAt": ended_at, "title": title}
        conv_row = build_conv_row(did, session, meta, gcs_path, len(msg_rows), total_words)
        conv_row["source"] = "granola"
        conv_row["duration_minutes"] = duration

        batch_load(bq, "conversations", [conv_row])
        batch_load(bq, "messages", msg_rows)

    print("\n[Granola] Done.")


# ── Entry point ────────────────────────────────────────────────────────────────

# ── Claude report ingestion ────────────────────────────────────────────────────

def ingest_claude_report(bq: bigquery.Client, gcs: storage.Client,
                         path: str, ingested: set):
    """
    Ingest a Claude-generated report (markdown or text file) into BQ + GCS.
    conversation_id  = sha1 of the file path (stable across runs)
    messages         = one row per ## section (or full text if no sections)
    source           = "claude"
    """
    import hashlib

    fpath = Path(path).expanduser().resolve()
    if not fpath.exists():
        print(f"[Claude report] File not found: {fpath}")
        return

    cid = "claude-" + hashlib.sha1(str(fpath).encode()).hexdigest()[:16]
    if cid in ingested:
        print(f"[Claude report] Already ingested: {fpath.name}")
        return

    print(f"\n[Claude report] Ingesting: {fpath.name}")
    raw_text = fpath.read_text()

    # Split into sections on ## headers; fall back to whole file as one section
    import re
    sections = re.split(r'\n(?=## )', raw_text)
    if len(sections) <= 1:
        sections = [raw_text]

    # Build full text for enrichment (skip pipeline log lines at top)
    enrichment_text = "\n\n".join(
        s for s in sections
        if not s.strip().startswith("[Planner]")
        and not s.strip().startswith("[Research]")
        and not s.strip().startswith("[Context]")
        and not s.strip().startswith("[Analyst]")
        and not s.strip().startswith("===")
        and not s.strip().startswith("Request:")
    )

    print("  [Claude] enriching...")
    meta = enrich(enrichment_text, fpath.stem.replace("_", " ").title())
    print(f"    topic:     {meta.get('topic','')[:80]}")
    print(f"    companies: {meta.get('companies')}")

    # File mtime as the date
    mtime = datetime.fromtimestamp(fpath.stat().st_mtime).isoformat() + "Z"

    # Upload raw file to GCS
    bucket = gcs.bucket(BUCKET)
    if not bucket.exists():
        bucket = gcs.create_bucket(BUCKET, location="US")
    blob_name = f"transcripts/claude/{fpath.stem}.md"
    bucket.blob(blob_name).upload_from_string(raw_text, content_type="text/markdown")
    gcs_path = f"gs://{BUCKET}/{blob_name}"
    print(f"  [GCS] {gcs_path}")

    # messages: one per section, role = "assistant"
    msg_rows = []
    for i, section in enumerate(sections):
        text = section.strip()
        if not text:
            continue
        msg_rows.append({
            "conversation_id": cid,
            "timestamp":       mtime,
            "role":            "assistant",
            "content":         text,
            "sequence":        i,
            "word_count":      len(text.split()),
        })

    total_words = sum(r["word_count"] for r in msg_rows)

    # Fake session dict for build_conv_row
    session = {"startedAt": mtime, "endedAt": mtime, "title": fpath.stem.replace("_", " ").title()}
    conv_row = build_conv_row(cid, session, meta, gcs_path, len(msg_rows), total_words)
    conv_row["source"] = "claude"
    conv_row["duration_minutes"] = None

    batch_load(bq, "conversations", [conv_row])
    batch_load(bq, "messages", msg_rows)
    print(f"  Done — {len(msg_rows)} sections, {total_words} words")


def run():
    print("=" * 60)
    print("PERSONAL ASSISTANT — CONVERSATION INGESTION PIPELINE")
    print("=" * 60)

    bq  = get_bq()
    gcs = get_gcs()
    ensure_dataset_and_tables(bq)

    if "--re-enrich" in sys.argv:
        re_enrich(bq, gcs)
        return

    ingested = get_ingested_ids(bq)
    print(f"[BQ] Already ingested: {len(ingested)} conversations")

    # Cluely
    ingest_cluely(bq, gcs, ingested)

    # Granola
    ingest_granola(bq, gcs, ingested)

    # Claude reports: --report path/to/file.md
    if "--report" in sys.argv:
        idx = sys.argv.index("--report")
        report_path = sys.argv[idx + 1]
        ingest_claude_report(bq, gcs, report_path, ingested)

    print("\n" + "=" * 60)
    print("Sample query:")
    print(f"  SELECT date, source, topic, companies")
    print(f"  FROM `{PROJECT_ID}.{DATASET}.conversations`")
    print(f"  ORDER BY date DESC")
    print("=" * 60)


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise EnvironmentError("Set ANTHROPIC_API_KEY before running.")
    run()
