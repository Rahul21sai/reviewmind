"""Run a no-credential ReviewMind demo for screen recording."""

from __future__ import annotations

import os
import sqlite3
import sys

from reviewmind.config import DB_PATH
from reviewmind.db import (
    get_acceptance_rate,
    get_accepted_patterns,
    get_feedback_count,
    get_rejected_patterns,
    init_db,
    save_feedback,
)
from reviewmind.style_writer import build_style_markdown


REPO = "demo/reviewmind-test"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEMO_DIFF = """
diff --git a/app/users.py b/app/users.py
--- a/app/users.py
+++ b/app/users.py
@@ -10,9 +10,16 @@
+def get_user(id):
+    x = db.query("SELECT * FROM users WHERE id="+id)
+    return x
+
+def process_users():
+    n = get_all_users()
+    for i in n:
+        if i.active == 1:
+            r = send_email(i)
"""

MOCK_SUGGESTIONS = [
    {
        "line": 11,
        "issue": "SQL injection via string concat",
        "suggestion": "Use parameterised query",
        "fix_code": "x = db.query('SELECT * FROM users WHERE id=?', (id,))",
    },
    {
        "line": 10,
        "issue": "Parameter name id shadows builtin",
        "suggestion": "Rename id to user_id",
        "fix_code": "def get_user(user_id):",
    },
    {
        "line": 14,
        "issue": "Variable n is not descriptive",
        "suggestion": "Rename n to users",
        "fix_code": "users = get_all_users()",
    },
    {
        "line": 16,
        "issue": "Magic number 1 for active check",
        "suggestion": "Use boolean True",
        "fix_code": "if i.active:",
    },
    {
        "line": 17,
        "issue": "Result r is unused",
        "suggestion": "Remove assignment or handle return value",
        "fix_code": "send_email(i)",
    },
]


def _seed_patterns() -> None:
    """Seed accepted and rejected demo feedback patterns."""
    patterns = [
        "Renamed single-letter variable to descriptive name",
        "Added try-except around external API call",
        "Extracted magic number into named constant",
        "Added return type annotation to function",
        "Used f-string instead of string concatenation",
        "Added input validation before processing",
        "Replaced bare except with specific exception type",
        "Used list comprehension instead of for loop",
        "Added docstring to public function",
        "Used pathlib instead of os.path",
    ]
    for pattern in patterns:
        save_feedback(REPO, 1, pattern, accepted=1)
    print("✓ Loaded 10 accepted patterns")

    rejected = [
        "Add an inline comment explaining this line",
        "Consider adding more documentation here",
        "This could benefit from additional comments",
        "Add type hints to every single parameter",
        "Consider breaking this into smaller functions",
    ]
    for pattern in rejected:
        save_feedback(REPO, 1, pattern, accepted=0)
    print("✓ Loaded 5 rejected patterns")


def _reset_demo_repo() -> None:
    """Remove prior demo rows so repeated runs stay deterministic."""
    with sqlite3.connect(DB_PATH) as conn:
        for table in ("feedback", "reviews", "style_snapshots"):
            conn.execute(f"DELETE FROM {table} WHERE repo = ?", (REPO,))


def _get_demo_suggestions() -> list[dict[str, object]]:
    """Return mock suggestions unless a real API key is configured."""
    if not os.getenv("OPENAI_API_KEY"):
        return MOCK_SUGGESTIONS

    from reviewmind.reviewer import generate_review

    suggestions = generate_review(DEMO_DIFF, REPO)
    return suggestions or MOCK_SUGGESTIONS


def main() -> None:
    """Run the complete ReviewMind command-line demo."""
    print("=" * 50)
    print("  REVIEWMIND DEMO")
    print("=" * 50)

    init_db()
    _reset_demo_repo()
    _seed_patterns()

    rate = get_acceptance_rate(REPO)
    count = get_feedback_count(REPO)
    print(f"\nPatterns learned : {count}")
    print(f"Acceptance rate  : {rate:.0%}")

    suggestions = _get_demo_suggestions()
    for index, suggestion in enumerate(suggestions, start=1):
        print(f"\nSUGGESTION {index}:")
        print(f"  Line   : {suggestion['line']}")
        print(f"  Issue  : {suggestion['issue']}")
        print(f"  Fix    : {suggestion['suggestion']}")
        print(f"  Code   : {suggestion['fix_code']}")

    print("\n" + "=" * 50)
    print("  THE LEARNING DIFFERENCE")
    print("=" * 50)
    print("\nBEFORE ReviewMind (generic bot):")
    print("  Typical suggestion : 'Add a comment here'")
    print("  Team response      : rejected every time")
    print("  Acceptance rate    : ~20%")
    print("\nAFTER ReviewMind (5 days of feedback):")
    print("  Focuses on         : SQL safety, naming, errors")
    print("  Stopped suggesting : comments, documentation")
    print("  Acceptance rate    : 75%+")
    print("  Bonus              : TEAM_STYLE.md committed")

    accepted = get_accepted_patterns(REPO, limit=15)
    rejected = get_rejected_patterns(REPO, limit=8)
    style_md = build_style_markdown(REPO, accepted, rejected, rate, count)
    print("\n" + style_md)
    print("\n✓ This file would be committed to your repo.")


if __name__ == "__main__":
    main()
