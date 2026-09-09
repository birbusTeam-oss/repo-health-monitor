"""
Repo Health Monitor Agent — built with Strands Agents SDK.

This agent monitors GitHub repositories for health indicators:
- Open pull requests and their review status
- CI/CD pipeline health
- Stale issues needing attention
- Review comments on PRs

It generates a comprehensive health report and can send it to Slack.
"""

import os
import sys

from strands import Agent

from .github_tools import (
    list_open_pull_requests,
    check_ci_status,
    list_stale_issues,
    get_review_comments,
    send_slack_summary,
    generate_health_report,
)


def _get_model():
    """Determine the LLM model provider based on environment.

    Priority:
    1. OLLAMA_HOST + OLLAMA_MODEL → OllamaModel (local or cloud Ollama)
    2. ANTHROPIC_API_KEY → Anthropic direct API
    3. Default: Bedrock (Claude Sonnet 4) — requires AWS credentials
    """
    ollama_host = os.environ.get("OLLAMA_HOST")
    ollama_model = os.environ.get("OLLAMA_MODEL")

    if ollama_host and ollama_model:
        from strands.models.ollama import OllamaModel
        return OllamaModel(
            host=ollama_host,
            model_id=ollama_model,
        )

    if os.environ.get("ANTHROPIC_API_KEY"):
        from strands.models.anthropic import AnthropicModel
        return AnthropicModel(
            client_args={"api_key": os.environ["ANTHROPIC_API_KEY"]},
            model_id="claude-sonnet-4-20250514",
        )

    # Default: Bedrock (Claude Sonnet 4 via AWS)
    return None  # Strands defaults to Bedrock

# System prompt — defines the agent's persona and behavior
SYSTEM_PROMPT = """You are the Repo Health Monitor, an AI agent built with the Strands Agents SDK.

Your job is to help development teams keep their GitHub repositories healthy by:
1. Monitoring open pull requests and their review status
2. Checking CI/CD pipeline health (passing, failing, queued)
3. Identifying stale issues that need attention
4. Getting detailed review comments on specific PRs
5. Generating comprehensive health reports
6. Sending summaries to Slack channels

You are proactive, clear, and concise. When asked to check a repo, use the
appropriate tools to gather data, then synthesize it into an actionable summary.
Always include specific numbers and actionable next steps.

When generating a report, structure it as:
- 🔄 PR Summary: count, oldest, blocking reviews
- 🔧 CI Health: latest run status, failure count
- 🐛 Stale Issues: count, oldest inactive
- 📋 Recommended Actions: bullet list of what to do next
"""


# Create the Strands agent with all GitHub monitoring tools
def create_agent() -> Agent:
    """Create and return the Repo Health Monitor Strands agent.

    The agent is configured with:
    - Custom GitHub monitoring tools (PRs, CI, issues, reviews)
    - Slack notification capability
    - Report generation tool
    - A system prompt defining its monitoring role
    - Auto-detected model provider (Ollama, Anthropic, or Bedrock)

    Returns:
        A Strands Agent instance ready to monitor repositories.
    """
    model = _get_model()
    kwargs = {
        "system_prompt": SYSTEM_PROMPT,
        "tools": [
            list_open_pull_requests,
            check_ci_status,
            list_stale_issues,
            get_review_comments,
            send_slack_summary,
            generate_health_report,
        ],
    }
    if model is not None:
        kwargs["model"] = model
    return Agent(**kwargs)


# Module-level agent instance for import convenience
repo_health_agent = create_agent()


# ─── CLI entry point ─────────────────────────────────────────────────────

def main():
    """Run the Repo Health Monitor from the command line.

    Usage:
        python -m repo_health_monitor               # interactive mode
        python -m repo_health_monitor owner/repo     # single repo report
        python -m repo_health_monitor owner/repo --slack WEBHOOK_URL  # send to Slack

    Environment variables:
        GITHUB_TOKEN (optional): GitHub API token for higher rate limits
        ANTHROPIC_API_KEY or AWS_BEDROCK credentials: for the LLM provider
    """
    args = sys.argv[1:]

    if not args:
        # Interactive mode
        print("\n📊 Repo Health Monitor — powered by Strands Agents SDK\n")
        print("Enter a GitHub repo (owner/repo) to check, or 'quit' to exit.\n")
        while True:
            try:
                user_input = input("repo> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye! 🐦")
                break
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if "/" not in user_input:
                print("Please enter as owner/repo (e.g. strands-agents/sdk-python)")
                continue
            owner, repo = user_input.split("/", 1)
            print(f"\nChecking {owner}/{repo}...\n")
            repo_health_agent(
                f"Generate a comprehensive health report for {owner}/{repo} "
                f"and tell me what actions the team should take."
            )
            print()
    else:
        # Single repo mode
        repo_arg = args[0]
        if "/" not in repo_arg:
            print("Usage: python -m repo_health_monitor owner/repo [--slack WEBHOOK_URL]")
            sys.exit(1)
        owner, repo = repo_arg.split("/", 1)

        # Check for Slack webhook
        slack_url = None
        if "--slack" in args:
            idx = args.index("--slack")
            if idx + 1 < len(args):
                slack_url = args[idx + 1]

        if slack_url:
            repo_health_agent(
                f"Generate a health report for {owner}/{repo} and send it to "
                f"Slack using webhook URL {slack_url}"
            )
        else:
            repo_health_agent(
                f"Generate a comprehensive health report for {owner}/{repo} "
                f"and tell me what actions the team should take."
            )


if __name__ == "__main__":
    main()