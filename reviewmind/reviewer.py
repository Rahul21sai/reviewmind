"""AI review generation using OpenAI Structured Outputs and GitHub comment formatting."""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from reviewmind.config import MAX_SUGGESTIONS, MODEL, OPENAI_API_KEY
from reviewmind.db import get_accepted_patterns, get_rejected_patterns, save_feedback


logger = logging.getLogger(__name__)


class Suggestion(BaseModel):
    """Pydantic model representing a single code review suggestion."""
    line: int = Field(description="The 1-indexed line number in the diff where the issue occurs.")
    issue: str = Field(description="One-sentence description of the code issue.")
    suggestion: str = Field(description="One-sentence action plan/suggestion to fix the issue.")
    fix_code: str = Field(description="The corrected snippet of code (max 5 lines).")


class SuggestionList(BaseModel):
    """Pydantic schema for structured OpenAI output."""
    suggestions: list[Suggestion] = Field(
        description="A list of specific review suggestions for the pull request."
    )


def _build_pattern_section(title: str, patterns: list[str]) -> str:
    """Build a prompt section from learned team patterns."""
    if not patterns:
        return ""
    lines = [title]
    lines.extend(f"- {pattern}" for pattern in patterns)
    return "\n".join(lines)


# Keywords used to classify suggestion risk level
_HIGH_RISK_KEYWORDS = {
    "security", "injection", "exception", "crash", "data loss", "auth",
    "secret", "password", "credential", "vulnerability", "sql injection",
    "xss", "csrf", "privilege", "overflow", "leak",
}
_MEDIUM_RISK_KEYWORDS = {
    "error handling", "validation", "edge case", "null", "missing check",
    "undefined", "unhandled", "timeout", "race condition", "concurrency",
    "type error", "assertion", "boundary",
}


def classify_risk(text: str) -> str:
    """Classify a suggestion's risk level based on keyword matching.

    Returns 'High', 'Medium', or 'Low'.
    """
    lower = text.lower()
    if any(kw in lower for kw in _HIGH_RISK_KEYWORDS):
        return "High"
    if any(kw in lower for kw in _MEDIUM_RISK_KEYWORDS):
        return "Medium"
    return "Low"


def generate_review(
    diff: str,
    repo: str,
    github_token: str = "",
    pr_number: int = 0,
    save_feedback_rows: bool = True,
) -> list[dict[str, Any]]:
    """Generate AI review suggestions for a PR diff using Structured Outputs."""
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

        system_prompt = f"""You are an expert code reviewer for a software team.
Review the pull request diff and give 3 to {MAX_SUGGESTIONS} specific suggestions.

{accepted_section}

{rejected_section}

Rules:
- Max {MAX_SUGGESTIONS} suggestions.
- Each suggestion: identify the issue in one concise sentence, and state the fix in one concise sentence.
- fix_code must contain only the direct code replacement (max 5 lines).
- Focus on correctness, code naming conventions, error handling, and performance improvements.
"""

        if not OPENAI_API_KEY or OPENAI_API_KEY.lower() == "mock":
            logger.info("OpenAI API key is not configured; returning no suggestions")
            return []

        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Call the beta chat completions parse API for guaranteed schema matching
        response = client.beta.chat.completions.parse(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": diff},
            ],
            response_format=SuggestionList,
        )
        
        parsed_output = response.choices[0].message.parsed
        if not parsed_output or not parsed_output.suggestions:
            logger.warning("No suggestions successfully parsed from OpenAI response")
            return []

        suggestions: list[dict[str, Any]] = []
        for item in parsed_output.suggestions[:MAX_SUGGESTIONS]:
            issue_text = item.issue.strip()
            suggestions.append({
                "line": item.line,
                "issue": issue_text,
                "suggestion": item.suggestion.strip(),
                "fix_code": item.fix_code.strip(),
                "risk": classify_risk(issue_text),
            })

        if save_feedback_rows:
            for suggestion in suggestions:
                save_feedback(repo, pr_number, suggestion["issue"])

        return suggestions
    except Exception:
        logger.exception("Failed to generate structured review for %s", repo)
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
