"""
Web dashboard for Repo Health Monitor.

A lightweight FastAPI app that provides:
- REST API endpoints for triggering health checks
- A simple HTML dashboard for viewing reports

Run: uvicorn web.app:app --host 0.0.0.0 --port 8000
"""

import json
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from repo_health_monitor.github_tools import (
    _gh_headers,
    _parse_iso,
    generate_health_report,
    list_open_pull_requests,
    check_ci_status,
    list_stale_issues,
)

app = FastAPI(
    title="Repo Health Monitor",
    description="AI agent that monitors GitHub repositories for health indicators",
    version="1.0.0",
)


# ─── API endpoints ────────────────────────────────────────────────────────

@app.get("/api/health/{owner}/{repo}")
async def health_check(owner: str, repo: str):
    """Get a full health report for a repository."""
    report = generate_health_report(owner, repo)
    return {"repo": f"{owner}/{repo}", "report": report, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/prs/{owner}/{repo}")
async def get_prs(owner: str, repo: str):
    """List open pull requests."""
    result = list_open_pull_requests(owner, repo)
    return json.loads(result)


@app.get("/api/ci/{owner}/{repo}")
async def get_ci(owner: str, repo: str):
    """Check CI/CD status."""
    result = check_ci_status(owner, repo)
    return json.loads(result)


@app.get("/api/stale/{owner}/{repo}")
async def get_stale(owner: str, repo: str, days: int = Query(14)):
    """List stale issues."""
    result = list_stale_issues(owner, repo, days)
    return json.loads(result)


# ─── Dashboard ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the HTML dashboard."""
    return DASHBOARD_HTML


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Repo Health Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117; color: #c9d1d9; min-height: 100vh;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 2rem; }
        h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
        .subtitle { color: #8b949e; margin-bottom: 2rem; }
        .input-group {
            display: flex; gap: 0.5rem; margin-bottom: 2rem;
        }
        input {
            flex: 1; padding: 0.75rem; border-radius: 8px; border: 1px solid #30363d;
            background: #161b22; color: #c9d1d9; font-size: 1rem;
        }
        button {
            padding: 0.75rem 1.5rem; border-radius: 8px; border: none;
            background: #238636; color: white; font-size: 1rem; cursor: pointer;
            font-weight: 600; transition: background 0.2s;
        }
        button:hover { background: #2ea043; }
        button:disabled { background: #21262d; color: #484f58; cursor: not-allowed; }
        .card {
            background: #161b22; border: 1px solid #30363d; border-radius: 12px;
            padding: 1.5rem; margin-bottom: 1rem;
        }
        .card h2 { font-size: 1.2rem; margin-bottom: 1rem; }
        .stat { display: inline-block; margin-right: 1.5rem; }
        .stat-value { font-size: 1.8rem; font-weight: 700; }
        .stat-label { font-size: 0.85rem; color: #8b949e; }
        .stat-value.warn { color: #d29922; }
        .stat-value.bad { color: #f85149; }
        .stat-value.good { color: #3fb950; }
        pre {
            white-space: pre-wrap; word-wrap: break-word; line-height: 1.6;
            font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 0.9rem;
        }
        .loading { text-align: center; padding: 2rem; color: #8b949e; }
        .badge {
            display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px;
            font-size: 0.8rem; font-weight: 600; margin-left: 0.5rem;
        }
        .badge-open { background: #1f6feb33; color: #58a6ff; }
        .badge-fail { background: #f8514933; color: #f85149; }
        .badge-ok { background: #3fb95033; color: #3fb950; }
        .powered-by {
            text-align: center; margin-top: 2rem; color: #484f58; font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Repo Health Monitor</h1>
        <p class="subtitle">Powered by Strands Agents SDK — monitors GitHub repos for PRs, CI, and stale issues</p>

        <div class="input-group">
            <input type="text" id="repoInput" placeholder="owner/repo (e.g. strands-agents/sdk-python)" value="strands-agents/sdk-python">
            <button onclick="checkRepo()" id="checkBtn">Check Health</button>
        </div>

        <div id="results"></div>

        <div class="powered-by">
            Built with <a href="https://strandsagents.com" style="color:#58a6ff">Strands Agents SDK</a> ·
            <a href="https://agentsforhumans.devpost.com" style="color:#58a6ff">Agents for Humans Hackathon</a>
        </div>
    </div>

    <script>
        async function checkRepo() {
            const input = document.getElementById('repoInput').value.trim();
            const btn = document.getElementById('checkBtn');
            const results = document.getElementById('results');

            if (!input || !input.includes('/')) {
                results.innerHTML = '<div class="card"><p>Please enter owner/repo format</p></div>';
                return;
            }

            btn.disabled = true;
            results.innerHTML = '<div class="loading">🔍 Checking repository health...</div>';

            try {
                const resp = await fetch(`/api/health/${input.split('/').join('/')}`);
                const data = await resp.json();
                results.innerHTML = `<div class="card"><pre>${data.report}</pre></div>`;
            } catch (err) {
                results.innerHTML = `<div class="card"><p style="color:#f85149">Error: ${err.message}</p></div>`;
            } finally {
                btn.disabled = false;
            }
        }

        // Auto-check on load
        window.addEventListener('load', () => checkRepo());
    </script>
</body>
</html>"""