"""AI review generation and GitHub comment formatting."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from reviewmind.config import MAX_SUGGESTIONS, MODEL, OPENAI_API_KEY
from reviewmind.db import get_accepted_patterns, get_rejected_patterns, save_feedback


logger = logging.getLogger(__name__)


def _strip_json_fences(content: str) -> str:
    """Remove markdown code fences from a model response."""
    stripped = content.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _build_pattern_section(title: str, patterns: list[str]) -> str:
    """Build a prompt section from learned team patterns."""
    if not patterns:
        return ""
    lines = [title]
    lines.extend(f"- {pattern}" for pattern in patterns)
    return "\n".join(lines)


def _normalize_suggestions(raw_suggestions: Any) -> list[dict[str, Any]]:
    """Validate model suggestions into the expected list-of-dicts shape."""
    if not isinstance(raw_suggestions, list):
        return []

    suggestions: list[dict[str, Any]] = []
    for item in raw_suggestions[:MAX_SUGGESTIONS]:
        if not isinstance(item, dict):
            continue
        try:
            suggestion = {
                "line": int(item.get("line", 0)),
                "issue": str(item.get("issue", "")).strip(),
                "suggestion": str(item.get("suggestion", "")).strip(),
                "fix_code": str(item.get("fix_code", "")).strip(),
            }
        except (TypeError, ValueError):
            logger.exception("Invalid suggestion payload: %s", item)
            continue
        if suggestion["issue"] and suggestion["suggestion"]:
            suggestions.append(suggestion)
    return suggestions


def generate_review(
    diff: str,
    repo: str,
    github_token: str = "",
    pr_number: int = 0,
    save_feedback_rows: bool = True,
) -> list[dict[str, Any]]:
    """Generate AI review suggestions for a PR diff."""
    del github_token
    try:
        accepted_patterns = get_accepted_patterns(repo, limit=10)
        rejected_patterns = get_rejected_patterns(repo, limit=5)

        accepted_section = _build_pattern_section(
            "This team previously ACCEPTED these patterns (match this style):",
            accepted_patterns,
        )
        rejected_section = _build_pattern_section(
            "This team previously REJECTED these patterns\n(never suggest these):",
            rejected_patterns,
        )

        system_prompt = f"""You are a code reviewer for a software team.
Review the PR diff and give 3-5 specific suggestions.

{accepted_section}

{rejected_section}

Rules:
- Max 5 suggestions
- Each suggestion: issue in one sentence, fix in one sentence
- fix_code must be the actual corrected code (5 lines max)
- Focus on: correctness, naming, error handling
- Respond ONLY as valid JSON array, no markdown, no preamble

Format exactly:
[
  {{
    "line": 12,
    "issue": "Variable x is ambiguous",
    "suggestion": "Rename x to user_count",
    "fix_code": "user_count = get_users()"
  }}
]"""

        if not OPENAI_API_KEY or OPENAI_API_KEY.lower() == "mock":
            logger.info("OpenAI API key is not configured; returning no suggestions")
            return []

        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": diff},
            ],
        )
        content = response.choices[0].message.content or "[]"
        parsed = json.loads(_strip_json_fences(content))
        suggestions = _normalize_suggestions(parsed)

        if save_feedback_rows:
            for suggestion in suggestions:
                save_feedback(repo, pr_number, suggestion["issue"])

        return suggestions
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        logger.exception("Failed to parse review suggestions for %s", repo)
        return []
    except Exception:
        logger.exception("Failed to generate review for %s", repo)
        return []


def format_suggestions_as_comment(suggestions: list[dict[str, Any]]) -> str:
    """Format review suggestions as a GitHub markdown comment."""
    header = """## ReviewMind suggestions
*This bot learns from your feedback.
Merge the fix PR to mark suggestions accepted.
Comment 'reviewmind accept' or 'reviewmind reject' to give feedback manually.*

---"""

    blocks = [header]
    for index, suggestion in enumerate(suggestions, start=1):
        line = suggestion.get("line", "?")
        issue = suggestion.get("issue", "")
        fix = suggestion.get("suggestion", "")
        fix_code = suggestion.get("fix_code", "")
        blocks.append(
            f"""**Suggestion {index} - Line {line}**
Issue: {issue}
Fix: {fix}
```python
{fix_code}
```"""
        )
    return "\n\n".join(blocks)
