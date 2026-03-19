# Personal Assistant — Claude Code Context

## Purpose
This repo is Jesse Watson's personal assistant knowledge base and agent infrastructure.
The goal is to give Claude Code superpowers: persistent memory from conversations + live access to tools.

## Jesse's Role
Jesse Watson — data/analytics leader at Remitly, working on pricing platform, cost data, ML pricing optimization.

## Architecture

### Ingestion pipeline (`pipeline.py`)
Pulls conversations and documents from various sources, enriches them with Claude (claude-sonnet-4-6), and stores them in BigQuery + GCS.

**Sources currently built:**
- `cluely` — platform.cluely.com API, session token from `~/Library/Application Support/cluely/user.session`
- `granola` — api.granola.ai API, WorkOS token from `~/Library/Application Support/Granola/stored-accounts.json`
- `claude` — Claude conversation reports (markdown files)
- `gdocs` — Google Docs via OAuth (`google_oauth_client.json` + `google_token.json`)

**Sources planned but not yet built:**
- `slack` — Slack message ingestion
- `email` — Gmail or similar
- `confluence` — Remitly Confluence wiki (token is configured, see below)

**BigQuery tables:**
- `conversations` — ~30-column dimension table, one row per session (participants, topics, action items, sentiment, etc.)
- `messages` — fact table, one row per utterance/message
- `partner_fees` — partner fee structure loaded from xlsx via `ingest_partner_fees.py`

**GCS:**
- Raw transcripts at `gs://jesse-personal-assistant/transcripts/{source}/{id}.json`
- Markdown versions at `gs://jesse-personal-assistant/transcripts/{source}/{id}.md`

### Other scripts
- `ingest_partner_fees.py` — one-off loader for Partner Fee Structure xlsx → `partner_fees` BQ table
- `org_context.md` — Remitly org chart used for name normalization during enrichment

### Infrastructure
- BigQuery dataset: `eng-reactor-287421.personal_assistant`
- GCS bucket: `jesse-personal-assistant`
- GCP credentials: `creds.json` (service account)
- Anthropic model: `claude-sonnet-4-6`

## Atlassian Access (Jira + Confluence)
MCP configured in `~/.claude/settings.json` under `mcpServers.atlassian` using `mcp-atlassian` via uvx:
- Confluence URL: `https://remitly.atlassian.net/wiki`
- Jira URL: `https://remitly.atlassian.net/`
- Username: `jessew@remitly.com`
- Token: stored in settings.json (same token works for both)
- uvx path: `/Users/jessew/Library/Python/3.9/bin/uvx`

Relevant Confluence spaces: `Pricing` (Pricing Analytics), `PricingPromotions` (Pricing & Promotions), `AN` (Analytics), `DP1` (Analytics Engineering), `MLE` (Machine Learning), `PAX` (Payments Acceptance).

Can also query Confluence directly via REST API using the token from settings.json.

## Vision / What's Not Built Yet
- Agent layer that can query BigQuery context and answer questions about past conversations, people, decisions
- Slack ingestion
- Email ingestion
- Confluence page ingestion into BigQuery
- Scheduled pipeline runs

## Current Constraints
- GitHub MCP is NOT set up yet. Do not suggest or include it in any plans.
