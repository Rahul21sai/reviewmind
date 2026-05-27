"""Flask entry point for ReviewMind webhooks and dashboard."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading

from flask import Flask, jsonify, request
from github import Github

from reviewmind.config import GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, MODEL, OPENAI_API_KEY, PORT
from reviewmind.dashboard import dashboard_bp
from reviewmind.db import init_db, save_review
from reviewmind.feedback import handle_issue_comment, handle_pr_closed
from reviewmind.fixer import create_fix_pr
from reviewmind.reviewer import format_suggestions_as_comment, generate_review


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
        g = Github(GITHUB_TOKEN)
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


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=False)
