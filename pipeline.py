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
import argparse
import hashlib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from anthropic import Anthropic
from google.cloud import bigquery, storage
from google.oauth2 import service_account

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
CREDS_PATH   = Path(__file__).parent / "creds.json"
PROJECT_ID   = "eng-reactor-287421"
DATASET      = "personal_assistant"
BUCKET       = "jesse-personal-assistant"
CLUELY_SESSION_PATH   = Path.home() / "Library/Application Support/cluely/user.session"
GRANOLA_ACCOUNTS_PATH = Path.home() / "Library/Application Support/Granola/stored-accounts.json"
GDOCS_CLIENT_FILE     = Path(__file__).parent / "google_oauth_client.json"
GDOCS_TOKEN_FILE      = Path(__file__).parent / "google_token.json"
DOCS_FOLDER           = Path(__file__).parent / "docs"
ANTHROPIC_MODEL       = "claude-sonnet-4-6"

# ── GCP clients ────────────────────────────────────────────────────────────────

def _creds() -> service_account.Credentials:
    return service_account.Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=[
            "https://www.googleapis.com/auth/bigquery",
            "https://www.googleapis.com/auth/devstorage.read_write",
        ],
    )

def get_bq() -> bigquery.Client:  return bigquery.Client(project=PROJECT_ID, credentials=_creds())
def get_gcs() -> storage.Client: return storage.Client(project=PROJECT_ID, credentials=_creds())

# ── BigQuery schema ─────────────────────────────────────────────────────────────

def _sf_string(name: str, **kw) -> bigquery.SchemaField:
    return bigquery.SchemaField(name, "STRING", **kw)

def _sf_timestamp(name: str, **kw) -> bigquery.SchemaField:
    return bigquery.SchemaField(name, "TIMESTAMP", **kw)

def _sf_float(name: str, **kw) -> bigquery.SchemaField:
    return bigquery.SchemaField(name, "FLOAT", **kw)

def _sf_integer(name: str, **kw) -> bigquery.SchemaField:
    return bigquery.SchemaField(name, "INTEGER", **kw)

def _sf_boolean(name: str, **kw) -> bigquery.SchemaField:
    return bigquery.SchemaField(name, "BOOLEAN", **kw)

CONVERSATIONS_SCHEMA = [
    # ── Identity ──────────────────────────────────────────────────────────────
    _sf_string("conversation_id",     mode="REQUIRED"),  # stable UUID from source
    _sf_timestamp("date"),                                # start time
    _sf_string("source"),             # cluely | claude | zoom | email | slack
    _sf_string("title"),              # original title from source
    _sf_float("duration_minutes"),    # end - start in minutes

    # ── People & orgs ─────────────────────────────────────────────────────────
    _sf_string("participants"),        # people actively in the conversation, comma-sep
    _sf_string("people_mentioned"),    # names mentioned but not necessarily speaking
    _sf_string("companies"),           # companies / orgs referenced
    _sf_string("roles_mentioned"),     # job titles that came up (VP Pricing, CTO, ...)

    # ── Content classification ─────────────────────────────────────────────────
    _sf_string("category"),    # interview | strategy | coaching | technical | social | admin
    _sf_string("subcategory"), # e.g. "salary negotiation" or "system design"
    _sf_string("domain"),      # finance | technology | career | personal | product | legal

    # ── Narrative ──────────────────────────────────────────────────────────────
    _sf_string("topic"),       # one-sentence subject line
    _sf_string("summary"),     # 2-3 sentence narrative of what happened and what was decided

    # ── Key content extracted ──────────────────────────────────────────────────
    _sf_string("action_items"),     # things someone committed to do, semicolon-sep
    _sf_string("decisions_made"),   # conclusions reached, semicolon-sep
    _sf_string("open_questions"),   # unresolved issues left hanging, semicolon-sep
    _sf_string("key_quotes"),       # verbatim standout lines, semicolon-sep

    # ── Strategy & tech ───────────────────────────────────────────────────────
    _sf_string("strategies"),             # high-level strategic moves discussed
    _sf_string("projects_mentioned"),     # named projects (Warm Fuzzies, pricing ML, ...)
    _sf_string("technologies_mentioned"), # tools / languages / platforms (Python, BigQuery, Claude, ...)
    _sf_string("products_mentioned"),     # commercial products or services (Wise, Remitly, ...)

    # ── Sentiment & tone ──────────────────────────────────────────────────────
    _sf_string("sentiment"),   # positive | neutral | negative | mixed
    _sf_string("urgency"),     # low | medium | high
    _sf_string("formality"),   # casual | professional | formal

    # ── Hiring context ────────────────────────────────────────────────────────
    _sf_boolean("hiring_related"),   # true if this is about a job
    _sf_string("hiring_company"),    # company being discussed for hire
    _sf_string("hiring_role"),       # role title
    _sf_string("hiring_stage"),      # screening | interview | offer | negotiation | rejected | accepted

    # ── Follow-up & relationships ─────────────────────────────────────────────
    _sf_boolean("follow_up_required"),
    _sf_string("follow_up_items"),      # specific next steps, semicolon-sep
    _sf_string("relationship_context"), # recruiter | colleague | manager | friend | client | vendor

    # ── Geography & finance ───────────────────────────────────────────────────
    _sf_string("locations_mentioned"),  # cities, countries, offices
    _sf_string("financial_context"),    # salary figures, deal sizes, cost topics mentioned

    # ── Retrieval pointer ─────────────────────────────────────────────────────
    _sf_string("raw_gcs_path"),  # gs://bucket/path/to/raw.json

    # ── Computed at ingest ────────────────────────────────────────────────────
    _sf_integer("message_count"),  # number of utterances in messages table
    _sf_integer("word_count"),     # total words across all messages
]

MESSAGES_SCHEMA = [
    _sf_string("conversation_id", mode="REQUIRED"),
    _sf_timestamp("timestamp"),
    _sf_string("role"),       # Jesse | other | system (normalised from mic/system)
    _sf_string("content"),    # raw utterance text
    _sf_integer("sequence"),  # 0-indexed order within conversation
    _sf_integer("word_count"),# words in this utterance
]


@dataclass
class MessageRow:
    conversation_id: str
    timestamp: str | None
    role: str
    content: str
    sequence: int
    word_count: int


@dataclass
class ConversationRow:
    conversation_id: str
    date: str | None
    source: str
    title: str
    duration_minutes: float | None
    participants: str
    people_mentioned: str
    companies: str
    roles_mentioned: str
    category: str
    subcategory: str
    domain: str
    topic: str
    summary: str
    action_items: str
    decisions_made: str
    open_questions: str
    key_quotes: str
    strategies: str
    projects_mentioned: str
    technologies_mentioned: str
    products_mentioned: str
    sentiment: str
    urgency: str
    formality: str
    hiring_related: bool
    hiring_company: str
    hiring_role: str
    hiring_stage: str
    follow_up_required: bool
    follow_up_items: str
    relationship_context: str
    locations_mentioned: str
    financial_context: str
    raw_gcs_path: str
    message_count: int
    word_count: int


def ensure_dataset_and_tables(bq: bigquery.Client) -> None:
    ds_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET}")
    ds_ref.location = "US"
    bq.create_dataset(ds_ref, exists_ok=True)
    for table_id, schema in [("conversations", CONVERSATIONS_SCHEMA), ("messages", MESSAGES_SCHEMA)]:
        ref = bq.dataset(DATASET).table(table_id)
        bq.create_table(bigquery.Table(ref, schema=schema), exists_ok=True)
    log.info("[BQ] Schema ready (%s.conversations, %s.messages)", DATASET, DATASET)


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


def _load_org_context() -> str:
    org_path = Path(__file__).parent / "org_context.md"
    if org_path.exists():
        return "\n\n" + org_path.read_text()
    return ""


def enrich(transcript_text: str, title: str) -> dict:
    client = Anthropic()
    org_context = _load_org_context()
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        system=(
            "You are a conversation analyst. Extract structured metadata from transcripts.\n"
            "The transcript uses [mic] for the local speaker (Jesse Watson) and [system] for other speakers.\n"
            "Normalize all people's names to their canonical full names using the org chart below as the ground truth.\n"
            "For example: 'Gustav' → 'Gustaf Bellstam', 'Sharwaree' → 'Smita Mahapatra', 'Thomasw' → 'Thomas Watkins'.\n"
            "If a name cannot be matched to the org chart, use the name as heard but clean up obvious transcription errors.\n\n"
            "Return ONLY valid JSON matching this exact schema — no markdown, no explanation:\n"
            + ENRICHMENT_SCHEMA
            + org_context
        ),
        messages=[{"role": "user", "content": f"Title: {title}\n\nTranscript:\n{transcript_text[:28000]}"}],
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
        log.warning("JSON parse failed, using defaults")
        return {}


def _str(meta: dict, key: str) -> str:
    val = meta.get(key, "")
    if isinstance(val, list):
        return "; ".join(str(v) for v in val)
    return str(val) if val else ""

def _bool(meta: dict, key: str) -> bool:
    return bool(meta.get(key, False))


def build_conv_row(sid: str, session: dict, meta: dict, gcs_path: str,
                   msg_count: int, word_count: int) -> ConversationRow:
    started_at = session.get("startedAt")
    ended_at   = session.get("endedAt")
    duration   = None
    if started_at and ended_at:
        s = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        e = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        duration = round((e - s).total_seconds() / 60, 1)

    return ConversationRow(
        conversation_id=sid,
        date=started_at,
        source="cluely",
        title=session.get("title", ""),
        duration_minutes=duration,
        participants=_str(meta, "participants"),
        people_mentioned=_str(meta, "people_mentioned"),
        companies=_str(meta, "companies"),
        roles_mentioned=_str(meta, "roles_mentioned"),
        category=_str(meta, "category"),
        subcategory=_str(meta, "subcategory"),
        domain=_str(meta, "domain"),
        topic=_str(meta, "topic") or session.get("title", ""),
        summary=_str(meta, "summary"),
        action_items=_str(meta, "action_items"),
        decisions_made=_str(meta, "decisions_made"),
        open_questions=_str(meta, "open_questions"),
        key_quotes=_str(meta, "key_quotes"),
        strategies=_str(meta, "strategies"),
        projects_mentioned=_str(meta, "projects_mentioned"),
        technologies_mentioned=_str(meta, "technologies_mentioned"),
        products_mentioned=_str(meta, "products_mentioned"),
        sentiment=_str(meta, "sentiment"),
        urgency=_str(meta, "urgency"),
        formality=_str(meta, "formality"),
        hiring_related=_bool(meta, "hiring_related"),
        hiring_company=_str(meta, "hiring_company"),
        hiring_role=_str(meta, "hiring_role"),
        hiring_stage=_str(meta, "hiring_stage"),
        follow_up_required=_bool(meta, "follow_up_required"),
        follow_up_items=_str(meta, "follow_up_items"),
        relationship_context=_str(meta, "relationship_context"),
        locations_mentioned=_str(meta, "locations_mentioned"),
        financial_context=_str(meta, "financial_context"),
        raw_gcs_path=gcs_path,
        message_count=msg_count,
        word_count=word_count,
    )


# ── GCS ────────────────────────────────────────────────────────────────────────

def upload_raw(gcs: storage.Client, data: dict, source: str, sid: str) -> str:
    bucket = gcs.bucket(BUCKET)
    if not bucket.exists():
        bucket = gcs.create_bucket(BUCKET, location="US")
        log.info("[GCS] Created bucket %s", BUCKET)
    path = f"transcripts/{source}/{sid}.json"
    bucket.blob(path).upload_from_string(json.dumps(data, indent=2), content_type="application/json")
    gcs_path = f"gs://{BUCKET}/{path}"
    log.info("[GCS] %s", gcs_path)
    return gcs_path


# ── BQ batch load (avoids streaming buffer limitations) ────────────────────────

def batch_load(bq: bigquery.Client, table_id: str, rows: list[Any],
               disposition: bigquery.WriteDisposition = bigquery.WriteDisposition.WRITE_APPEND) -> None:
    if not rows:
        return
    rows = [asdict(r) if hasattr(r, "__dataclass_fields__") else r for r in rows]
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
        log.error("[BQ] load errors for %s: %s", table_id, job.errors)
    else:
        log.info("[BQ] Loaded %d rows → %s", len(rows), table_id)


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


def get_ingested_ids(bq: bigquery.Client) -> set[str]:
    try:
        return {r.conversation_id for r in
                bq.query(f"SELECT conversation_id FROM `{PROJECT_ID}.{DATASET}.conversations`").result()}
    except Exception:
        return set()


def ingest_cluely(bq: bigquery.Client, gcs: storage.Client, ingested: set[str]) -> None:
    log.info("[Cluely] Starting ingestion...")
    if not CLUELY_SESSION_PATH.exists():
        log.warning("[Cluely] Session file not found, skipping.")
        return
    token    = load_cluely_token()
    sessions = fetch_sessions(token)
    log.info("[Cluely] Found %d sessions, %d already ingested", len(sessions), len(ingested))

    for session in sessions:
        sid   = session["id"]
        title = session.get("title", "")

        if sid in ingested:
            log.debug("  skip %s — already ingested", title or sid)
            continue
        if not title:
            log.debug("  skip %s — no title", sid)
            continue

        log.info("  Processing: %s", title)

        segments = fetch_transcript(token, sid)
        if not segments:
            log.debug("  empty transcript, skipping")
            continue

        transcript_text = "\n".join(
            f"[{s.get('role','')}]: {s.get('text','').strip()}"
            for s in segments if s.get("text", "").strip()
        )

        log.debug("  [Claude] enriching...")
        meta = enrich(transcript_text, title)
        log.debug("    topic:        %s", meta.get("topic", "")[:80])
        log.debug("    participants: %s", meta.get("participants"))
        log.debug("    companies:    %s", meta.get("companies"))
        log.debug("    category:     %s / %s", meta.get("category"), meta.get("subcategory"))
        log.debug("    hiring:       %s — %s", meta.get("hiring_related"), meta.get("hiring_company"))
        log.debug("    follow_up:    %s", meta.get("follow_up_required"))

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

    log.info("[Cluely] Done.")


# ── Re-enrich (rebuild conversations table from GCS raw files) ─────────────────

def re_enrich(bq: bigquery.Client, gcs: storage.Client) -> None:
    """Re-extract all metadata. Truncates and reloads conversations table."""
    log.info("[Re-enrich] Loading existing conversation IDs...")
    rows = list(bq.query(
        f"SELECT conversation_id, title, source, raw_gcs_path FROM `{PROJECT_ID}.{DATASET}.conversations`"
    ).result())
    log.info("[Re-enrich] %d conversations to re-enrich", len(rows))

    bucket = gcs.bucket(BUCKET)
    new_conv_rows = []

    for row in rows:
        sid             = row.conversation_id
        title           = row.title or ""
        source          = row.source or "cluely"
        stored_gcs_path = row.raw_gcs_path or ""
        log.info("  Re-enriching [%s]: %s", source, title or sid)

        # Locate the raw file in GCS — use stored path first, then fallback candidates
        raw      = None
        gcs_path = None
        candidates = []
        if stored_gcs_path.startswith(f"gs://{BUCKET}/"):
            candidates.append(stored_gcs_path[len(f"gs://{BUCKET}/"):])
        candidates += [
            f"transcripts/{source}/{sid}.json",
            f"transcripts/{source}/{sid}.md",
            f"transcripts/cluely/{sid}.json",
        ]
        for candidate in candidates:
            blob = bucket.blob(candidate)
            try:
                raw_text = blob.download_as_text()
                gcs_path = f"gs://{BUCKET}/{candidate}"
                raw = json.loads(raw_text) if candidate.endswith(".json") else {"markdown": raw_text}
                break
            except Exception:
                continue

        if raw is None:
            log.warning("  no raw file found for %s, skipping", sid)
            continue

        # Extract transcript text based on source
        match source:
            case "granola":
                segments = raw.get("transcript", [])
                transcript_text = "\n".join(
                    f"[{'mic' if s.get('source') == 'microphone' else 'system'}]: {s.get('text','').strip()}"
                    for s in segments if s.get("text", "").strip()
                )
                started_at = segments[0].get("start_timestamp") if segments else raw.get("document", {}).get("created_at")
                ended_at   = segments[-1].get("end_timestamp") if segments else raw.get("document", {}).get("updated_at")
                session    = {"startedAt": started_at, "endedAt": ended_at, "title": title}
            case "claude":
                transcript_text = raw.get("markdown", "")
                session = {"startedAt": None, "endedAt": None, "title": title}
            case _:  # cluely (and anything else)
                session  = raw.get("session", {})
                segments = raw.get("transcript", [])
                transcript_text = "\n".join(
                    f"[{s.get('role','')}]: {s.get('text','').strip()}"
                    for s in segments if s.get("text", "").strip()
                )

        meta = enrich(transcript_text, title)
        log.debug("    participants: %s", meta.get("participants"))
        log.debug("    companies:    %s", meta.get("companies"))

        match source:
            case "claude":
                words = transcript_text.split()
                msg_count, word_count = 1, len(words)
            case _:  # granola and cluely are identical
                segments   = raw.get("transcript", [])
                msg_count  = sum(1 for s in segments if s.get("text", "").strip())
                word_count = sum(len(s.get("text", "").split()) for s in segments if s.get("text", "").strip())

        conv_row = build_conv_row(sid, session, meta, gcs_path, msg_count, word_count)
        conv_row.source = source
        new_conv_rows.append(conv_row)

    # Truncate and reload conversations table (avoids streaming buffer issue)
    log.info("[Re-enrich] Truncating conversations table and reloading %d rows...", len(new_conv_rows))
    batch_load(bq, "conversations", new_conv_rows, bigquery.WriteDisposition.WRITE_TRUNCATE)
    log.info("[Re-enrich] Done.")


# ── Granola ingestion ──────────────────────────────────────────────────────────

def load_granola_token() -> str:
    data    = json.loads(GRANOLA_ACCOUNTS_PATH.read_text())
    account = json.loads(data["accounts"])[0]
    return json.loads(account["tokens"])["access_token"]


def granola_post(token: str, endpoint: str, payload: dict) -> Any:
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


def ingest_granola(bq: bigquery.Client, gcs: storage.Client, ingested: set[str]) -> None:
    log.info("[Granola] Starting ingestion...")
    token = load_granola_token()
    docs  = fetch_granola_documents(token)
    log.info("[Granola] Found %d documents, %d already ingested", len(docs), len(ingested))

    for doc in docs:
        did   = doc["id"]
        title = doc.get("title") or ""

        if did in ingested:
            log.debug("  skip %s — already ingested", title or did)
            continue

        # Pull calendar event title as fallback
        if not title:
            cal   = doc.get("google_calendar_event") or {}
            title = cal.get("summary", "") if isinstance(cal, dict) else ""
        if not title:
            log.debug("  skip %s — no title", did)
            continue

        log.info("  Processing: %s", title)

        segments = fetch_granola_transcript(token, did)
        if not segments:
            log.debug("  empty transcript, skipping")
            continue

        # Granola uses source="microphone" for Jesse, "system" for others
        transcript_text = "\n".join(
            f"[{'mic' if s.get('source') == 'microphone' else 'system'}]: {s.get('text','').strip()}"
            for s in segments if s.get("text", "").strip()
        )

        log.debug("  [Claude] enriching...")
        meta = enrich(transcript_text, title)
        log.debug("    topic:        %s", meta.get("topic", "")[:80])
        log.debug("    participants: %s", meta.get("participants"))
        log.debug("    companies:    %s", meta.get("companies"))
        log.debug("    category:     %s / %s", meta.get("category"), meta.get("subcategory"))
        log.debug("    hiring:       %s — %s", meta.get("hiring_related"), meta.get("hiring_company"))
        log.debug("    follow_up:    %s", meta.get("follow_up_required"))

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
        session  = {"startedAt": started_at, "endedAt": ended_at, "title": title}
        conv_row = build_conv_row(did, session, meta, gcs_path, len(msg_rows), total_words)
        conv_row.source           = "granola"
        conv_row.duration_minutes = duration

        batch_load(bq, "conversations", [conv_row])
        batch_load(bq, "messages", msg_rows)

    log.info("[Granola] Done.")


# ── Google Docs ingestion ──────────────────────────────────────────────────────

GDOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def auth_google() -> None:
    """One-time OAuth flow — opens browser, saves token to google_token.json."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow  = InstalledAppFlow.from_client_secrets_file(str(GDOCS_CLIENT_FILE), GDOCS_SCOPES)
    creds = flow.run_local_server(port=0)
    GDOCS_TOKEN_FILE.write_text(creds.to_json())
    log.info("[Google] Token saved to %s", GDOCS_TOKEN_FILE)


def _gdocs_creds() -> Any:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    if not GDOCS_TOKEN_FILE.exists():
        raise EnvironmentError("No Google token found — run: python pipeline.py --auth-google")
    creds = Credentials.from_authorized_user_file(str(GDOCS_TOKEN_FILE), GDOCS_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        GDOCS_TOKEN_FILE.write_text(creds.to_json())
    return creds


def _doc_id_from_url(url: str) -> str:
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError(f"Could not extract doc ID from URL: {url}")
    return m.group(1)


def fetch_gdoc_as_markdown(doc_id: str) -> tuple[str, str]:
    """Returns (title, markdown_text) for a Google Doc."""
    from googleapiclient.discovery import build
    creds   = _gdocs_creds()
    service = build("docs", "v1", credentials=creds, cache_discovery=False)
    doc     = service.documents().get(documentId=doc_id).execute()
    title   = doc.get("title", "Untitled")

    # Walk the document body and extract plain text
    lines = []
    for elem in doc.get("body", {}).get("content", []):
        para = elem.get("paragraph")
        if not para:
            continue
        style = para.get("paragraphStyle", {}).get("namedStyleType", "")
        text  = "".join(
            r.get("textRun", {}).get("content", "")
            for r in para.get("elements", [])
        ).rstrip("\n")
        if not text.strip():
            lines.append("")
            continue
        match style:
            case "HEADING_1":
                lines.append(f"# {text}")
            case "HEADING_2":
                lines.append(f"## {text}")
            case "HEADING_3":
                lines.append(f"### {text}")
            case _:
                lines.append(text)

    return title, "\n".join(lines)


def ingest_gdoc(bq: bigquery.Client, gcs: storage.Client, url: str, ingested: set[str]) -> None:
    doc_id = _doc_id_from_url(url)
    cid    = "gdoc-" + hashlib.sha1(doc_id.encode()).hexdigest()[:16]

    if cid in ingested:
        log.debug("[GDoc] Already ingested: %s", doc_id)
        return

    log.info("[GDoc] Fetching: %s", url)
    title, text = fetch_gdoc_as_markdown(doc_id)
    log.info("  Title: %s  (%d words)", title, len(text.split()))

    sections = re.split(r"\n(?=## )", text)
    if len(sections) <= 1:
        sections = [text]

    log.debug("  [Claude] enriching...")
    meta = enrich(text[:14000], title)
    log.debug("    topic:     %s", meta.get("topic", "")[:80])
    log.debug("    companies: %s", meta.get("companies"))

    # Upload raw to GCS
    bucket    = gcs.bucket(BUCKET)
    blob_name = f"transcripts/gdoc/{doc_id}.md"
    bucket.blob(blob_name).upload_from_string(text, content_type="text/markdown")
    gcs_path  = f"gs://{BUCKET}/{blob_name}"
    log.info("  [GCS] %s", gcs_path)

    now      = datetime.now(timezone.utc).isoformat()
    msg_rows = []
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        msg_rows.append({
            "conversation_id": cid,
            "timestamp":       now,
            "role":            "assistant",
            "content":         section,
            "sequence":        i,
            "word_count":      len(section.split()),
        })

    total_words = sum(r["word_count"] for r in msg_rows)
    session     = {"startedAt": now, "endedAt": now, "title": title}
    conv_row    = build_conv_row(cid, session, meta, gcs_path, len(msg_rows), total_words)
    conv_row.source           = "gdoc"
    conv_row.duration_minutes = None

    batch_load(bq, "conversations", [conv_row])
    batch_load(bq, "messages", msg_rows)
    log.info("  Done — %d sections, %d words", len(msg_rows), total_words)


# ── Claude report ingestion ────────────────────────────────────────────────────

def ingest_claude_report(bq: bigquery.Client, gcs: storage.Client,
                         path: str, ingested: set[str]) -> None:
    """
    Ingest a Claude-generated report (markdown or text file) into BQ + GCS.
    conversation_id  = sha1 of the file path (stable across runs)
    messages         = one row per ## section (or full text if no sections)
    source           = "claude"
    """
    fpath = Path(path).expanduser().resolve()
    if not fpath.exists():
        log.warning("[Claude report] File not found: %s", fpath)
        return

    cid = "claude-" + hashlib.sha1(str(fpath).encode()).hexdigest()[:16]
    if cid in ingested:
        log.debug("[Claude report] Already ingested: %s", fpath.name)
        return

    log.info("[Claude report] Ingesting: %s", fpath.name)
    raw_text = fpath.read_text()

    # Split into sections on ## headers; fall back to whole file as one section
    sections = re.split(r"\n(?=## )", raw_text)
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

    log.debug("  [Claude] enriching...")
    meta = enrich(enrichment_text, fpath.stem.replace("_", " ").title())
    log.debug("    topic:     %s", meta.get("topic", "")[:80])
    log.debug("    companies: %s", meta.get("companies"))

    # File mtime as the date
    mtime = datetime.fromtimestamp(fpath.stat().st_mtime).isoformat() + "Z"

    # Upload raw file to GCS
    bucket = gcs.bucket(BUCKET)
    if not bucket.exists():
        bucket = gcs.create_bucket(BUCKET, location="US")
    blob_name = f"transcripts/claude/{fpath.stem}.md"
    bucket.blob(blob_name).upload_from_string(raw_text, content_type="text/markdown")
    gcs_path = f"gs://{BUCKET}/{blob_name}"
    log.info("  [GCS] %s", gcs_path)

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

    session  = {"startedAt": mtime, "endedAt": mtime, "title": fpath.stem.replace("_", " ").title()}
    conv_row = build_conv_row(cid, session, meta, gcs_path, len(msg_rows), total_words)
    conv_row.source           = "claude"
    conv_row.duration_minutes = None

    batch_load(bq, "conversations", [conv_row])
    batch_load(bq, "messages", msg_rows)
    log.info("  Done — %d sections, %d words", len(msg_rows), total_words)


# ── Local docs folder ingestion ────────────────────────────────────────────────

def ingest_folder(bq: bigquery.Client, gcs: storage.Client,
                  folder: Path, ingested: set[str]) -> None:
    txt_files = sorted(folder.glob("*.txt"))
    if not txt_files:
        log.info("[Docs] No .txt files found in %s", folder)
        return
    log.info("[Docs] Found %d .txt files in %s", len(txt_files), folder)
    for fpath in txt_files:
        try:
            ingest_claude_report(bq, gcs, str(fpath), ingested)
        except Exception as e:
            log.warning("[Docs] Skipping %s — %s", fpath.name, e)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Personal assistant conversation ingestion pipeline."
    )
    parser.add_argument(
        "--re-enrich", action="store_true",
        help="Re-extract metadata for all stored conversations",
    )
    parser.add_argument(
        "--auth-google", action="store_true",
        help="One-time OAuth flow for Google Docs access",
    )
    parser.add_argument(
        "--report", action="append", metavar="PATH",
        help="Ingest a Claude-generated report (repeatable)",
    )
    parser.add_argument(
        "--gdocs", action="append", metavar="URL",
        help="Ingest a Google Doc by URL (repeatable)",
    )
    parser.add_argument(
        "--folder", action="append", metavar="PATH",
        help="Ingest all .txt files in a folder (repeatable); docs/ is always scanned automatically",
    )
    args = parser.parse_args()

    if args.auth_google:
        auth_google()
        return

    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        raise EnvironmentError("Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN before running.")

    log.info("=" * 60)
    log.info("PERSONAL ASSISTANT — CONVERSATION INGESTION PIPELINE")
    log.info("=" * 60)

    bq  = get_bq()
    gcs = get_gcs()
    ensure_dataset_and_tables(bq)

    if args.re_enrich:
        re_enrich(bq, gcs)
        return

    ingested = get_ingested_ids(bq)
    log.info("[BQ] Already ingested: %d conversations", len(ingested))

    ingest_cluely(bq, gcs, ingested)
    ingest_granola(bq, gcs, ingested)

    for path in (args.report or []):
        ingest_claude_report(bq, gcs, path, ingested)

    for url in (args.gdocs or []):
        ingest_gdoc(bq, gcs, url, ingested)

    # Always scan the default docs/ folder, plus any --folder args
    folders = list({DOCS_FOLDER} | {Path(p).expanduser().resolve() for p in (args.folder or [])})
    for folder in folders:
        if folder.is_dir():
            ingest_folder(bq, gcs, folder, ingested)

    log.info("=" * 60)
    log.info("Sample query:")
    log.info("  SELECT date, source, topic, companies")
    log.info("  FROM `%s.%s.conversations`", PROJECT_ID, DATASET)
    log.info("  ORDER BY date DESC")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
