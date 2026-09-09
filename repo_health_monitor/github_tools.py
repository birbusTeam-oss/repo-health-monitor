"""
GitHub tools for the Repo Health Monitor agent.

Each tool is a Python function decorated with @tool from the Strands SDK.
The agent uses these tools to inspect repository health.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

import requests
from strands import tool


# ─── helpers ──────────────────────────────────────────────────────────────

GITHUB_API = "https://api.github.com"


def _gh_headers() -> dict[str, str]:
    """Build GitHub API headers with optional token auth."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_iso(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return None


# ─── tools ────────────────────────────────────────────────────────────────


@tool
def list_open_pull_requests(owner: str, repo: str) -> str:
    """List all open pull requests in a GitHub repository.

    Args:
        owner: The GitHub repository owner (e.g. "strands-agents")
        repo: The repository name (e.g. "sdk-python")

    Returns:
        JSON string with PR details: number, title, author, created date,
        updated date, draft status, labels, and review comments count.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
    params = {"state": "open", "per_page": 50, "sort": "updated", "direction": "desc"}
    resp = requests.get(url, headers=_gh_headers(), params=params, timeout=30)
    resp.raise_for_status()

    prs = []
    for pr in resp.json():
        prs.append({
            "number": pr["number"],
            "title": pr["title"],
            "author": pr["user"]["login"],
            "created_at": pr["created_at"],
            "updated_at": pr["updated_at"],
            "draft": pr["draft"],
            "labels": [l["name"] for l in pr.get("labels", [])],
            "review_comments": pr.get("review_comments", 0),
            "comments": pr.get("comments", 0),
            "url": pr["html_url"],
        })

    return json.dumps({"repo": f"{owner}/{repo}", "count": len(prs), "pull_requests": prs}, indent=2)


@tool
def check_ci_status(owner: str, repo: str) -> str:
    """Check the latest CI/CD workflow run status for a GitHub repository.

    Args:
        owner: The GitHub repository owner (e.g. "strands-agents")
        repo: The repository name (e.g. "sdk-python")

    Returns:
        JSON string with the 10 most recent workflow runs: name, status,
        conclusion, branch, created date, and HTML URL.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs"
    params = {"per_page": 10, "sort": "created", "direction": "desc"}
    resp = requests.get(url, headers=_gh_headers(), params=params, timeout=30)
    resp.raise_for_status()

    runs = []
    for run in resp.json().get("workflow_runs", []):
        runs.append({
            "id": run["id"],
            "name": run["name"],
            "status": run["status"],
            "conclusion": run.get("conclusion"),
            "branch": run["head_branch"],
            "created_at": run["created_at"],
            "html_url": run["html_url"],
        })

    return json.dumps({"repo": f"{owner}/{repo}", "count": len(runs), "workflow_runs": runs}, indent=2)


@tool
def list_stale_issues(owner: str, repo: str, days_stale: int = 14) -> str:
    """List open issues that have had no activity for a specified number of days.

    Args:
        owner: The GitHub repository owner (e.g. "strands-agents")
        repo: The repository name (e.g. "sdk-python")
        days_stale: Number of days with no activity to consider an issue stale (default: 14)

    Returns:
        JSON string with stale issues: number, title, author, created date,
        last updated date, days since last activity, labels, and URL.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_stale)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
    params = {
        "state": "open",
        "since": cutoff_str,
        "per_page": 50,
        "sort": "updated",
        "direction": "asc",  # oldest-updated first = most stale
    }
    resp = requests.get(url, headers=_gh_headers(), params=params, timeout=30)
    resp.raise_for_status()

    stale_issues = []
    now = datetime.now(timezone.utc)
    for issue in resp.json():
        if "pull_request" in issue:
            continue  # skip PRs — we have a separate tool for those
        updated = _parse_iso(issue.get("updated_at"))
        if updated and updated < cutoff:
            days_inactive = (now - updated).days
            stale_issues.append({
                "number": issue["number"],
                "title": issue["title"],
                "author": issue["user"]["login"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "days_inactive": days_inactive,
                "labels": [l["name"] for l in issue.get("labels", [])],
                "url": issue["html_url"],
            })

    return json.dumps({
        "repo": f"{owner}/{repo}",
        "stale_threshold_days": days_stale,
        "count": len(stale_issues),
        "stale_issues": stale_issues,
    }, indent=2)


@tool
def get_review_comments(owner: str, repo: str, pr_number: int) -> str:
    """Get review comments and review states for a specific pull request.

    Args:
        owner: The GitHub repository owner (e.g. "strands-agents")
        repo: The repository name (e.g. "sdk-python")
        pr_number: The pull request number

    Returns:
        JSON string with review states (approved, changes_requested, commented)
        and review comment details: author, body, path, and line.
    """
    # Get review states
    reviews_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    resp = requests.get(reviews_url, headers=_gh_headers(), timeout=30)
    resp.raise_for_status()

    reviews = []
    for rev in resp.json():
        reviews.append({
            "user": rev["user"]["login"],
            "state": rev["state"],  # APPROVED, CHANGES_REQUESTED, COMMENTED, etc.
            "submitted_at": rev.get("submitted_at"),
            "body": rev.get("body", "")[:500],
        })

    # Get review comments (inline code comments)
    comments_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    resp2 = requests.get(comments_url, headers=_gh_headers(), timeout=30)
    resp2.raise_for_status()

    comments = []
    for c in resp2.json():
        comments.append({
            "author": c["user"]["login"],
            "path": c.get("path", ""),
            "line": c.get("line", c.get("original_line")),
            "body": c.get("body", "")[:500],
            "created_at": c["created_at"],
        })

    return json.dumps({
        "repo": f"{owner}/{repo}",
        "pr_number": pr_number,
        "reviews": reviews,
        "review_comments": comments,
    }, indent=2)


@tool
def send_slack_summary(webhook_url: str, summary: str) -> str:
    """Send a summary message to a Slack channel via incoming webhook.

    Args:
        webhook_url: The Slack incoming webhook URL
        summary: The summary text to send (markdown supported)

    Returns:
        Confirmation message indicating success or failure.
    """
    payload = {"text": f"📊 *Repo Health Monitor*\n\n{summary}"}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        return f"Slack notification sent successfully (HTTP {resp.status_code})"
    except Exception as e:
        return f"Failed to send Slack notification: {e}"


@tool
def generate_health_report(owner: str, repo: str) -> str:
    """Generate a comprehensive health report for a GitHub repository.

    Combines PR status, CI status, and stale issues into a single
    human-readable report suitable for posting to Slack or saving.

    Args:
        owner: The GitHub repository owner (e.g. "strands-agents")
        repo: The repository name (e.g. "sdk-python")

    Returns:
        A formatted markdown health report string.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Gather data using the GitHub API directly (internal calls)
    report_parts = [f"# 📊 Repo Health Report: {owner}/{repo}", f"_Generated: {now_str}_", ""]

    # PRs
    try:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
        params = {"state": "open", "per_page": 50, "sort": "updated", "direction": "desc"}
        resp = requests.get(url, headers=_gh_headers(), params=params, timeout=30)
        resp.raise_for_status()
        prs = resp.json()

        report_parts.append(f"## 🔄 Open Pull Requests ({len(prs)})")
        if not prs:
            report_parts.append("_No open pull requests._")
        else:
            now = datetime.now(timezone.utc)
            for pr in prs[:10]:
                updated = _parse_iso(pr["updated_at"])
                days = (now - updated).days if updated else "?"
                draft_tag = " [DRAFT]" if pr["draft"] else ""
                report_parts.append(
                    f"- **#{pr['number']}**{draft_tag} {pr['title']} "
                    f"— by @{pr['user']['login']} — updated {days}d ago "
                    f"({pr.get('review_comments', 0)} review comments)"
                )
        report_parts.append("")
    except Exception as e:
        report_parts.append(f"## 🔄 Open Pull Requests\n_Error: {e}_\n")

    # CI
    try:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs"
        params = {"per_page": 5, "sort": "created", "direction": "desc"}
        resp = requests.get(url, headers=_gh_headers(), params=params, timeout=30)
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])

        report_parts.append(f"## 🔧 Recent CI Runs (last 5)")
        if not runs:
            report_parts.append("_No CI runs found._")
        else:
            for run in runs[:5]:
                status_icon = {
                    "success": "✅", "failure": "❌", "cancelled": "🚫",
                    "in_progress": "🔄", "queued": "⏳",
                }.get(run.get("conclusion", run.get("status")), "❓")
                report_parts.append(
                    f"- {status_icon} **{run['name']}** on `{run['head_branch']}` "
                    f"— {run.get('conclusion', run['status'])} "
                    f"— {run['created_at'][:10]}"
                )
        report_parts.append("")
    except Exception as e:
        report_parts.append(f"## 🔧 Recent CI Runs\n_Error: {e}_\n")

    # Stale issues
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
        params = {"state": "open", "since": cutoff_str, "per_page": 50, "sort": "updated", "direction": "asc"}
        resp = requests.get(url, headers=_gh_headers(), params=params, timeout=30)
        resp.raise_for_status()

        stale = []
        for issue in resp.json():
            if "pull_request" in issue:
                continue
            updated = _parse_iso(issue.get("updated_at"))
            if updated and updated < cutoff:
                days = (datetime.now(timezone.utc) - updated).days
                stale.append({"number": issue["number"], "title": issue["title"], "days": days})

        report_parts.append(f"## 🐛 Stale Issues (>14 days inactive: {len(stale)})")
        if not stale:
            report_parts.append("_No stale issues. 🎉_")
        else:
            for s in stale[:10]:
                report_parts.append(f"- **#{s['number']}** {s['title']} — _{s['days']}d inactive_")
        report_parts.append("")
    except Exception as e:
        report_parts.append(f"## 🐛 Stale Issues\n_Error: {e}_\n")

    # Summary
    report_parts.append("---")
    report_parts.append(f"_Report by Repo Health Monitor — powered by Strands Agents SDK_")

    return "\n".join(report_parts)