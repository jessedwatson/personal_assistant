---
name: slack-agent
description: NOT AVAILABLE. Do not delegate to this agent.
model: haiku
---
# Slack Agent (Not Built Yet)
This agent is a placeholder. Do not use.

# Slack Agent

Search Slack messages and threads relevant to a question.

## Status: NOT BUILT
This agent is a skeleton. Implementation needed.

## When to use
- "What's the latest on X in Slack?"
- "Find the thread where we discussed Y"
- Any question that might have been discussed in Slack

## Planned approach
- Use Slack MCP or API to search messages by keyword/date/channel
- Return relevant threads with context

## Output format
Return matching messages with channel, sender, timestamp, and a snippet. Group by thread where relevant.
