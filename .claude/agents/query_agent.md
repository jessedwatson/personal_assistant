# Query Agent

Query BigQuery and GCS for past conversation context — meeting notes, decisions, action items, and discussion history.

## Status: NOT BUILT
This agent is a skeleton. Implementation needed.

## When to use
- "What did we decide about X?"
- "Have I talked to [person] about Y?"
- "What are the open action items from pricing meetings?"
- Any question about past conversations, people, or decisions

## Planned approach
1. Translate the user's question into a BigQuery SQL query against `conversations` and/or `messages`
2. Fetch relevant transcript snippets from GCS if needed for detail
3. Return structured summary with source attribution (meeting title, date, participants)

## BigQuery tables

**`eng-reactor-287421.personal_assistant.conversations`**
~30-column dimension table, one row per session. Key columns (TBD — inspect schema when building).

**`eng-reactor-287421.personal_assistant.messages`**
Fact table, one row per utterance/message.

## GCS
- Raw: `gs://jesse-personal-assistant/transcripts/{source}/{id}.json`
- Markdown: `gs://jesse-personal-assistant/transcripts/{source}/{id}.md`

## Credentials
GCP service account: `creds.json` in project root.

## Output format
Return a concise answer with source attribution: meeting name, date, and key quote or summary.
