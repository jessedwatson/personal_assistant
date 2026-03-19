# Personal Assistant — Claude Code Context

## Purpose
This repo is Jesse Watson's personal assistant knowledge base and agent infrastructure.
The goal is to give Claude Code superpowers: persistent memory from conversations + live access to tools.

## Jesse's Role
Jesse Watson — data/analytics leader at Remitly, working on pricing platform, cost data, ML pricing optimization.

## Architecture

This project uses a **multi-agent architecture** with two core agents:

1. **Ingestion Agent** — proactively pulls from Granola and Cluely, writes to BQ+GCS
2. **Query Agent** — triggered on user questions; fans out to all available sources and synthesizes a single answer

```
Orchestrator (personal assistant)
├── Ingestion Agent (scheduled/triggered — writes to BQ+GCS)
│    ├── Granola subagent  — proactive, checks for new meeting transcripts [BUILT]
│    └── Cluely subagent   — proactive, checks for new sessions [BUILT]
└── Query Agent (on demand — fans out to all sources, synthesizes answer) [NOT BUILT]
     ├── BigQuery/GCS      — past conversations, transcripts, decisions [BUILT storage]
     ├── Confluence        — Atlassian MCP, reads/searches Remitly Confluence [BUILT]
     ├── Slack             — reads Slack messages [NOT BUILT]
     └── Email             — reads Gmail [NOT BUILT]
```

**Important:** The Ingestion Agent only proactively checks Granola and Cluely. The Query Agent is triggered on demand by a user question — it fans out to all available sources in parallel, then synthesizes results into a single answer. Confluence, Slack, and Email are never ingested automatically; they are always queried live.

### Ingestion Agent — `pipeline.py`
Proactively pulls meeting notes from Granola and Cluely, enriches with Claude (claude-sonnet-4-6), and stores in BigQuery + GCS. Also has manual/one-off loaders for Claude reports and Google Docs.

**Sources (proactive):**
- `granola` — api.granola.ai API, WorkOS token from `~/Library/Application Support/Granola/stored-accounts.json`
- `cluely` — platform.cluely.com API, session token from `~/Library/Application Support/cluely/user.session`

**Sources (manual/one-off, not proactive):**
- `claude` — Claude conversation reports (markdown files)
- `gdocs` — Google Docs via OAuth (`google_oauth_client.json` + `google_token.json`)

**BigQuery tables:**
- `conversations` — ~30-column dimension table, one row per session (participants, topics, action items, sentiment, etc.)
- `messages` — fact table, one row per utterance/message
- `partner_fees` — partner fee structure loaded from xlsx via `ingest_partner_fees.py`

**GCS:**
- Raw transcripts at `gs://jesse-personal-assistant/transcripts/{source}/{id}.json`
- Markdown versions at `gs://jesse-personal-assistant/transcripts/{source}/{id}.md`

### Confluence subagent — Atlassian MCP (on demand)
Reads and searches Remitly Confluence via the Atlassian MCP server. Triggered only when the user asks. Not part of the ingestion pipeline.

MCP configured in `~/.claude.json` (NOT `~/.claude/settings.json`) using `mcp-atlassian` via uvx:
- Confluence URL: `https://remitly.atlassian.net/wiki`
- Jira URL: `https://remitly.atlassian.net/`
- Username: `jessew@remitly.com`
- Token: stored in `~/.claude.json` (same token works for both)
- uvx path: `/Users/jessew/Library/Python/3.9/bin/uvx`

Relevant Confluence spaces: `Pricing` (Pricing Analytics), `PricingPromotions` (Pricing & Promotions), `AN` (Analytics), `DP1` (Analytics Engineering), `MLE` (Machine Learning), `PAX` (Payments Acceptance).

### Other scripts
- `ingest_partner_fees.py` — one-off loader for Partner Fee Structure xlsx → `partner_fees` BQ table
- `org_context.md` — Remitly org chart used for name normalization during enrichment

### Infrastructure
- BigQuery dataset: `eng-reactor-287421.personal_assistant`
- GCS bucket: `jesse-personal-assistant`
- GCP credentials: `creds.json` (service account)
- Anthropic model: `claude-sonnet-4-6`

## Vision / What's Not Built Yet
- Query Agent — fan-out orchestrator that queries all sources (BQ/GCS, Confluence, Slack, Email) in parallel and synthesizes a single answer
- Slack subagent (on demand)
- Email subagent (on demand)
- Scheduled/triggered runs of the Ingestion Agent

## Session Workflow
At the end of each session, update this file (CLAUDE.md) with anything significant that was set up or changed. A `Stop` hook in `~/.claude/settings.json` will automatically `git add CLAUDE.md`, commit with "Auto-update session notes", and push — so no manual commit/push needed as long as CLAUDE.md is updated before the session ends.

## Current Constraints
- GitHub MCP is NOT set up yet. Do not suggest or include it in any plans.
