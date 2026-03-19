# Personal Assistant — Claude Code Context

## Purpose
This repo is Jesse Watson's personal assistant knowledge base and agent infrastructure.
The goal is to give Claude Code superpowers: persistent memory from conversations + live access to tools.

## Jesse's Role
Jesse Watson — data/analytics leader at Remitly, working on pricing platform, cost data, ML pricing optimization.

## Architecture

This project uses a **multi-agent architecture**. The orchestrator (main personal assistant) delegates to specialized subagents, each with its own MCP tools and scope. The orchestrator routes requests, synthesizes results, and maintains overall context.

```
Orchestrator (personal assistant)
├── Confluence subagent  — reads/searches Remitly Confluence via Atlassian MCP; ingests pages into BigQuery [BUILT]
├── Data subagent        — queries BigQuery, runs ingestion pipeline [BUILT]
├── Slack subagent       — ingests Slack messages [NOT BUILT]
└── Email subagent       — ingests Gmail/email [NOT BUILT]
```

Each subagent has its own MCP tools:
- **Confluence subagent**: Atlassian MCP (`mcp-atlassian` via uvx) — `confluence_search`, `confluence_get_page`, etc.
- **Data subagent**: BigQuery + GCS via `creds.json` service account; runs `pipeline.py`
- **Slack subagent**: Slack API (not configured yet)
- **Email subagent**: Gmail API (not configured yet)

### Data subagent — ingestion pipeline (`pipeline.py`)
Pulls conversations and documents from various sources, enriches them with Claude (claude-sonnet-4-6), and stores them in BigQuery + GCS.

**Sources currently built:**
- `cluely` — platform.cluely.com API, session token from `~/Library/Application Support/cluely/user.session`
- `granola` — api.granola.ai API, WorkOS token from `~/Library/Application Support/Granola/stored-accounts.json`
- `claude` — Claude conversation reports (markdown files)
- `gdocs` — Google Docs via OAuth (`google_oauth_client.json` + `google_token.json`)

**Sources planned (owned by other subagents):**
- `confluence` — delegated to Confluence subagent
- `slack` — delegated to Slack subagent
- `email` — delegated to Email subagent

**BigQuery tables:**
- `conversations` — ~30-column dimension table, one row per session (participants, topics, action items, sentiment, etc.)
- `messages` — fact table, one row per utterance/message
- `partner_fees` — partner fee structure loaded from xlsx via `ingest_partner_fees.py`

**GCS:**
- Raw transcripts at `gs://jesse-personal-assistant/transcripts/{source}/{id}.json`
- Markdown versions at `gs://jesse-personal-assistant/transcripts/{source}/{id}.md`

### Confluence subagent — Atlassian MCP
Reads and searches Remitly Confluence via the Atlassian MCP server. Can ingest pages into BigQuery.

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
- Slack subagent + ingestion
- Email subagent + ingestion
- Scheduled pipeline runs
- Orchestrator memory layer — query BigQuery to answer questions about past conversations, people, decisions

## Session Workflow
At the end of each session, update this file (CLAUDE.md) with anything significant that was set up or changed. A `Stop` hook in `~/.claude/settings.json` will automatically `git add CLAUDE.md`, commit with "Auto-update session notes", and push — so no manual commit/push needed as long as CLAUDE.md is updated before the session ends.

## Current Constraints
- GitHub MCP is NOT set up yet. Do not suggest or include it in any plans.
