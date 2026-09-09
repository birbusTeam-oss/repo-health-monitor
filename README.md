# 📊 Repo Health Monitor

> AI agent that monitors GitHub repositories for stale PRs, failing CI, and unaddressed reviews — built with the [Strands Agents SDK](https://strandsagents.com) for the [Agents for Humans Hackathon](https://agentsforhumans.devpost.com/).

## What It Does

Repo Health Monitor is an autonomous AI agent that runs in the background and keeps watch over your GitHub repositories. Instead of manually checking dozens of repos for stale PRs, broken CI, or issues that have been sitting for weeks, the agent:

- 🔄 **Monitors open pull requests** — tracks age, review status, and blocking comments
- 🔧 **Checks CI/CD health** — identifies failing workflows, cancelled runs, and queued jobs
- 🐛 **Flags stale issues** — surfaces issues with no activity for 14+ days
- 📝 **Reviews PR comments** — pulls inline review comments to see what's blocking merges
- 📊 **Generates health reports** — synthesizes everything into an actionable markdown report
- 💬 **Sends Slack notifications** — posts summaries to your team's Slack channel

The agent only surfaces when there's a real decision to make — that's the philosophy of the Agents for Humans hackathon: agents that run quietly in the background and only ping you when it matters.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User / Scheduler                       │
│  (CLI, cron, or webhook trigger)                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Strands Agent (Agent Loop)                   │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  System      │  │  LLM Provider │  │  Tool Router   │  │
│  │  Prompt      │──│  (Bedrock /   │──│  (Strands SDK) │  │
│  │  (Monitor)   │  │   Ollama)     │  │                │  │
│  └─────────────┘  └──────────────┘  └───────┬────────┘  │
│                                             │            │
└─────────────────────────────────────────────┼────────────┘
                                              │
                    ┌─────────────────────────┼─────────────┐
                    │                         │             │
                    ▼                         ▼             ▼
          ┌──────────────┐       ┌──────────────┐  ┌──────────────┐
          │ GitHub Tools │       │  Report Tool  │  │  Slack Tool  │
          │              │       │               │  │              │
          │ • List PRs   │       │ • Generate    │  │ • Send       │
          │ • Check CI   │       │   health      │  │   summary    │
          │ • Stale      │       │   report      │  │   to Slack   │
          │   issues     │       │   (markdown)  │  │   webhook    │
          │ • PR reviews │       │               │  │              │
          └──────┬───────┘       └───────────────┘  └──────────────┘
                 │
                 ▼
          ┌──────────────┐
          │ GitHub API   │
          │ (REST v3)    │
          └──────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- A GitHub personal access token (optional, but avoids rate limits)
- An LLM provider: AWS Bedrock (default), Anthropic, OpenAI, or Ollama

### Install

```bash
git clone https://github.com/birbusTeam-oss/repo-health-monitor.git
cd repo-health-monitor
pip install -r requirements.txt
```

### Configure

```bash
# Optional: GitHub token for higher API rate limits
export GITHUB_TOKEN=ghp_your_token_here

# Choose your LLM provider (Strands defaults to AWS Bedrock / Claude Sonnet 4)
# For Bedrock: configure AWS credentials via `aws configure`
# For Ollama: see Strands docs for model provider configuration
# For Anthropic: export ANTHROPIC_API_KEY=sk-ant-...
```

### Run

```bash
# Interactive mode — enter repos to check
python -m repo_health_monitor

# Single repo report
python -m repo_health_monitor strands-agents/sdk-python

# Send report to Slack
python -m repo_health_monitor strands-agents/sdk-python --slack https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Example Output

```
📊 Repo Health Report: strands-agents/sdk-python
Generated: 2026-09-08 20:30 UTC

## 🔄 Open Pull Requests (7)
- **#142** [DRAFT] Add multi-agent orchestration — @alice — updated 3d ago (5 review comments)
- **#139** Fix tool registration race condition — @bob — updated 1d ago (2 review comments)
- **#137** Add Ollama model provider — @charlie — updated 7d ago (0 review comments)

## 🔧 Recent CI Runs (last 5)
- ✅ **CI** on `main` — success — 2026-09-08
- ❌ **Integration Tests** on `feature/auth` — failure — 2026-09-07
- ✅ **Lint** on `main` — success — 2026-09-08

## 🐛 Stale Issues (>14 days inactive: 3)
- **#98** Support custom system prompts — 23d inactive
- **#85** Document tool creation patterns — 31d inactive

## 📋 Recommended Actions
- Review PR #142 — has 5 unaddressed review comments and is 3 days old
- Fix CI failure on feature/auth branch — integration tests failing
- Triage stale issues #98 and #85 — consider closing or prioritizing
```

## How It Uses Strands Agents SDK

This project showcases several key Strands SDK patterns:

### 1. Custom Tools with `@tool` Decorator

Each GitHub monitoring function is a Strands tool — a Python function decorated with `@tool` that the agent's LLM can invoke:

```python
from strands import tool

@tool
def list_open_pull_requests(owner: str, repo: str) -> str:
    """List all open pull requests in a GitHub repository.

    Args:
        owner: The GitHub repository owner
        repo: The repository name

    Returns:
        JSON string with PR details.
    """
    # ... GitHub API call ...
```

The docstring and type hints are automatically used by Strands to generate the tool schema for the LLM. The agent decides when to call each tool based on the user's request.

### 2. Agent with Multiple Tools

```python
from strands import Agent

agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=[
        list_open_pull_requests,
        check_ci_status,
        list_stale_issues,
        get_review_comments,
        send_slack_summary,
        generate_health_report,
    ],
)
```

### 3. Agent-as-a-Function

The agent is called like a function — `agent("check repo strands-agents/sdk-python")` — and Strands handles the entire agent loop: LLM reasoning, tool selection, tool execution, and response synthesis.

### 4. Tool Composition

The `generate_health_report` tool internally calls the GitHub API (same endpoints as the other tools) to gather all data in one pass, demonstrating how tools can compose functionality while remaining individually available to the agent's LLM.

## Use Cases

| Who | How They Use It |
|-----|-----------------|
| **Open-source maintainer** | Run daily via cron to check all repos they maintain |
| **Dev team lead** | Get a Slack summary every morning of what needs attention |
| **Solo developer** | Quick check before starting work: "what's broken?" |
| **Hackathon judge** | Monitor hackathon repos for activity and PR status |

## Scheduling

Run it on a schedule with cron:

```bash
# Daily 9 AM health check
0 9 * * * cd /path/to/repo-health-monitor && python -m repo_health_monitor myorg/myrepo --slack $SLACK_WEBHOOK
```

Or use AWS Lambda + EventBridge for cloud scheduling (see deployment guide).

## Built With

- [Strands Agents SDK](https://strandsagents.com) — AI agent framework by AWS
- [GitHub REST API](https://docs.github.com/en/rest) — repository data source
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks) — notification delivery

## License

MIT — see [LICENSE](LICENSE)

## Team

Built by **Team Birby** 🐦 for the [Agents for Humans Hackathon](https://agentsforhumans.devpost.com/) (September 2026).

AI-assisted development with Hermes Agent. We directed the AI to design the tool architecture, write the GitHub API integration, and create the agent orchestration — the full picture of how we directed the AI is in our git history.