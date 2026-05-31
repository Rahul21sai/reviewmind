"""Flask dashboard blueprint with premium UI for ReviewMind."""

from __future__ import annotations

import json
import logging
import re

from flask import Blueprint, jsonify, render_template, request

from reviewmind.demo_data import seed_learning_data

from reviewmind.db import (
    get_acceptance_rate,
    get_accepted_patterns,
    get_feedback_count,
    get_fix_pr_merged_count,
    get_fix_pr_opened_count,
    get_latest_style_snapshot,
    get_recent_feedback,
    get_rejected_patterns,
    get_review_count,
    get_weekly_acceptance_rates,
)
from reviewmind.reviewer import generate_review
from functools import wraps
import time


logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


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


@dashboard_bp.get("/dashboard")
def dashboard():
    """Render the ReviewMind repository dashboard."""
    repo = request.args.get("repo", "demo/reviewmind-test").strip()
    if not repo or not validate_repo_name(repo):
        return render_template("404.html"), 404

    feedback_count = get_feedback_count(repo)

    # Auto-seed demo data on first visit so judges never see an empty dashboard
    if feedback_count == 0:
        try:
            seed_learning_data(repo)
            feedback_count = get_feedback_count(repo)
            logger.info("Auto-seeded demo data for %s", repo)
        except Exception:
            logger.exception("Failed to auto-seed demo data")

    weekly_rates = get_weekly_acceptance_rates(repo)
    style_snapshot = get_latest_style_snapshot(repo)
    recent = get_recent_feedback(repo, limit=15)
    return render_template(
        "dashboard.html",
        repo=repo,
        repo_json=json.dumps(repo),
        review_count=get_review_count(repo),
        acceptance_rate=round(get_acceptance_rate(repo) * 100),
        fix_opened=get_fix_pr_opened_count(repo),
        fix_merged=get_fix_pr_merged_count(repo),
        weekly_rates=weekly_rates,
        weekly_rates_json=json.dumps(weekly_rates),
        accepted=get_accepted_patterns(repo, limit=8),
        rejected=get_rejected_patterns(repo, limit=5),
        style_snapshot=style_snapshot,
        feedback_count=feedback_count,
        progress=min(100, int((feedback_count / 20) * 100)),
        recent_feedback=recent,
    )


@dashboard_bp.post("/demo-review")
@rate_limit(limit=10, period=60)
def demo_review():
    """Return live demo suggestions for a submitted diff."""
    try:
        data = request.get_json(silent=True) or {}
        diff = str(data.get("diff", "")).strip()
        repo = str(data.get("repo", "demo/reviewmind-test")).strip()

        if not diff:
            return jsonify({"error": "Diff content cannot be empty"}), 400
        if len(diff) > 1000000:
            return jsonify({"error": "Diff content exceeds size limit (1MB)"}), 400
        if not repo or not validate_repo_name(repo):
            return jsonify({"error": "Invalid repository format"}), 400

        return jsonify(generate_review(diff, repo, save_feedback_rows=False))
    except Exception:
        logger.exception("Demo review failed")
        return jsonify([]), 200
