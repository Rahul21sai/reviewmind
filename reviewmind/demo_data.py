"""Realistic demo data seeder for ReviewMind hackathon demos."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from reviewmind.db import save_feedback, save_review, save_style_snapshot

logger = logging.getLogger(__name__)

# Realistic accepted patterns (things a real team would approve)
ACCEPTED_PATTERNS = [
    ("Use descriptive variable names instead of single letters", "x = get_data()", 1),
    ("Add specific exception handling around API calls", "except Exception: pass", 2),
    ("Use parameterised queries to prevent SQL injection", "query = 'SELECT * FROM users WHERE id=' + id", 3),
    ("Replace magic numbers with named constants", "if retries > 3:", 4),
    ("Add input validation before database writes", "db.insert(user_input)", 5),
    ("Use context managers for file and database operations", "conn = sqlite3.connect(db)", 6),
    ("Return structured JSON errors from API endpoints", "return 'error', 500", 7),
    ("Add type hints to public function signatures", "def process(data):", 8),
    ("Use f-strings instead of string concatenation", "msg = 'Hello ' + name", 9),
    ("Prefer pathlib.Path over os.path for file operations", "os.path.join(base, file)", 10),
    ("Add guard clauses to reduce nesting depth", "if valid: if ready: process()", 11),
    ("Use enumerate instead of manual index tracking", "i = 0; for item in list: i += 1", 12),
    ("Extract repeated logic into helper functions", "# duplicate block in 3 places", 13),
    ("Add logging before and after critical operations", "db.execute(dangerous_migration)", 14),
]

# Realistic rejected patterns (things a team would find unhelpful)
REJECTED_PATTERNS = [
    ("Add an inline comment explaining this line", "result = process(data)", 15),
    ("Consider adding more documentation to this module", "# utils.py", 16),
    ("This function could be broken into smaller pieces", "def handle_request():", 17),
    ("Add type hints to every local variable", "count = 0", 18),
    ("Consider using a design pattern here", "if action == 'create': ...", 19),
    ("Add unit tests for this helper function", "def _format_name(n):", 20),
]


def seed_learning_data(repo: str) -> dict:
    """Seed 20 realistic feedback entries for a repository demo.

    Returns a summary dict with counts and status.
    """
    accepted_count = 0
    rejected_count = 0
    base_time = datetime.now() - timedelta(days=7)

    try:
        # Seed accepted patterns
        for i, (suggestion, context, pr_num) in enumerate(ACCEPTED_PATTERNS):
            save_feedback(
                repo=repo,
                pr_number=pr_num,
                suggestion_text=suggestion,
                code_context=context,
                accepted=1,
            )
            # Save a corresponding review record
            save_review(
                repo=repo,
                pr_number=pr_num,
                diff=f"diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -{pr_num},3 +{pr_num},3 @@\n-{context}\n+# fixed by ReviewMind",
                suggestions_json=f'[{{"line": {pr_num}, "issue": "{suggestion}", "suggestion": "Apply fix", "fix_code": "# fixed"}}]',
                fix_branch=f"reviewmind/fix-pr-{pr_num}" if random.random() > 0.3 else None,
            )
            accepted_count += 1

        # Seed rejected patterns
        for i, (suggestion, context, pr_num) in enumerate(REJECTED_PATTERNS):
            save_feedback(
                repo=repo,
                pr_number=pr_num,
                suggestion_text=suggestion,
                code_context=context,
                accepted=0,
            )
            save_review(
                repo=repo,
                pr_number=pr_num,
                diff=f"diff --git a/utils.py b/utils.py\n--- a/utils.py\n+++ b/utils.py\n@@ -{pr_num},2 +{pr_num},2 @@\n-{context}\n+# unchanged",
                suggestions_json=f'[{{"line": {pr_num}, "issue": "{suggestion}", "suggestion": "Consider change", "fix_code": "# suggestion"}}]',
            )
            rejected_count += 1

        logger.info(
            "Seeded %d accepted + %d rejected feedbacks for %s",
            accepted_count,
            rejected_count,
            repo,
        )
        return {
            "accepted": accepted_count,
            "rejected": rejected_count,
            "total": accepted_count + rejected_count,
            "repo": repo,
        }
    except Exception:
        logger.exception("Failed to seed learning data for %s", repo)
        return {
            "accepted": accepted_count,
            "rejected": rejected_count,
            "total": accepted_count + rejected_count,
            "repo": repo,
            "error": "Partial seed — check logs",
        }
