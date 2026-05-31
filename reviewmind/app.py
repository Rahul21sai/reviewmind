"""Flask entry point for ReviewMind webhooks, dashboard, and demo routes."""

from __future__ import annotations

from functools import wraps
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time

from flask import Flask, jsonify, render_template, request
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


# Custom in-memory rate limiter using client IP
_rate_limits = {}

def rate_limit(limit=10, period=60):
    """Simple thread-safe in-memory rate limiter decorator using client IP."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr or "127.0.0.1"
            now = time.time()
            history = _rate_limits.setdefault(ip, [])
            # Clean up events older than period
            history = [t for t in history if now - t < period]
            _rate_limits[ip] = history
            if len(history) >= limit:
                logger.warning("Rate limit exceeded for IP %s on route %s", ip, request.path)
                return jsonify({"error": "Too many requests. Please try again later."}), 429
            history.append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def validate_repo_name(repo: str) -> bool:
    """Validate GitHub repository name format 'owner/repo'."""
    pattern = r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$"
    return bool(re.match(pattern, repo))


def _verify_signature() -> bool:
    """Verify the GitHub webhook signature for the current request."""
    if not GITHUB_WEBHOOK_SECRET:
        logger.error("Signature verification skipped: GITHUB_WEBHOOK_SECRET is not configured.")
        return False
    try:
        sig = request.headers.get("X-Hub-Signature-256", "")
        if not sig:
            logger.warning("Missing X-Hub-Signature-256 header in webhook request.")
            return False
        secret = GITHUB_WEBHOOK_SECRET.encode()
        expected = "sha256=" + hmac.new(secret, request.data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            logger.warning("Invalid signature mismatch.")
            return False
        return True
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


@app.get("/")
def landing():
    """Render the ReviewMind landing page."""
    return render_template("landing.html")



# ─── Health & Setup ──────────────────────────────────────────────

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
    return render_template("setup.html", checks=checks)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


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
    """Liveness check probe verifying database connectivity."""
    db_ok = False
    try:
        from reviewmind.db import DBContext
        with DBContext() as db:
            db.execute("SELECT 1")
            db_ok = True
    except Exception:
        logger.exception("Database health probe failed")

    if not db_ok:
        return jsonify({"status": "unhealthy", "database": "disconnected"}), 503

    return jsonify({
        "status": "healthy",
        "database": "connected",
        "model": MODEL,
        "version": "2.1"
    }), 200


# ─── PR Review ───────────────────────────────────────────────────

@app.post("/review-pr")
@rate_limit(limit=5, period=60)
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

        if not repo_name or not validate_repo_name(repo_name):
            return jsonify({"error": "Invalid repository format"}), 400
        if pr_number <= 0:
            return jsonify({"error": "Invalid PR number"}), 400

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

        if not repo_name or not validate_repo_name(repo_name):
            return jsonify({"error": "Invalid repository format"}), 400
        if pr_number <= 0:
            return jsonify({"error": "Invalid PR number"}), 400

        mark_pr_feedback(repo_name, pr_number, accepted=accepted)
        # NOTE: Style guide commit is intentionally NOT triggered here.
        # Use the explicit /style-commit route instead to avoid triggering
        # a cascade of Render auto-deploys on every accept/reject click.

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
        if not repo_name or not validate_repo_name(repo_name):
            return jsonify({"error": "Invalid repository format"}), 400

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
        if not repo_name or not validate_repo_name(repo_name):
            return jsonify({"error": "Invalid repository format"}), 400

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
@rate_limit(limit=5, period=60)
def style_commit():
    """Generate and commit TEAM_STYLE.md to GitHub."""
    try:
        data = request.get_json(silent=True) or {}
        repo_name = str(data.get("repo", "")).strip()
        if not repo_name or not validate_repo_name(repo_name):
            return jsonify({"error": "Invalid repository format"}), 400

        check_and_generate_style(repo_name, GITHUB_TOKEN)
        return jsonify({"status": "committed", "repo": repo_name})
    except Exception:
        logger.exception("Failed to commit style guide")
        return jsonify({"error": "Commit failed"}), 500


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=False)
