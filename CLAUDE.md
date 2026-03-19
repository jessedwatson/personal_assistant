# Personal Assistant — Orchestrator

## Purpose
This is Jesse Watson's personal assistant. When a question comes in, fan out to the relevant subagents, synthesize their results, and answer.

## Jesse's Role
Jesse Watson — data/analytics leader at Remitly, working on pricing platform, cost data, ML pricing optimization.

## Subagent Routing

Invoke subagents based on the question. Fan out to multiple in parallel when relevant.

| Question type | Subagents to invoke |
|---|---|
| Past meetings, decisions, context | `query_agent` |
| Remitly docs, specs, team pages | `confluence_agent` |
| Ingest new Granola/Cluely sessions | `ingestion_agent` |
| Slack threads, messages | `slack_agent` (not built) |
| Email | `email_agent` (not built) |
| Improve agent architecture, Claude Code best practices | `claude_advisor_agent` |

**Example:** "What's the status of pricing platform?"
→ spawn `confluence_agent` + `query_agent` in parallel → synthesize into one answer.

Invoke with `@agent_name` or let the orchestrator decide.

## Architecture

```
CLAUDE.md (orchestrator)
└── .claude/agents/
    ├── confluence_agent.md   — searches Remitly Confluence via Atlassian MCP [BUILT]
    ├── ingestion_agent.md    — runs Granola/Cluely pipeline, writes to BQ+GCS [BUILT]
    ├── query_agent.md        — reads BigQuery/GCS for past conversation context [NOT BUILT]
    ├── slack_agent.md        — searches Slack messages [NOT BUILT]
    ├── email_agent.md        — reads Gmail [NOT BUILT]
    └── claude_advisor_agent.md — audits architecture against latest Claude Code docs [BUILT]
```

## Infrastructure

- **BigQuery:** `eng-reactor-287421.personal_assistant`
  - `conversations` — ~30-column dimension table, one row per session
  - `messages` — fact table, one row per utterance/message
  - `partner_fees` — partner fee structure
- **GCS:** `jesse-personal-assistant`
  - `gs://jesse-personal-assistant/transcripts/{source}/{id}.json` — raw
  - `gs://jesse-personal-assistant/transcripts/{source}/{id}.md` — markdown
- **GCP credentials:** `creds.json` (service account)
- **Anthropic model:** `claude-sonnet-4-6`

## Other Scripts

- `pipeline.py` — ingestion agent entry point (Granola + Cluely sources)
- `ingest_partner_fees.py` — one-off loader for Partner Fee Structure xlsx
- `org_context.md` — Remitly org chart for name normalization during enrichment

## What's Not Built Yet

- `query_agent` — BigQuery/GCS reader for past conversation context
- `slack_agent` — Slack reader
- `email_agent` — Gmail reader
- Scheduled/triggered runs of the ingestion agent

## Session Workflow

At the end of each session, update this file (CLAUDE.md) with anything significant that was set up or changed. A `Stop` hook in `~/.claude/settings.json` will automatically `git add CLAUDE.md`, commit with "Auto-update session notes", and push.

## Current Constraints

- GitHub MCP is NOT set up yet. Do not suggest or include it in any plans.
