"""Automated GitHub fix PR generation for ReviewMind suggestions."""

from __future__ import annotations

import logging
import re
from typing import Any

from github import Github

from reviewmind.config import FIX_BRANCH_PREFIX


logger = logging.getLogger(__name__)


def _extract_filenames(diff: str) -> list[str]:
    """Extract changed filenames from a unified Git diff."""
    filenames: list[str] = []
    for line in diff.splitlines():
        if line.startswith("diff --git a/"):
            match = re.match(r"diff --git a/.+ b/(.+)$", line)
            if match:
                filenames.append(match.group(1).strip())
    return filenames


def _apply_suggestion_to_text(text: str, suggestion: dict[str, Any]) -> str | None:
    """Apply a simple line-based suggestion to file text when possible."""
    fix_code = str(suggestion.get("fix_code", "")).strip()
    if not fix_code:
        return None

    lines = text.splitlines()
    try:
        line_number = int(suggestion.get("line", 0))
    except (TypeError, ValueError):
        line_number = 0

    if 1 <= line_number <= len(lines):
        new_lines = lines[:]
        replacement = fix_code.splitlines()
        new_lines[line_number - 1 : line_number] = replacement
        new_text = "\n".join(new_lines)
        if text.endswith("\n"):
            new_text += "\n"
        return new_text if new_text != text else None

    return None


def _build_pr_body(pr_number: int, suggestions: list[dict[str, Any]]) -> str:
    """Build the markdown body for an automated fix PR."""
    blocks = [
        f"## ReviewMind automated fixes for PR #{pr_number}",
        "",
        "The following changes have been applied automatically:",
        "",
    ]
    for suggestion in suggestions:
        blocks.append(f"### {suggestion.get('issue', 'Suggested fix')}")
        blocks.append("**Fix applied:**")
        blocks.append("```python")
        blocks.append(str(suggestion.get("fix_code", "")).strip())
        blocks.append("```")
        blocks.append("---")
        blocks.append("")
    blocks.append(
        "*Merge this PR -> teaches ReviewMind these patterns are correct for your team.*"
    )
    blocks.append(
        "*Close without merging -> teaches ReviewMind to avoid these suggestions.*"
    )
    return "\n".join(blocks)


def create_fix_pr(
    repo_name: str,
    pr_number: int,
    suggestions: list[dict[str, Any]],
    diff: str,
    github_token: str,
) -> str | None:
    """Create a GitHub PR containing simple automated fixes."""
    try:
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        original_pr = repo.get_pull(pr_number)
        base_branch = original_pr.base.ref
        base_sha = repo.get_branch(base_branch).commit.sha
    except Exception:
        logger.exception("Failed to load original PR %s#%s", repo_name, pr_number)
        return None

    fix_branch = f"{FIX_BRANCH_PREFIX}{pr_number}"
    try:
        repo.create_git_ref(ref=f"refs/heads/{fix_branch}", sha=base_sha)
    except Exception:
        logger.exception("Failed to create fix branch %s", fix_branch)
        return None

    filenames = _extract_filenames(diff)
    if not filenames:
        logger.warning("No filenames found in diff for %s PR #%s", repo_name, pr_number)

    for suggestion in suggestions:
        filepath = str(suggestion.get("file") or (filenames[0] if filenames else ""))
        if not filepath:
            logger.warning("Skipping suggestion without a target file")
            continue
        try:
            file_content = repo.get_contents(filepath, ref=base_branch)
            if isinstance(file_content, list):
                logger.warning("Skipping directory path %s", filepath)
                continue
            current_text = file_content.decoded_content.decode()
            new_text = _apply_suggestion_to_text(current_text, suggestion)
            if new_text is None:
                logger.warning("Could not locate suggestion target in %s", filepath)
                continue
            repo.update_file(
                path=filepath,
                message=f"ReviewMind: {str(suggestion.get('issue', 'fix'))[:60]}",
                content=new_text,
                sha=file_content.sha,
                branch=fix_branch,
            )
        except Exception:
            logger.exception("Failed to apply suggestion to %s", filepath)
            continue

    try:
        fix_pr = repo.create_pull(
            title=f"ReviewMind: fixes for PR #{pr_number}",
            body=_build_pr_body(pr_number, suggestions),
            head=fix_branch,
            base=base_branch,
        )
        original_pr.create_issue_comment(
            f"""🤖 **ReviewMind** opened a fix PR with changes applied:
{fix_pr.html_url}

✅ **Merge it** -> I'll learn these are correct for your team
❌ **Close it** -> I'll learn to avoid these suggestions

*Your feedback makes me smarter with every review.*"""
        )
        return str(fix_pr.html_url)
    except Exception:
        logger.exception("Failed to create or announce fix PR for %s PR #%s", repo_name, pr_number)
        return None
