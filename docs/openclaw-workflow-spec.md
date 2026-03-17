# OpenClaw Marketing Automation — Dispatch Launch Spec

**Project:** Dispatch — Claude Code skill router
**System:** OpenClaw on Hostinger VPS
**Author:** Visionairy
**Date:** 2026-03-16
**Target:** Always-on marketing automation for Dispatch public launch

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Slack Channel Setup](#2-slack-channel-setup)
3. [Reddit API Setup](#3-reddit-api-setup)
4. [Environment Variables](#4-environment-variables)
5. [Workflow 1 — Keyword Monitor to Slack Queue](#5-workflow-1--keyword-monitor-to-slack-queue)
6. [Workflow 2 — Slack Approval to Publish](#6-workflow-2--slack-approval-to-publish)
7. [Workflow 3 — Launch Schedule](#7-workflow-3--launch-schedule)
8. [Workflow 4 — GitHub Stargazer Outreach](#8-workflow-4--github-stargazer-outreach)
9. [Claude API HTTP Request Node Config](#9-claude-api-http-request-node-config)
10. [Testing Checklist](#10-testing-checklist)

---

## 1. Architecture Overview

### System Layout

```
OpenClaw (Hostinger VPS)
├── Skills: discord, xurl, github, gh-issues, blogwatcher,
│           humanizer, n8n-workflow-automation, slack,
│           openai-image-gen, notion, outlook, todoist, 1password
└── n8n instance (via n8n-workflow-automation skill)
    ├── Workflow 1: Keyword Monitor → Slack Queue     (every 30 min)
    ├── Workflow 2: Slack Approval → Publish           (webhook trigger)
    ├── Workflow 3: Launch Schedule                    (cron dates)
    └── Workflow 4: Stargazer Outreach                 (daily)
```

### Data Flow

```
Platforms (Reddit/Twitter/GitHub/Discord/Blogs)
        │
        ▼ poll every 30 min
[Workflow 1: Monitor]
        │
        ├── deduplicate against Notion "Seen Items" DB
        │
        ├── classify intent via Claude API
        │
        ├── draft response via Claude API
        │
        └── humanize via humanizer skill
                │
                ▼
[Slack #dispatch-queue]
        │
        ├── Approve ──► [Workflow 2: Publish] ──► Platform
        ├── Edit   ──► Edit modal ──► re-queue
        └── Reject ──► Log only
                │
                ▼ all paths
[Notion Activity Log]
```

### Decision Rules

| Content Type | Approval Required | Rationale |
|---|---|---|
| Scheduled launch posts (Show HN, Reddit day 1) | No — auto-fire | Time-sensitive, pre-written |
| Twitter thread (own account) | No — auto-fire | Own content, pre-approved |
| Replies to keyword mentions | Yes — Slack queue | Context-dependent |
| Discord community posts | Yes — Slack queue | Relationship risk |
| Cold outreach emails | Yes — Slack queue | Reputation risk |
| Cold DMs (any platform) | Never auto-fire | Hard rule |
| Negative sentiment responses | Never auto-fire | Hard rule |
| Competitor mentions | Never auto-fire | Hard rule |

### Platforms Summary

| Platform | Skill / Method | Monitor | Post |
|---|---|---|---|
| Twitter/X | xurl skill | Keywords + mentions | xurl skill |
| GitHub | github + gh-issues skills | Issues, PRs, stargazers | github skill |
| Discord | discord skill | #tools, #plugins channels | discord skill |
| Reddit | HTTP Request (n8n) | /new.json endpoint | HTTP Request + OAuth |
| Dev.to / Medium / HN | blogwatcher skill | Keyword submissions | N/A (link share only) |
| Email outreach | outlook skill | N/A | outlook skill |

---

## 2. Slack Channel Setup

Create two channels before setting up workflows.

### #dispatch-queue

**Purpose:** Incoming approval requests — one message per detected item.

**Message format (each item):**
```
[PLATFORM] [INTENT: high/medium/low]
Original: <url>
Context: <first 280 chars of original post>
---
Draft response:
<humanized draft>
---
[Approve] [Edit] [Reject]
```

**Slack app permissions required:**
- `chat:write` — post messages
- `interactive_components` — receive button clicks
- `incoming-webhook` — post from n8n

**Approve/Edit/Reject buttons** are Slack interactive components (Block Kit). Each button posts a callback to the Workflow 2 webhook URL with `action_id` set to `approve`, `edit`, or `reject`, plus the full item payload in `value`.

### #dispatch-log

**Purpose:** Audit trail. One message posted after every publish or reject action.

**Message format:**
```
[PUBLISHED] 2026-03-14 09:05 ET
Platform: twitter
URL: https://twitter.com/...
Content: <first 100 chars>...
```

---

## 3. Reddit API Setup

### Read (no auth required)

Reddit exposes public JSON feeds without authentication.

```
GET https://www.reddit.com/r/ClaudeCode/new.json?limit=25
GET https://www.reddit.com/r/ClaudeDev/new.json?limit=25
GET https://www.reddit.com/r/programming/new.json?limit=25
```

**Headers required:**
```
User-Agent: OpenClaw-Dispatch-Monitor/1.0 (by /u/YOUR_REDDIT_USERNAME)
```

Reddit will 429 or block requests without a descriptive User-Agent.

Parse `data.children[*].data` from the response. Fields used: `id`, `title`, `selftext`, `url`, `permalink`, `created_utc`, `subreddit`.

### Post (OAuth required)

**Step 1 — Create Reddit app:**
1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app"
3. Name: `Dispatch-Automation`
4. Type: `script` (for server-side)
5. Redirect URI: `http://localhost:8080` (unused for script apps)
6. Save `client_id` (shown under app name) and `client_secret`

**Step 2 — Get OAuth token (HTTP Request node):**
```
POST https://www.reddit.com/api/v1/access_token
Authorization: Basic base64(client_id:client_secret)
Content-Type: application/x-www-form-urlencoded
Body: grant_type=password&username=YOUR_REDDIT_USERNAME&password=YOUR_REDDIT_PASSWORD&scope=submit
```

Response: `{ "access_token": "...", "token_type": "bearer", "expires_in": 3600 }`

**Step 3 — Post (HTTP Request node):**
```
POST https://oauth.reddit.com/api/submit
Authorization: Bearer <access_token>
User-Agent: OpenClaw-Dispatch-Monitor/1.0 (by /u/YOUR_REDDIT_USERNAME)
Content-Type: application/x-www-form-urlencoded
Body: sr=ClaudeCode&kind=self&title=<title>&text=<body>&resubmit=false
```

**Token refresh:** Reddit script tokens expire in 1 hour. For Workflow 3 (launch day posts), fetch a fresh token immediately before posting — do not cache overnight.

---

## 4. Environment Variables

Store all secrets in 1password using the `op` CLI skill. Reference them in n8n via environment variable names.

### Required Variables

```bash
# Anthropic
ANTHROPIC_API_KEY          # Claude API key — used in all Claude HTTP Request nodes

# Reddit
REDDIT_CLIENT_ID           # From Reddit app settings
REDDIT_CLIENT_SECRET       # From Reddit app settings
REDDIT_USERNAME            # Account that will post
REDDIT_PASSWORD            # Account password

# Slack
SLACK_BOT_TOKEN            # xoxb- token for posting messages
SLACK_APPROVAL_WEBHOOK_URL # Incoming webhook URL for Workflow 2 trigger
SLACK_QUEUE_CHANNEL_ID     # Channel ID for #dispatch-queue
SLACK_LOG_CHANNEL_ID       # Channel ID for #dispatch-log

# GitHub
GITHUB_TOKEN               # PAT with repo, issues read scope

# Notion
NOTION_API_KEY             # Integration secret
NOTION_SEEN_ITEMS_DB_ID    # Database ID for deduplication store
NOTION_ACTIVITY_LOG_DB_ID  # Database ID for activity log
NOTION_CONTACTS_DB_ID      # Database ID for stargazer CRM

# Twitter/X (managed by xurl skill — confirm var names with skill docs)
TWITTER_API_KEY
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_TOKEN_SECRET

# Hacker News (read-only, no auth — only posting needs credentials)
HN_USERNAME                # Your HN username
HN_PASSWORD                # Your HN password (used in Workflow 3)

# Outreach
OUTLOOK_FROM_ADDRESS       # Sending email address
```

### Load into n8n

In n8n Settings → Environment Variables, reference each as `{{ $env.VAR_NAME }}` inside HTTP Request node headers/body fields. Do not hardcode secrets in node configurations.

### 1password Retrieval Pattern (in OpenClaw shell scripts)

```bash
export ANTHROPIC_API_KEY=$(op item get "Dispatch Automation" --field "anthropic_api_key")
```

---

## 5. Workflow 1 — Keyword Monitor to Slack Queue

**Trigger:** Cron — every 30 minutes
**n8n Workflow ID:** `dispatch-monitor-v1` (set this as the workflow name)

### Keyword List

```
"Claude Code plugin"
"MCP server"
"Claude hooks"
"skill router"
"best plugins for Claude"
"dispatch visionairy"
"@VisionAIrySE"
"n8n Claude"
"claude code extension"
```

### Node Structure

```
[Schedule Trigger]
        │
        ├──────────────────────────────────────┐
        │                                      │
[Reddit Monitor]                    [Twitter Monitor]
        │                                      │
[GitHub Monitor]                   [Discord Monitor]
        │                                      │
[Blog Monitor]                                 │
        │                                      │
        └──────────────────────────────────────┘
                        │
                [Merge — all sources]
                        │
                [Notion Dedup Check]
                        │
              [Filter — new items only]
                        │
              [Claude — Classify Intent]
                        │
              [Filter — intent >= medium]
                        │
              [Claude — Draft Response]
                        │
              [Humanizer — Refine Draft]
                        │
              [Filter — approval rules]
                  /          \
    [Auto-fire path]    [Slack Queue path]
```

---

### Node Definitions

#### Node: Schedule Trigger

```json
{
  "name": "Schedule Trigger",
  "type": "n8n-nodes-base.scheduleTrigger",
  "parameters": {
    "rule": {
      "interval": [{ "field": "minutes", "minutesInterval": 30 }]
    }
  }
}
```

---

#### Node: Reddit Monitor

```json
{
  "name": "Reddit Monitor",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "GET",
    "url": "https://www.reddit.com/r/ClaudeCode/new.json",
    "sendQuery": true,
    "queryParameters": {
      "parameters": [{ "name": "limit", "value": "25" }]
    },
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        {
          "name": "User-Agent",
          "value": "OpenClaw-Dispatch-Monitor/1.0 (by /u/{{ $env.REDDIT_USERNAME }})"
        }
      ]
    },
    "options": { "response": { "response": { "responseFormat": "json" } } }
  }
}
```

Add a second HTTP Request node in parallel for `r/ClaudeDev` and `r/programming` (identical config, different URL). Merge with a Merge node (Append mode) before dedup.

**Post-node — Reddit Extract (Code node):**

```javascript
// Extract post data from Reddit JSON structure
const items = [];
for (const input of $input.all()) {
  const children = input.json.data?.children || [];
  for (const child of children) {
    const post = child.data;
    // Keyword filter
    const text = (post.title + " " + (post.selftext || "")).toLowerCase();
    const keywords = [
      "claude code plugin", "mcp server", "claude hooks",
      "skill router", "best plugins for claude", "dispatch visionairy",
      "@visionairySE", "n8n claude", "claude code extension"
    ];
    const matched = keywords.find(kw => text.includes(kw));
    if (!matched) continue;
    items.push({
      json: {
        source: "reddit",
        id: `reddit_${post.id}`,
        url: `https://reddit.com${post.permalink}`,
        title: post.title,
        body: (post.selftext || "").substring(0, 500),
        created_utc: post.created_utc,
        subreddit: post.subreddit,
        matched_keyword: matched,
        author: post.author
      }
    });
  }
}
return items;
```

---

#### Node: Twitter Monitor

Use the xurl skill's n8n integration node (confirm exact node type name from skill docs). Configuration:

```json
{
  "name": "Twitter Monitor",
  "type": "n8n-nodes-xurl.search",
  "parameters": {
    "query": "\"Claude Code plugin\" OR \"MCP server\" OR \"Claude hooks\" OR \"skill router\" OR \"@VisionAIrySE\" -is:retweet lang:en",
    "max_results": 20,
    "since_id": "{{ $('State Store').item.json.twitter_last_id }}"
  }
}
```

**Post-node — Twitter Normalize (Code node):**

```javascript
const items = [];
for (const tweet of $input.all()) {
  items.push({
    json: {
      source: "twitter",
      id: `twitter_${tweet.json.id}`,
      url: `https://twitter.com/i/web/status/${tweet.json.id}`,
      title: tweet.json.text.substring(0, 100),
      body: tweet.json.text,
      created_utc: Math.floor(new Date(tweet.json.created_at).getTime() / 1000),
      author: tweet.json.author_id,
      matched_keyword: "twitter_mention"
    }
  });
}
return items;
```

---

#### Node: GitHub Monitor

```json
{
  "name": "GitHub Issues Monitor",
  "type": "n8n-nodes-base.github",
  "parameters": {
    "resource": "issue",
    "operation": "getAll",
    "owner": "anthropics",
    "repository": "claude-code",
    "filters": {
      "state": "open",
      "since": "{{ new Date(Date.now() - 35 * 60 * 1000).toISOString() }}"
    },
    "authentication": "oAuth2",
    "limit": 20
  }
}
```

Add parallel nodes for:
- `modelcontextprotocol/servers` — watch new PRs
- `hesreallyhim/awesome-claude-code` — watch new issues

**Post-node — GitHub Normalize (Code node):**

```javascript
const keywords = [
  "claude code plugin", "mcp server", "claude hooks",
  "skill router", "dispatch"
];
const items = [];
for (const issue of $input.all()) {
  const text = ((issue.json.title || "") + " " + (issue.json.body || "")).toLowerCase();
  const matched = keywords.find(kw => text.includes(kw));
  if (!matched) continue;
  items.push({
    json: {
      source: "github",
      id: `github_${issue.json.id}`,
      url: issue.json.html_url,
      title: issue.json.title,
      body: (issue.json.body || "").substring(0, 500),
      created_utc: Math.floor(new Date(issue.json.created_at).getTime() / 1000),
      author: issue.json.user?.login,
      matched_keyword: matched,
      repo: issue.json.repository_url?.split("/").slice(-2).join("/")
    }
  });
}
return items;
```

---

#### Node: Blog Monitor

Use the blogwatcher skill node:

```json
{
  "name": "Blog Monitor",
  "type": "n8n-nodes-blogwatcher.monitor",
  "parameters": {
    "sources": ["dev.to", "medium.com", "news.ycombinator.com"],
    "keywords": [
      "Claude Code plugin", "MCP server", "Claude hooks",
      "skill router", "Dispatch Visionairy"
    ],
    "lookback_minutes": 35
  }
}
```

---

#### Node: Merge All Sources

```json
{
  "name": "Merge All Sources",
  "type": "n8n-nodes-base.merge",
  "parameters": {
    "mode": "append"
  }
}
```

Connect all five source nodes to this Merge node.

---

#### Node: Notion Dedup Check

Query the Notion `Seen Items` database. If an item's `id` already exists, it was processed in a prior run.

```json
{
  "name": "Notion Dedup Check",
  "type": "n8n-nodes-base.notion",
  "parameters": {
    "resource": "databasePage",
    "operation": "getAll",
    "databaseId": "{{ $env.NOTION_SEEN_ITEMS_DB_ID }}",
    "filterType": "manual",
    "filters": {
      "conditions": [
        {
          "key": "item_id",
          "condition": "equals",
          "value": "{{ $json.id }}"
        }
      ]
    },
    "limit": 1
  }
}
```

**Post-node — Filter New Only (IF node):**

```json
{
  "name": "Filter New Only",
  "type": "n8n-nodes-base.if",
  "parameters": {
    "conditions": {
      "options": { "caseSensitive": false },
      "conditions": [
        {
          "leftValue": "{{ $json.results.length }}",
          "operator": { "operation": "equals" },
          "rightValue": 0
        }
      ]
    }
  }
}
```

True path continues. False path ends (already seen).

---

#### Node: Write to Seen Items (Notion)

Run this immediately after the New Only filter — before any downstream failure can cause a re-process.

```json
{
  "name": "Mark Seen in Notion",
  "type": "n8n-nodes-base.notion",
  "parameters": {
    "resource": "databasePage",
    "operation": "create",
    "databaseId": "{{ $env.NOTION_SEEN_ITEMS_DB_ID }}",
    "title": "{{ $json.id }}",
    "propertiesUi": {
      "propertyValues": [
        { "key": "item_id", "type": "rich_text", "textValue": "{{ $json.id }}" },
        { "key": "source", "type": "select", "selectValue": "{{ $json.source }}" },
        { "key": "url", "type": "url", "urlValue": "{{ $json.url }}" },
        { "key": "seen_at", "type": "date", "dateValue": "{{ new Date().toISOString() }}" }
      ]
    }
  }
}
```

---

#### Node: Claude — Classify Intent

```json
{
  "name": "Claude Classify Intent",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "POST",
    "url": "https://api.anthropic.com/v1/messages",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "x-api-key", "value": "{{ $env.ANTHROPIC_API_KEY }}" },
        { "name": "anthropic-version", "value": "2023-06-01" },
        { "name": "content-type", "value": "application/json" }
      ]
    },
    "sendBody": true,
    "contentType": "raw",
    "body": "={{ JSON.stringify({ model: 'claude-haiku-4-5', max_tokens: 100, messages: [{ role: 'user', content: 'Classify the intent of this post. Reply with JSON only: {\"intent\": \"high|medium|low\", \"reason\": \"one sentence\", \"reply_worthy\": true|false}\\n\\nPost from ' + $json.source + ':\\nTitle: ' + $json.title + '\\nBody: ' + $json.body.substring(0, 300) + '\\n\\nHigh = asking for recommendations or help and dispatch/claude-code-plugins are directly relevant.\\nMedium = discussing tools/plugins generally.\\nLow = tangentially related.' }] }) }}"
  }
}
```

**Post-node — Parse Intent (Code node):**

```javascript
const raw = $input.first().json.content[0].text.trim();
let parsed;
try {
  const clean = raw.replace(/```json\n?/, "").replace(/```/, "").trim();
  parsed = JSON.parse(clean);
} catch (e) {
  parsed = { intent: "low", reason: "parse failed", reply_worthy: false };
}
return [{
  json: {
    ...$('Merge All Sources').first().json,  // carry forward item data
    intent: parsed.intent,
    intent_reason: parsed.reason,
    reply_worthy: parsed.reply_worthy
  }
}];
```

**Post-node — Filter Intent (IF node):**

Keep only `medium` or `high` intent items, or where `reply_worthy` is true.

```json
{
  "name": "Filter Intent",
  "type": "n8n-nodes-base.if",
  "parameters": {
    "conditions": {
      "conditions": [
        {
          "leftValue": "{{ $json.intent }}",
          "operator": { "operation": "notEquals" },
          "rightValue": "low"
        }
      ]
    }
  }
}
```

---

#### Node: Claude — Draft Response

```json
{
  "name": "Claude Draft Response",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "POST",
    "url": "https://api.anthropic.com/v1/messages",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "x-api-key", "value": "{{ $env.ANTHROPIC_API_KEY }}" },
        { "name": "anthropic-version", "value": "2023-06-01" },
        { "name": "content-type", "value": "application/json" }
      ]
    },
    "sendBody": true,
    "contentType": "raw",
    "body": "={{ JSON.stringify({ model: 'claude-haiku-4-5', max_tokens: 400, messages: [{ role: 'user', content: 'You are a developer advocate for Dispatch (https://github.com/VisionAIrySE/Dispatch), a Claude Code runtime that surfaces the best tools when you shift tasks (grouped by type: Plugins, Skills, MCPs with install commands) and intercepts tool calls when Claude picks something suboptimal (10+ point gap triggers a block). Free to start, BYOK for full dual-layer..\\n\\nWrite a helpful, non-spammy reply to this ' + $json.source + ' post. Be genuinely useful. Mention Dispatch only if it directly solves their problem. Do not mention competitors. Write like a real developer, not a marketer.\\n\\nPost:\\nTitle: ' + $json.title + '\\nBody: ' + $json.body.substring(0, 400) + '\\n\\nWrite only the reply text, no preamble.' }] }) }}"
  }
}
```

---

#### Node: Humanizer

Use the humanizer skill node. If it accepts raw text input:

```json
{
  "name": "Humanizer",
  "type": "n8n-nodes-humanizer.process",
  "parameters": {
    "text": "{{ $json.content[0].text }}",
    "tone": "developer-casual",
    "preserve_technical_terms": true
  }
}
```

If the humanizer skill does not expose an n8n node directly, call it via HTTP Request to the OpenClaw local API (confirm endpoint with skill docs).

---

#### Node: Apply Approval Rules (Switch node)

```json
{
  "name": "Approval Router",
  "type": "n8n-nodes-base.switch",
  "parameters": {
    "mode": "rules",
    "rules": {
      "rules": [
        {
          "outputKey": "never",
          "conditions": {
            "conditions": [
              {
                "leftValue": "{{ $json.body.toLowerCase() }}",
                "operator": { "operation": "contains" },
                "rightValue": "competitor"
              }
            ]
          }
        },
        {
          "outputKey": "auto",
          "conditions": {
            "conditions": [
              {
                "leftValue": "{{ $json.is_scheduled }}",
                "operator": { "operation": "equals" },
                "rightValue": true
              }
            ]
          }
        },
        {
          "outputKey": "queue",
          "conditions": {
            "conditions": [
              {
                "leftValue": "{{ $json.reply_worthy }}",
                "operator": { "operation": "equals" },
                "rightValue": true
              }
            ]
          }
        }
      ]
    }
  }
}
```

- `never` output: terminate, no action
- `auto` output: connect directly to publisher nodes
- `queue` output: connect to Slack Queue node

---

#### Node: Post to Slack Queue

```json
{
  "name": "Post to Slack Queue",
  "type": "n8n-nodes-base.slack",
  "parameters": {
    "authentication": "accessToken",
    "resource": "message",
    "operation": "post",
    "channel": "{{ $env.SLACK_QUEUE_CHANNEL_ID }}",
    "blocksUi": {
      "blocksValues": [
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "*[{{ $json.source.toUpperCase() }}]* Intent: `{{ $json.intent }}` | {{ $json.url }}\n\n*Original:* {{ $json.body.substring(0, 200) }}..."
          }
        },
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "*Draft:*\n{{ $json.humanized_text }}"
          }
        },
        {
          "type": "actions",
          "elements": [
            {
              "type": "button",
              "text": { "type": "plain_text", "text": "Approve" },
              "style": "primary",
              "action_id": "approve",
              "value": "={{ JSON.stringify({ id: $json.id, source: $json.source, url: $json.url, draft: $json.humanized_text }) }}"
            },
            {
              "type": "button",
              "text": { "type": "plain_text", "text": "Edit" },
              "action_id": "edit",
              "value": "={{ JSON.stringify({ id: $json.id, source: $json.source, url: $json.url, draft: $json.humanized_text }) }}"
            },
            {
              "type": "button",
              "text": { "type": "plain_text", "text": "Reject" },
              "style": "danger",
              "action_id": "reject",
              "value": "={{ JSON.stringify({ id: $json.id }) }}"
            }
          ]
        }
      ]
    }
  }
}
```

---

## 6. Workflow 2 — Slack Approval to Publish

**Trigger:** Webhook (Slack interactive components callback)
**n8n Workflow ID:** `dispatch-approval-v1`

### Slack App Setup for Interactivity

1. In your Slack App settings → Interactive Components
2. Enable "Interactivity"
3. Request URL: `https://YOUR_N8N_HOST/webhook/dispatch-approval`
4. Save

### Node Structure

```
[Webhook Trigger — /webhook/dispatch-approval]
        │
[Parse Slack Payload]
        │
[Route by action_id]
     /    |    \
[approve] [edit] [reject]
     │              │
     │         [Log Reject]
     │
[Route by source]
  /   |   \    \
[reddit] [twitter] [github] [discord] [outlook]
     │
[Platform Publisher]
     │
[Log to Notion Activity]
     │
[Post to #dispatch-log]
```

### Node Definitions

#### Node: Webhook Trigger

```json
{
  "name": "Slack Webhook",
  "type": "n8n-nodes-base.webhook",
  "parameters": {
    "path": "dispatch-approval",
    "httpMethod": "POST",
    "responseMode": "responseNode"
  }
}
```

Slack sends `application/x-www-form-urlencoded` with a `payload` field containing JSON.

#### Node: Parse Slack Payload (Code node)

```javascript
const raw = $input.first().json.body?.payload;
if (!raw) return [{ json: { error: "no payload" } }];
const payload = JSON.parse(decodeURIComponent(raw));
const action = payload.actions?.[0];
const actionId = action?.action_id;
const value = JSON.parse(action?.value || "{}");
return [{
  json: {
    action_id: actionId,
    item_id: value.id,
    source: value.source,
    original_url: value.url,
    draft: value.draft,
    slack_user: payload.user?.username,
    response_url: payload.response_url,
    message_ts: payload.message?.ts,
    channel_id: payload.channel?.id
  }
}];
```

#### Node: Route by Action (Switch node)

Route on `action_id`:
- `approve` → publish path
- `edit` → post ephemeral edit prompt to Slack (out of scope for v1 — send a note saying "edit not yet implemented, please re-queue manually")
- `reject` → log and stop

#### Node: Route by Source (Switch node)

Route on `source` field:
- `reddit` → Reddit Post node
- `twitter` → Twitter Reply node
- `github` → GitHub Comment node
- `discord` → Discord Post node
- `blog` → (no post action — blogs are read-only; skip)

---

#### Node: Reddit Post

```json
{
  "name": "Reddit Post Reply",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "POST",
    "url": "https://oauth.reddit.com/api/comment",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Authorization", "value": "Bearer {{ $('Get Reddit Token').first().json.access_token }}" },
        { "name": "User-Agent", "value": "OpenClaw-Dispatch-Monitor/1.0 (by /u/{{ $env.REDDIT_USERNAME }})" },
        { "name": "Content-Type", "value": "application/x-www-form-urlencoded" }
      ]
    },
    "sendBody": true,
    "contentType": "form-urlencoded",
    "bodyParameters": {
      "parameters": [
        { "name": "parent", "value": "={{ $json.item_id.replace('reddit_', 't3_') }}" },
        { "name": "text", "value": "={{ $json.draft }}" }
      ]
    }
  }
}
```

Note: Add a `Get Reddit Token` node before this that calls the OAuth token endpoint (see Section 3).

---

#### Node: Twitter Reply

Use the xurl skill's reply node:

```json
{
  "name": "Twitter Reply",
  "type": "n8n-nodes-xurl.reply",
  "parameters": {
    "in_reply_to_tweet_id": "={{ $json.item_id.replace('twitter_', '') }}",
    "text": "={{ $json.draft }}"
  }
}
```

---

#### Node: GitHub Comment

```json
{
  "name": "GitHub Comment",
  "type": "n8n-nodes-base.github",
  "parameters": {
    "resource": "issue",
    "operation": "createComment",
    "owner": "={{ $json.original_url.split('/')[3] }}",
    "repository": "={{ $json.original_url.split('/')[4] }}",
    "issueNumber": "={{ $json.original_url.split('/')[6] }}",
    "body": "={{ $json.draft }}"
  }
}
```

---

#### Node: Discord Post

```json
{
  "name": "Discord Post",
  "type": "n8n-nodes-discord.sendMessage",
  "parameters": {
    "guildId": "={{ $json.discord_guild_id }}",
    "channelId": "={{ $json.discord_channel_id }}",
    "content": "={{ $json.draft }}"
  }
}
```

Discord channel IDs must be stored with the item at classification time (add `discord_guild_id` and `discord_channel_id` fields in the Discord monitor node output).

---

#### Node: Log to Notion Activity

```json
{
  "name": "Log to Notion",
  "type": "n8n-nodes-base.notion",
  "parameters": {
    "resource": "databasePage",
    "operation": "create",
    "databaseId": "{{ $env.NOTION_ACTIVITY_LOG_DB_ID }}",
    "title": "{{ $json.source }} — {{ new Date().toISOString().substring(0, 10) }}",
    "propertiesUi": {
      "propertyValues": [
        { "key": "item_id", "type": "rich_text", "textValue": "{{ $json.item_id }}" },
        { "key": "platform", "type": "select", "selectValue": "{{ $json.source }}" },
        { "key": "action", "type": "select", "selectValue": "published" },
        { "key": "original_url", "type": "url", "urlValue": "{{ $json.original_url }}" },
        { "key": "content", "type": "rich_text", "textValue": "{{ $json.draft.substring(0, 1000) }}" },
        { "key": "approved_by", "type": "rich_text", "textValue": "{{ $json.slack_user }}" },
        { "key": "published_at", "type": "date", "dateValue": "{{ new Date().toISOString() }}" }
      ]
    }
  }
}
```

---

#### Node: Post to #dispatch-log

```json
{
  "name": "Post to Dispatch Log",
  "type": "n8n-nodes-base.slack",
  "parameters": {
    "authentication": "accessToken",
    "resource": "message",
    "operation": "post",
    "channel": "{{ $env.SLACK_LOG_CHANNEL_ID }}",
    "text": "[PUBLISHED] {{ new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }) }} ET\nPlatform: {{ $json.source }}\nURL: {{ $json.original_url }}\nContent: {{ $json.draft.substring(0, 100) }}..."
  }
}
```

---

#### Node: Webhook Response

Slack requires a 200 response within 3 seconds or it retries.

```json
{
  "name": "Respond to Slack",
  "type": "n8n-nodes-base.respondToWebhook",
  "parameters": {
    "respondWith": "text",
    "responseBody": "",
    "responseCode": 200
  }
}
```

Place this node early in the flow (right after Parse Slack Payload) using a separate branch so it fires immediately, before the publish operations complete.

---

## 7. Workflow 3 — Launch Schedule

**Trigger:** Cron (specific date/time)
**n8n Workflow ID:** `dispatch-launch-schedule-v1`

This workflow is a single-run sequence. Set it up before launch day and let it fire. Each step has a separate Schedule Trigger node set to its specific time.

### Day 1 Schedule

| Time (ET) | Action | Node |
|---|---|---|
| 9:00 AM | Post to r/ClaudeCode | Reddit Submit |
| 9:05 AM | Post to r/ClaudeDev | Reddit Submit |
| 9:10 AM | Open PR on awesome-claude-code | GitHub PR |
| 10:00 AM | Tweet 1 of 10 | xurl Tweet |
| 10:30 AM | Tweet 2 | xurl Tweet |
| 11:00 AM | Tweet 3 | xurl Tweet |
| ... | Continue at 30-min intervals | ... |
| 5:00 PM | Tweet 10 | xurl Tweet |

### Monday 9:00 AM (Show HN day)

| Time (ET) | Action | Node |
|---|---|---|
| 9:00 AM | Post to Hacker News | HN Submit |
| 9:05 AM | Tweet "Just posted on Show HN: ..." | xurl Tweet |

### Node Definitions

#### Cron Triggers (one per action)

```json
{
  "name": "Day 1 Reddit ClaudeCode — 9:00 AM ET",
  "type": "n8n-nodes-base.scheduleTrigger",
  "parameters": {
    "rule": {
      "interval": [
        {
          "field": "cronExpression",
          "expression": "0 14 LAUNCH_DAY LAUNCH_MONTH *"
        }
      ]
    }
  }
}
```

Replace `LAUNCH_DAY` and `LAUNCH_MONTH` with actual values. ET = UTC-5 (standard) or UTC-4 (daylight). 9:00 AM ET in March = 13:00 UTC.

---

#### Node: Reddit Submit — r/ClaudeCode

```json
{
  "name": "Reddit Submit ClaudeCode",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "POST",
    "url": "https://oauth.reddit.com/api/submit",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Authorization", "value": "Bearer {{ $('Get Reddit Token Launch').first().json.access_token }}" },
        { "name": "User-Agent", "value": "OpenClaw-Dispatch-Monitor/1.0 (by /u/{{ $env.REDDIT_USERNAME }})" },
        { "name": "Content-Type", "value": "application/x-www-form-urlencoded" }
      ]
    },
    "sendBody": true,
    "contentType": "form-urlencoded",
    "bodyParameters": {
      "parameters": [
        { "name": "sr", "value": "ClaudeCode" },
        { "name": "kind", "value": "self" },
        { "name": "title", "value": "Dispatch — auto-routes Claude Code to the right plugin based on what you're doing" },
        { "name": "text", "value": "PASTE_FULL_REDDIT_POST_BODY_HERE" },
        { "name": "resubmit", "value": "false" }
      ]
    }
  }
}
```

Write the post body before launch day. Store it as a static value in this node (not fetched at runtime).

---

#### Node: GitHub PR — awesome-claude-code

```json
{
  "name": "Open PR awesome-claude-code",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "POST",
    "url": "https://api.github.com/repos/hesreallyhim/awesome-claude-code/pulls",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Authorization", "value": "Bearer {{ $env.GITHUB_TOKEN }}" },
        { "name": "Accept", "value": "application/vnd.github+json" },
        { "name": "X-GitHub-Api-Version", "value": "2022-11-28" }
      ]
    },
    "sendBody": true,
    "contentType": "raw",
    "body": "={ \"title\": \"Add Dispatch — skill router for Claude Code\", \"head\": \"VisionAIrySE:add-dispatch\", \"base\": \"main\", \"body\": \"PASTE_PR_DESCRIPTION_HERE\" }"
  }
}
```

Pre-requisite: Fork the repo under VisionAIrySE org, create branch `add-dispatch`, commit the addition to the README, then this node opens the PR.

---

#### Node: Hacker News Submit

HN does not have a public API for submissions. Use a Playwright/HTTP session approach:

```json
{
  "name": "HN Submit",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "POST",
    "url": "https://news.ycombinator.com/r",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Cookie", "value": "user={{ $env.HN_COOKIE }}" },
        { "name": "Content-Type", "value": "application/x-www-form-urlencoded" }
      ]
    },
    "sendBody": true,
    "contentType": "form-urlencoded",
    "bodyParameters": {
      "parameters": [
        { "name": "title", "value": "Show HN: Dispatch – proactively surfaces the best tools when you shift tasks, then intercepts Claude before it picks wrong" },
        { "name": "url", "value": "https://github.com/VisionAIrySE/Dispatch" },
        { "name": "fnid", "value": "={{ $('Get HN FNID').first().json.fnid }}" }
      ]
    }
  }
}
```

HN submission requires a valid session cookie and a `fnid` (CSRF token fetched from the submit page). Add a pre-node `Get HN FNID` that GETs `https://news.ycombinator.com/submit`, parses the `fnid` hidden input, and passes it forward. Store the HN session cookie in 1password as `HN_COOKIE`.

Alternative: Post manually on Show HN day and let Workflow 3 fire only the Twitter announcement.

---

#### Node: Twitter Thread

Create 10 tweet nodes chained sequentially. First tweet:

```json
{
  "name": "Tweet 1",
  "type": "n8n-nodes-xurl.tweet",
  "parameters": {
    "text": "PASTE_TWEET_1_BODY_HERE"
  }
}
```

Subsequent tweets reply to the previous tweet's ID:

```json
{
  "name": "Tweet 2",
  "type": "n8n-nodes-xurl.tweet",
  "parameters": {
    "text": "PASTE_TWEET_2_BODY_HERE",
    "reply": {
      "in_reply_to_tweet_id": "={{ $('Tweet 1').first().json.id }}"
    }
  }
}
```

Write all 10 tweet bodies before launch day.

---

## 8. Workflow 4 — GitHub Stargazer Outreach

**Trigger:** Cron (daily at 8:00 AM ET)
**n8n Workflow ID:** `dispatch-stargazer-outreach-v1`

### Node Structure

```
[Schedule — daily 8 AM ET]
        │
[Get Stargazers — anthropics/claude-code]
[Get Stargazers — modelcontextprotocol/servers]
        │
[Merge Stargazers]
        │
[Filter — has email in profile]
        │
[Filter — not in Notion CRM]
        │
[Filter — has recent activity (< 30 days)]
        │
[Claude — Draft Personalized Outreach]
        │
[Humanizer]
        │
[Post to Slack Queue — email approval]
        │
[On Approve: Outlook Send]
        │
[Log to Notion CRM]
```

---

### Node Definitions

#### Node: Get Stargazers

```json
{
  "name": "Get Stargazers — claude-code",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "GET",
    "url": "https://api.github.com/repos/anthropics/claude-code/stargazers",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Authorization", "value": "Bearer {{ $env.GITHUB_TOKEN }}" },
        { "name": "Accept", "value": "application/vnd.github.star+json" }
      ]
    },
    "sendQuery": true,
    "queryParameters": {
      "parameters": [
        { "name": "per_page", "value": "100" },
        { "name": "page", "value": "1" }
      ]
    }
  }
}
```

The `application/vnd.github.star+json` accept header returns `{ starred_at, user }` objects instead of just user objects, giving you the star timestamp for recency filtering.

For pagination: add a loop that increments `page` until fewer than 100 results are returned. Limit to last 7 days of new stars by filtering on `starred_at`.

---

#### Node: Enrich — Get User Profile (Code node + HTTP Request)

For each stargazer, fetch their full profile to get email:

```json
{
  "name": "Get User Profile",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "GET",
    "url": "https://api.github.com/users/{{ $json.user.login }}",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Authorization", "value": "Bearer {{ $env.GITHUB_TOKEN }}" }
      ]
    }
  }
}
```

---

#### Node: Filter Has Email (IF node)

```json
{
  "name": "Filter Has Email",
  "type": "n8n-nodes-base.if",
  "parameters": {
    "conditions": {
      "conditions": [
        {
          "leftValue": "{{ $json.email }}",
          "operator": { "operation": "isNotEmpty" }
        }
      ]
    }
  }
}
```

---

#### Node: Check Notion CRM (Notion node)

Query `NOTION_CONTACTS_DB_ID` for records where `github_username` equals the current user's login. If found, skip (already contacted).

---

#### Node: Filter Recent Activity (Code node)

```javascript
const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
const updatedAt = new Date($json.updated_at).getTime();
if (updatedAt < thirtyDaysAgo) return [];
return [$input.first()];
```

---

#### Node: Claude — Draft Outreach

```json
{
  "name": "Claude Draft Outreach",
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "POST",
    "url": "https://api.anthropic.com/v1/messages",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "x-api-key", "value": "{{ $env.ANTHROPIC_API_KEY }}" },
        { "name": "anthropic-version", "value": "2023-06-01" },
        { "name": "content-type", "value": "application/json" }
      ]
    },
    "sendBody": true,
    "contentType": "raw",
    "body": "={{ JSON.stringify({ model: 'claude-haiku-4-5', max_tokens: 300, messages: [{ role: 'user', content: 'Write a short, personal cold email (max 5 sentences) to a developer who recently starred the ' + $json.source_repo + ' GitHub repo. Their GitHub bio: ' + ($json.bio || 'not available') + '. Their public repos include: ' + ($json.public_repos || 'unknown') + ' repos.\\n\\nContext: I built Dispatch (https://github.com/VisionAIrySE/Dispatch), a Claude Code runtime that proactively surfaces the best tools when you shift tasks — Plugins, Skills, and MCPs with install commands, grouped by type — and intercepts tool calls when Claude picks something suboptimal.\\n\\nWrite: subject line on first line, blank line, then email body. Be human. Do not pitch hard. Reference their interest in ' + $json.source_repo + '.' }] }) }}"
  }
}
```

---

#### Node: Post to Slack Queue (Outreach)

Same Block Kit format as Workflow 1, but labeled `[EMAIL OUTREACH]` and showing `To: {{ $json.email }}` and `Subject: {{ $json.subject }}`.

Include `action_id: approve_email` to distinguish from reply approvals in Workflow 2.

---

#### Node: Outlook Send

Use the outlook skill's n8n node:

```json
{
  "name": "Outlook Send",
  "type": "n8n-nodes-outlook.sendEmail",
  "parameters": {
    "from": "{{ $env.OUTLOOK_FROM_ADDRESS }}",
    "to": "{{ $json.email }}",
    "subject": "={{ $json.subject }}",
    "body": "={{ $json.humanized_body }}",
    "bodyType": "text"
  }
}
```

---

#### Node: Log to Notion CRM

Create a record in `NOTION_CONTACTS_DB_ID`:

```json
{
  "propertiesUi": {
    "propertyValues": [
      { "key": "github_username", "type": "rich_text", "textValue": "{{ $json.login }}" },
      { "key": "email", "type": "email", "emailValue": "{{ $json.email }}" },
      { "key": "source_repo", "type": "rich_text", "textValue": "{{ $json.source_repo }}" },
      { "key": "status", "type": "select", "selectValue": "contacted" },
      { "key": "contacted_at", "type": "date", "dateValue": "{{ new Date().toISOString() }}" },
      { "key": "outreach_content", "type": "rich_text", "textValue": "{{ $json.humanized_body.substring(0, 500) }}" }
    ]
  }
}
```

---

## 9. Claude API HTTP Request Node Config

This is the standard config used across all four workflows. Copy-paste this as a base.

### Headers

```json
{
  "x-api-key": "{{ $env.ANTHROPIC_API_KEY }}",
  "anthropic-version": "2023-06-01",
  "content-type": "application/json"
}
```

### Body (raw JSON)

```json
{
  "model": "claude-haiku-4-5",
  "max_tokens": 300,
  "messages": [
    {
      "role": "user",
      "content": "YOUR_PROMPT_HERE"
    }
  ]
}
```

### Model Selection

| Use Case | Model | Max Tokens |
|---|---|---|
| Intent classification | `claude-haiku-4-5` | 100 |
| Draft response (reply) | `claude-haiku-4-5` | 400 |
| Cold outreach email | `claude-haiku-4-5` | 300 |
| Complex reasoning | `claude-sonnet-4-5` | 1000 |

Use Haiku for all automation tasks. It is 15x cheaper than Sonnet and handles these tasks reliably at production scale.

### Estimated Monthly API Cost

At 30-minute intervals, Workflow 1 runs 48 times/day. Assuming 10 matched items per run with 2 Claude calls each (classify + draft):

```
48 runs/day × 10 items × 2 calls × 500 tokens avg = 480,000 tokens/day
Haiku input: $0.80/MTok → 0.48M × $0.80 = $0.38/day
Haiku output: $4.00/MTok → ~50K output tokens × $4.00 = $0.20/day
Total: ~$0.58/day → ~$18/month
```

This is a worst-case estimate. In practice, most runs will find 0-2 new items.

### Response Parsing

Always strip markdown code fences before JSON.parse. Claude API returns plain text in `response.content[0].text`. Some prompts will return markdown-wrapped JSON even when instructed not to.

```javascript
function parseClaudeJSON(response) {
  let text = response.content[0].text.trim();
  if (text.startsWith("```")) {
    text = text.split("```")[1];
    if (text.startsWith("json")) text = text.substring(4);
    text = text.split("```")[0];
  }
  return JSON.parse(text.trim());
}
```

---

## 10. Testing Checklist

Complete these in order before going live.

### Phase 1 — Infrastructure (30 min)

- [ ] Both Slack channels created: `#dispatch-queue`, `#dispatch-log`
- [ ] Slack app created with `chat:write`, `interactive_components`, `incoming-webhook` scopes
- [ ] All environment variables loaded into n8n from 1password
- [ ] Notion databases created:
  - [ ] `Seen Items` (columns: item_id, source, url, seen_at)
  - [ ] `Activity Log` (columns: item_id, platform, action, original_url, content, approved_by, published_at)
  - [ ] `Contacts CRM` (columns: github_username, email, source_repo, status, contacted_at, outreach_content)
- [ ] Reddit app created, client_id and client_secret saved to 1password
- [ ] Reddit OAuth token test: `curl -X POST https://www.reddit.com/api/v1/access_token ...` returns 200

### Phase 2 — Workflow 1 (45 min)

- [ ] Reddit Monitor node: run manually, verify response structure matches extractor Code node
- [ ] Twitter Monitor node: run manually, verify at least 1 result returned for known keyword
- [ ] GitHub Monitor node: run manually against `anthropics/claude-code`, verify issues returned
- [ ] Blog Monitor node: run manually, verify no error
- [ ] Merge node: verify all sources arrive as separate items (not nested)
- [ ] Notion Dedup Check: insert a test item_id into Seen Items, run workflow, verify test item is filtered out
- [ ] Claude Classify Intent: run manually with a sample post, verify JSON response parsed correctly
- [ ] Claude Draft Response: run manually, verify plain text response (not markdown)
- [ ] Humanizer: run manually, verify output is human-readable
- [ ] Slack Queue post: verify message appears in `#dispatch-queue` with working Approve/Edit/Reject buttons

### Phase 3 — Workflow 2 (30 min)

- [ ] Slack interactive components URL configured and verified (Slack sends a verification challenge on save)
- [ ] Click Approve on a test item, verify n8n webhook receives payload within 3s
- [ ] Parse Slack Payload node: verify all fields extracted correctly (action_id, draft, source, original_url)
- [ ] Immediate 200 response to Slack: verify Slack does not show error/timeout state
- [ ] Twitter publish: approve a test item with source=twitter, verify tweet posted
- [ ] Notion Activity Log: verify record created with correct fields
- [ ] `#dispatch-log` post: verify confirmation message appears

### Phase 4 — Workflow 3 (20 min)

- [ ] All cron times verified in UTC (account for ET offset)
- [ ] Reddit post bodies written and stored in node configs
- [ ] Twitter thread (10 tweets) written and stored
- [ ] awesome-claude-code fork and branch `add-dispatch` prepared with README addition
- [ ] GitHub PR body written
- [ ] Run Workflow 3 in test mode 24 hours before launch to catch cron config errors (then disable until launch day)

### Phase 5 — Workflow 4 (20 min)

- [ ] Get Stargazers node: run manually, verify user objects returned with `starred_at`
- [ ] Get User Profile: run manually for one username, verify `email` field present/absent
- [ ] Filter Has Email: verify users without email are dropped
- [ ] Notion CRM check: insert a test username, verify they are filtered out
- [ ] Claude outreach draft: run manually, verify subject + body format correct
- [ ] Slack approval post: verify `[EMAIL OUTREACH]` message appears correctly
- [ ] Outlook send: approve one test item, verify email arrives at test inbox
- [ ] Notion CRM log: verify contact record created with status=contacted

### Phase 6 — End-to-End Dry Run (30 min)

- [ ] Post a test message in r/ClaudeCode sandbox (use r/test) containing "Claude Code plugin"
- [ ] Wait up to 35 minutes for Workflow 1 to pick it up
- [ ] Verify Slack queue message appears with correct content
- [ ] Click Approve, verify:
  - [ ] Reply posted on Reddit
  - [ ] Notion Activity Log updated
  - [ ] `#dispatch-log` confirmation posted
- [ ] Verify the same item does NOT re-appear in the next 30-min run (dedup working)

### Launch Day Checklist

- [ ] Verify all four workflows are active in n8n
- [ ] Verify Slack app is connected and interactive
- [ ] Reddit OAuth token freshly generated (expires 1hr)
- [ ] Monitor `#dispatch-queue` for first 2 hours after launch posts go live
- [ ] Monitor `#dispatch-log` for confirmation of scheduled posts firing

---

*End of spec. Estimated setup time: 2-3 hours with all credentials ready in 1password.*
