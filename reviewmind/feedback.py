"""GitHub webhook feedback processors for ReviewMind learning."""

from __future__ import annotations

import logging

from reviewmind.config import FIX_BRANCH_PREFIX
from reviewmind.db import mark_pr_feedback
from reviewmind.style_writer import check_and_generate_style


logger = logging.getLogger(__name__)


def handle_pr_closed(payload: dict, github_token: str) -> None:
    """Record feedback when a ReviewMind fix PR is closed."""
    try:
        repo_name = payload["repository"]["full_name"]
        merged = bool(payload["pull_request"]["merged"])
        branch = payload["pull_request"]["head"]["ref"]

        if branch.startswith(FIX_BRANCH_PREFIX):
            original = branch.removeprefix(FIX_BRANCH_PREFIX)
            orig_pr_num = int(original)
            mark_pr_feedback(repo_name, orig_pr_num, accepted=merged)
            logger.info(
                "Feedback recorded: fix PR merged=%s for original PR #%s",
                merged,
                orig_pr_num,
            )
            check_and_generate_style(repo_name, github_token)
    except Exception:
        logger.exception("Failed to handle pull request closed webhook")
    return None


def handle_issue_comment(payload: dict, github_token: str) -> None:
    """Record manual ReviewMind accept or reject feedback from a comment."""
    try:
        repo_name = payload["repository"]["full_name"]
        body = payload["comment"]["body"].lower().strip()
        pr_number = int(payload["issue"]["number"])

        if "reviewmind accept" in body:
            mark_pr_feedback(repo_name, pr_number, True)
            logger.info("Manual accept recorded for PR #%s", pr_number)
            check_and_generate_style(repo_name, github_token)

        if "reviewmind reject" in body:
            mark_pr_feedback(repo_name, pr_number, False)
            logger.info("Manual reject recorded for PR #%s", pr_number)
            check_and_generate_style(repo_name, github_token)
    except Exception:
        logger.exception("Failed to handle issue comment webhook")
    return None
