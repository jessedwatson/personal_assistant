---
name: ingestion-agent
description: Runs the ingestion pipeline to pull new sessions from Granola and Cluely into BigQuery and GCS. Use when the user asks to ingest new meetings, sync recent Granola transcripts, or sync recent Cluely sessions.
tools: Bash, Read
model: inherit
---
# Ingestion Agent

Run the ingestion pipeline to pull new sessions from Granola and Cluely into BigQuery and GCS.

## When to use
- User asks to ingest new meetings or sessions
- Syncing recent Granola meeting transcripts
- Syncing recent Cluely sessions

## Entry point
```
python pipeline.py [--source granola|cluely|all] [--since YYYY-MM-DD]
```

## Sources

| Source | API | Auth |
|---|---|---|
| `granola` | `api.granola.ai` | WorkOS token from `~/Library/Application Support/Granola/stored-accounts.json` |
| `cluely` | `platform.cluely.com` | Session token from `~/Library/Application Support/cluely/user.session` |

Manual/one-off sources (not run automatically):
- `claude` — Claude conversation reports (markdown files)
- `gdocs` — Google Docs via OAuth (`google_oauth_client.json` + `google_token.json`)

## Output
- BigQuery: `eng-reactor-287421.personal_assistant.conversations` + `.messages`
- GCS: `gs://jesse-personal-assistant/transcripts/{source}/{id}.json` and `.md`
- GCP credentials: `creds.json`

## Output format
Report how many sessions were ingested, any errors, and the date range covered.
