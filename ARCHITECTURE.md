# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      User / Scheduler                           │
│  (CLI, cron, webhook, or web dashboard trigger)                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Strands Agent (Agent Loop)                      │
│                                                                 │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐   │
│  │  System Prompt │    │  LLM Provider  │    │  Tool Router  │   │
│  │  (Monitor role)│───▶│  (Ollama /     │───▶│  (Strands SDK)│   │
│  │                │    │   Anthropic /  │    │               │   │
│  │  "You are the  │    │   Bedrock)     │    │  Selects the  │   │
│  │   Repo Health  │    │                │    │  right tool   │   │
│  │   Monitor..."  │    │  Claude Sonnet │    │  for the job  │   │
│  └───────────────┘    │  4 (default)   │    │               │   │
│                        └───────────────┘    └──────┬────────┘   │
│                                                    │            │
└────────────────────────────────────────────────────┼────────────┘
                                                     │
                    ┌────────────────────────────────┼────────────┐
                    │                                │            │
                    ▼                                ▼            ▼
          ┌────────────────┐         ┌──────────────────┐  ┌──────────────┐
          │  GitHub Tools  │         │  Report Tool     │  │  Slack Tool  │
          │                │         │                  │  │              │
          │ • list_open_   │         │ • generate_      │  │ • send_slack │
          │   pull_        │         │   health_report  │  │   _summary   │
          │   requests     │         │                  │  │              │
          │ • check_ci_    │         │   Synthesizes    │  │   Posts to   │
          │   status       │         │   all data into  │  │   Slack      │
          │ • list_stale_  │         │   markdown       │  │   incoming   │
          │   issues       │         │   report         │  │   webhook    │
          │ • get_review_  │         │                  │  │              │
          │   comments     │         │                  │  │              │
          └───────┬────────┘         └──────────────────┘  └──────────────┘
                  │
                  ▼
          ┌────────────────┐
          │  GitHub REST   │
          │  API (v3)      │
          │                │
          │  api.github.com│
          └────────────────┘
```

## Component Details

### 1. Strands Agent (Agent Loop)
The core agent loop is powered by the Strands Agents SDK. It receives a user query (e.g., "check the health of strands-agents/sdk-python"), uses the LLM to understand the request, selects the appropriate tools, executes them, and synthesizes the results into a coherent response.

### 2. LLM Provider (Auto-detected)
The agent auto-detects the LLM provider based on environment variables:
- **Ollama** (local or cloud) — `OLLAMA_HOST` + `OLLAMA_MODEL`
- **Anthropic** (direct API) — `ANTHROPIC_API_KEY`
- **Amazon Bedrock** (default) — requires AWS credentials

All providers use Claude Sonnet 4 or equivalent models with tool-calling support.

### 3. GitHub Monitoring Tools (6 custom @tool functions)
Each tool is a Python function decorated with `@tool` from Strands. The SDK automatically generates the tool schema from the function's docstring and type hints, making it available to the LLM's tool-calling interface.

| Tool | Purpose | GitHub API Endpoint |
|------|---------|-------------------|
| `list_open_pull_requests` | Get all open PRs with metadata | `/repos/{owner}/{repo}/pulls` |
| `check_ci_status` | Get recent workflow runs | `/repos/{owner}/{repo}/actions/runs` |
| `list_stale_issues` | Find issues inactive > N days | `/repos/{owner}/{repo}/issues?since=` |
| `get_review_comments` | Get PR review states + inline comments | `/repos/{owner}/{repo}/pulls/{n}/reviews` |
| `generate_health_report` | Synthesize all data into markdown report | (calls above internally) |
| `send_slack_summary` | Post report to Slack channel | (Slack webhook URL) |

### 4. Web Dashboard (FastAPI)
Optional web interface providing:
- `GET /` — HTML dashboard with interactive repo checker
- `GET /api/health/{owner}/{repo}` — Full health report (JSON)
- `GET /api/prs/{owner}/{repo}` — PR list (JSON)
- `GET /api/ci/{owner}/{repo}` — CI runs (JSON)
- `GET /api/stale/{owner}/{repo}` — Stale issues (JSON)

### 5. CLI Interface
The agent can be run from the command line in three modes:
- **Interactive**: `python -m repo_health_monitor` — enter repos interactively
- **Single repo**: `python -m repo_health_monitor owner/repo` — one-shot report
- **Slack notification**: `python -m repo_health_monitor owner/repo --slack WEBHOOK_URL`

## Data Flow

```
User Input: "Check health of owner/repo"
         │
         ▼
  ┌─────────────┐
  │ Strands     │  LLM understands the request
  │ Agent Loop  │  and decides which tools to call
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Tool:       │  Calls GitHub API
  │ list_PRs    │  → Returns JSON with 50 PRs
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Tool:       │  Calls GitHub API
  │ check_ci    │  → Returns JSON with 10 CI runs
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Tool:       │  Calls GitHub API
  │ stale_issues│  → Returns JSON with 3 stale issues
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ LLM         │  Synthesizes all tool results
  │ Synthesis   │  into actionable health report
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Output:     │  "📊 Repo Health Report: owner/repo
  │ Response    │   50 open PRs, 1 failing CI,
  │             │   3 stale issues. Actions: ..."
  └─────────────┘
```