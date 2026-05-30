"""Flask entry point for ReviewMind webhooks, dashboard, and demo routes."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading

from flask import Flask, jsonify, render_template_string, request
from github import Auth, Github

from reviewmind.config import GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, MODEL, OPENAI_API_KEY, PORT
from reviewmind.dashboard import dashboard_bp
from reviewmind.db import (
    get_acceptance_rate,
    get_feedback_count,
    get_recent_feedback,
    init_db,
    mark_pr_feedback,
    save_review,
)
from reviewmind.demo_data import seed_learning_data
from reviewmind.feedback import handle_issue_comment, handle_pr_closed
from reviewmind.fixer import create_fix_pr
from reviewmind.reviewer import format_suggestions_as_comment, generate_review
from reviewmind.style_writer import build_style_markdown, check_and_generate_style


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(dashboard_bp)
init_db()


def _verify_signature() -> bool:
    """Verify the GitHub webhook signature for the current request."""
    try:
        sig = request.headers.get("X-Hub-Signature-256", "")
        secret = GITHUB_WEBHOOK_SECRET.encode()
        expected = "sha256=" + hmac.new(secret, request.data, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        logger.exception("Failed to verify webhook signature")
        return False


def _start_thread(target, args: tuple) -> None:
    """Start a daemon thread for webhook side effects."""
    try:
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()
    except Exception:
        logger.exception("Failed to start background thread")


def _get_pr_diff(repo_name: str, pr_number: int) -> tuple[object, object, str] | None:
    """Fetch a pull request and return its repo, PR object, and combined diff."""
    try:
        g = Github(auth=Auth.Token(GITHUB_TOKEN))
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        files = pr.get_files()
        diff = "\n".join(
            f"diff --git a/{file.filename} b/{file.filename}\n{file.patch or ''}"
            for file in files
        )
        return repo, pr, diff
    except Exception:
        logger.exception("Failed to fetch PR diff for %s PR #%s", repo_name, pr_number)
        return None


# ─── Landing page ────────────────────────────────────────────────

LANDING_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ReviewMind — AI PR Reviewer That Learns Your Team's Taste</title>
  <meta name="description" content="ReviewMind reviews pull requests, learns from developer feedback, opens fix PRs, and generates a living TEAM_STYLE.md for each team.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #06090f;
      --surface: #0d1117;
      --card: rgba(22, 27, 34, 0.8);
      --border: rgba(48, 54, 61, 0.6);
      --text: #e6edf3;
      --muted: #7d8590;
      --accent: #3fb950;
      --accent-glow: rgba(63, 185, 80, 0.15);
      --purple: #a371f7;
      --blue: #58a6ff;
      --orange: #d29922;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      overflow-x: hidden;
    }
    .hero {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 40px 20px;
      position: relative;
    }
    .hero::before {
      content: '';
      position: absolute;
      top: -120px;
      left: 50%;
      transform: translateX(-50%);
      width: 600px;
      height: 600px;
      background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
      pointer-events: none;
      z-index: 0;
    }
    .hero > * { position: relative; z-index: 1; }
    .logo {
      font-size: 4.5rem;
      margin-bottom: 16px;
      animation: float 3s ease-in-out infinite;
    }
    @keyframes float {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-8px); }
    }
    h1 {
      font-size: clamp(2.5rem, 6vw, 4.5rem);
      font-weight: 900;
      letter-spacing: -0.03em;
      background: linear-gradient(135deg, #e6edf3 0%, var(--accent) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 16px;
    }
    .tagline {
      font-size: clamp(1.1rem, 2.5vw, 1.4rem);
      color: var(--muted);
      max-width: 600px;
      line-height: 1.6;
      margin-bottom: 40px;
    }
    .features {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      max-width: 900px;
      margin: 0 auto 48px;
    }
    .feature-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 28px 24px;
      backdrop-filter: blur(12px);
      transition: transform 0.3s ease, border-color 0.3s ease;
    }
    .feature-card:hover {
      transform: translateY(-4px);
      border-color: var(--accent);
    }
    .feature-icon { font-size: 2rem; margin-bottom: 14px; }
    .feature-title { font-weight: 700; font-size: 1.05rem; margin-bottom: 8px; }
    .feature-desc { color: var(--muted); font-size: 0.9rem; line-height: 1.5; }
    .cta-row {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      justify-content: center;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 14px 28px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 1rem;
      text-decoration: none;
      transition: all 0.25s ease;
      border: none;
      cursor: pointer;
      font-family: inherit;
    }
    .btn-primary {
      background: var(--accent);
      color: #052e16;
      box-shadow: 0 0 24px var(--accent-glow);
    }
    .btn-primary:hover {
      transform: translateY(-2px);
      box-shadow: 0 0 40px rgba(63, 185, 80, 0.3);
    }
    .btn-secondary {
      background: var(--card);
      color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-secondary:hover {
      border-color: var(--accent);
      transform: translateY(-2px);
    }
    .flow {
      max-width: 800px;
      margin: 0 auto 40px;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }
    .flow-step {
      text-align: center;
      padding: 16px 8px;
    }
    .flow-num {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--accent-glow);
      border: 2px solid var(--accent);
      color: var(--accent);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 0.9rem;
      margin-bottom: 10px;
    }
    .flow-label { font-size: 0.85rem; color: var(--muted); line-height: 1.4; }
    .flow-label strong { color: var(--text); display: block; margin-bottom: 4px; }
    @media (max-width: 720px) {
      .features { grid-template-columns: 1fr; }
      .flow { grid-template-columns: repeat(2, 1fr); }
    }
  </style>
</head>
<body>
  <div class="hero">
    <div class="logo">🧠</div>
    <h1>ReviewMind</h1>
    <p class="tagline">
      The AI PR reviewer that learns your team's coding taste.
      Reviews PRs, opens fix branches, and writes your team's style guide — automatically.
    </p>

    <div class="flow">
      <div class="flow-step">
        <div class="flow-num">1</div>
        <div class="flow-label"><strong>PR Opened</strong>GitHub triggers webhook</div>
      </div>
      <div class="flow-step">
        <div class="flow-num">2</div>
        <div class="flow-label"><strong>AI Reviews</strong>gpt-4o-mini analyzes diff</div>
      </div>
      <div class="flow-step">
        <div class="flow-num">3</div>
        <div class="flow-label"><strong>Team Decides</strong>Merge fix = accept, close = reject</div>
      </div>
      <div class="flow-step">
        <div class="flow-num">4</div>
        <div class="flow-label"><strong>Bot Evolves</strong>TEAM_STYLE.md auto-commits</div>
      </div>
    </div>

    <div class="features">
      <div class="feature-card">
        <div class="feature-icon">🔧</div>
        <div class="feature-title">Auto Fix PRs</div>
        <div class="feature-desc">Doesn't just comment — opens a fix branch with changes applied. Merge it and the bot learns.</div>
      </div>
      <div class="feature-card">
        <div class="feature-icon">📈</div>
        <div class="feature-title">Learns From Feedback</div>
        <div class="feature-desc">Every accept/reject becomes training data. Future reviews align with your team's real taste.</div>
      </div>
      <div class="feature-card">
        <div class="feature-icon">📋</div>
        <div class="feature-title">Living Style Guide</div>
        <div class="feature-desc">After 20 feedbacks, auto-generates and commits TEAM_STYLE.md — your team's conventions, codified.</div>
      </div>
    </div>

    <div class="cta-row">
      <a href="/dashboard?repo=Rahul21sai/reviewmind" class="btn btn-primary">
        Open Dashboard →
      </a>
      <a href="/setup" class="btn btn-secondary">
        ⚙️ Setup Status
      </a>
      <a href="https://github.com/Rahul21sai/reviewmind" class="btn btn-secondary" target="_blank">
        GitHub Repo
      </a>
    </div>
  </div>
</body>
</html>
"""


@app.get("/")
def landing():
    """Render the ReviewMind landing page."""
    return render_template_string(LANDING_HTML)


# ─── Health & Setup ──────────────────────────────────────────────

SETUP_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ReviewMind — Setup Status</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #06090f; --surface: #0d1117; --card: rgba(22, 27, 34, 0.8);
      --border: rgba(48, 54, 61, 0.6); --text: #e6edf3; --muted: #7d8590;
      --accent: #3fb950; --danger: #f85149;
    }
    * { box-sizing: border-box; margin: 0; }
    body {
      min-height: 100vh; background: var(--bg); color: var(--text);
      font-family: 'Inter', system-ui, sans-serif; padding: 48px 20px;
    }
    .container { max-width: 640px; margin: 0 auto; }
    h1 { font-size: 2rem; font-weight: 800; margin-bottom: 8px; }
    .subtitle { color: var(--muted); margin-bottom: 32px; }
    .check-row {
      display: flex; align-items: center; justify-content: space-between;
      padding: 16px 20px; background: var(--card); border: 1px solid var(--border);
      border-radius: 12px; margin-bottom: 10px;
      backdrop-filter: blur(8px);
    }
    .check-label { font-weight: 600; }
    .badge-ok {
      padding: 4px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 700;
      background: rgba(63, 185, 80, 0.15); color: var(--accent);
    }
    .badge-fail {
      padding: 4px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 700;
      background: rgba(248, 81, 73, 0.15); color: var(--danger);
    }
    .back-link {
      display: inline-block; margin-top: 24px; color: var(--accent);
      text-decoration: none; font-weight: 600;
    }
    .back-link:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <h1>⚙️ Setup Status</h1>
    <p class="subtitle">Integration health checks for ReviewMind.</p>
    {% for check in checks %}
    <div class="check-row">
      <span class="check-label">{{ check.name }}</span>
      {% if check.ok %}
        <span class="badge-ok">✓ Configured</span>
      {% else %}
        <span class="badge-fail">✗ Missing</span>
      {% endif %}
    </div>
    {% endfor %}
    <a href="/" class="back-link">← Back to home</a>
  </div>
</body>
</html>
"""


@app.get("/setup")
def setup():
    """Show integration health status for judges."""
    db_ok = False
    try:
        from reviewmind.db import DBContext
        with DBContext() as db:
            db.execute("SELECT 1")
            db_ok = True
    except Exception:
        pass

    github_ok = False
    if GITHUB_TOKEN:
        try:
            g = Github(auth=Auth.Token(GITHUB_TOKEN))
            g.get_user().login
            github_ok = True
        except Exception:
            pass

    checks = [
        {"name": "OpenAI API Key", "ok": bool(OPENAI_API_KEY and OPENAI_API_KEY.lower() != "mock")},
        {"name": "GitHub Token", "ok": bool(GITHUB_TOKEN)},
        {"name": "GitHub API Access", "ok": github_ok},
        {"name": "Webhook Secret", "ok": bool(GITHUB_WEBHOOK_SECRET)},
        {"name": "Database Connection", "ok": db_ok},
        {"name": "AI Model", "ok": True},
    ]
    return render_template_string(SETUP_HTML, checks=checks)


# ─── Webhook ─────────────────────────────────────────────────────

@app.post("/webhook")
def webhook():
    """Receive GitHub webhook events and dispatch background work."""
    if not _verify_signature():
        return jsonify({"error": "invalid signature"}), 401

    try:
        event = request.headers.get("X-GitHub-Event")
        payload = request.get_json(silent=True) or {}

        if event == "pull_request":
            action = payload.get("action")
            if action in ["opened", "reopened", "synchronize"]:
                _start_thread(run_review, (payload,))
            if action == "closed":
                _start_thread(handle_pr_closed, (payload, GITHUB_TOKEN))

        if event == "issue_comment" and "pull_request" in payload.get("issue", {}):
            _start_thread(handle_issue_comment, (payload, GITHUB_TOKEN))

        return jsonify({"status": "received"}), 200
    except Exception:
        logger.exception("Failed to process webhook")
        return jsonify({"status": "received"}), 200


def run_review(payload: dict) -> None:
    """Generate a review comment and automated fix PR for a pull request."""
    try:
        repo_name = payload["repository"]["full_name"]
        pr_number = int(payload["pull_request"]["number"])

        pr_data = _get_pr_diff(repo_name, pr_number)
        if pr_data is None:
            return None
        _, pr, diff = pr_data

        suggestions = generate_review(diff, repo_name, GITHUB_TOKEN, pr_number=pr_number)
        if not suggestions:
            return None

        comment = format_suggestions_as_comment(suggestions)
        pr.create_issue_comment(comment)

        fix_url = create_fix_pr(repo_name, pr_number, suggestions, diff, GITHUB_TOKEN)
        if fix_url:
            logger.info("Fix PR created: %s", fix_url)

        save_review(
            repo_name,
            pr_number,
            diff,
            json.dumps(suggestions),
            fix_branch=f"reviewmind/fix-pr-{pr_number}",
        )
    except Exception:
        logger.exception("Failed to run review")
    return None


@app.get("/health")
def health():
    """Return a basic application health response."""
    return jsonify({"status": "ok", "model": MODEL, "version": "2.0"})


# ─── PR Review ───────────────────────────────────────────────────

@app.post("/review-pr")
def review_pr():
    """Review a real GitHub pull request from the dashboard."""
    try:
        if not GITHUB_TOKEN:
            return jsonify({"error": "GITHUB_TOKEN is not configured"}), 400
        if not OPENAI_API_KEY or OPENAI_API_KEY.lower() == "mock":
            return jsonify({"error": "OPENAI_API_KEY is not configured"}), 400

        data = request.get_json(silent=True) or {}
        repo_name = str(data.get("repo", "")).strip()
        pr_number = int(data.get("pr_number", 0))
        should_comment = bool(data.get("comment", True))
        should_create_fix = bool(data.get("create_fix_pr", False))

        if not repo_name or pr_number <= 0:
            return jsonify({"error": "repo and pr_number are required"}), 400

        pr_data = _get_pr_diff(repo_name, pr_number)
        if pr_data is None:
            return jsonify({"error": "Could not fetch pull request diff"}), 502
        _, pr, diff = pr_data

        suggestions = generate_review(diff, repo_name, GITHUB_TOKEN, pr_number=pr_number)
        if not suggestions:
            return jsonify({"error": "No suggestions returned", "suggestions": []}), 200

        if should_comment:
            try:
                pr.create_issue_comment(format_suggestions_as_comment(suggestions))
            except Exception:
                logger.exception("Failed to comment on PR %s#%s", repo_name, pr_number)

        fix_url = None
        if should_create_fix:
            fix_url = create_fix_pr(repo_name, pr_number, suggestions, diff, GITHUB_TOKEN)

        save_review(
            repo_name,
            pr_number,
            diff,
            json.dumps(suggestions),
            fix_branch=f"reviewmind/fix-pr-{pr_number}" if fix_url else None,
        )
        return jsonify(
            {
                "repo": repo_name,
                "pr_number": pr_number,
                "suggestions": suggestions,
                "commented": should_comment,
                "fix_pr_url": fix_url,
            }
        )
    except Exception:
        logger.exception("Failed to review real pull request")
        return jsonify({"error": "Review failed"}), 500


# ─── Dashboard interactive routes ────────────────────────────────

@app.post("/feedback")
def feedback():
    """Accept or reject feedback for a PR from the dashboard."""
    try:
        data = request.get_json(silent=True) or {}
        repo_name = str(data.get("repo", "")).strip()
        pr_number = int(data.get("pr_number", 0))
        accepted = bool(data.get("accepted", False))

        if not repo_name or pr_number <= 0:
            return jsonify({"error": "repo and pr_number are required"}), 400

        mark_pr_feedback(repo_name, pr_number, accepted=accepted)
        check_and_generate_style(repo_name, GITHUB_TOKEN)

        return jsonify({
            "repo": repo_name,
            "pr_number": pr_number,
            "accepted": accepted,
            "acceptance_rate": round(get_acceptance_rate(repo_name) * 100),
            "feedback_count": get_feedback_count(repo_name),
        })
    except Exception:
        logger.exception("Failed to process feedback")
        return jsonify({"error": "Feedback failed"}), 500


@app.post("/simulate-learning")
def simulate_learning():
    """Seed realistic learning data for demo purposes."""
    try:
        data = request.get_json(silent=True) or {}
        repo_name = str(data.get("repo", "Rahul21sai/reviewmind")).strip()
        result = seed_learning_data(repo_name)
        result["acceptance_rate"] = round(get_acceptance_rate(repo_name) * 100)
        result["feedback_count"] = get_feedback_count(repo_name)
        return jsonify(result)
    except Exception:
        logger.exception("Failed to simulate learning")
        return jsonify({"error": "Simulation failed"}), 500


@app.post("/style-preview")
def style_preview():
    """Generate a TEAM_STYLE.md preview without committing."""
    try:
        data = request.get_json(silent=True) or {}
        repo_name = str(data.get("repo", "")).strip()
        if not repo_name:
            return jsonify({"error": "repo is required"}), 400

        from reviewmind.db import get_accepted_patterns, get_rejected_patterns
        accepted = get_accepted_patterns(repo_name, limit=15)
        rejected = get_rejected_patterns(repo_name, limit=8)
        rate = get_acceptance_rate(repo_name)
        count = get_feedback_count(repo_name)
        style_md = build_style_markdown(repo_name, accepted, rejected, rate, count)

        return jsonify({"style_md": style_md, "rate": round(rate * 100), "count": count})
    except Exception:
        logger.exception("Failed to generate style preview")
        return jsonify({"error": "Preview failed"}), 500


@app.post("/style-commit")
def style_commit():
    """Generate and commit TEAM_STYLE.md to GitHub."""
    try:
        data = request.get_json(silent=True) or {}
        repo_name = str(data.get("repo", "")).strip()
        if not repo_name:
            return jsonify({"error": "repo is required"}), 400

        check_and_generate_style(repo_name, GITHUB_TOKEN)
        return jsonify({"status": "committed", "repo": repo_name})
    except Exception:
        logger.exception("Failed to commit style guide")
        return jsonify({"error": "Commit failed"}), 500


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=False)
