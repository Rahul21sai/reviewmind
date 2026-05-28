"""SQLite and PostgreSQL persistence helpers for ReviewMind feedback, reviews, and styles."""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any

DB_PATH = "reviewmind.db"
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# Try to import psycopg2 for Postgres support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


def is_postgres() -> bool:
    """Check if PostgreSQL configuration is active and the driver is installed."""
    return bool(
        DATABASE_URL
        and HAS_POSTGRES
        and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"))
    )


class DBContext:
    """Unified database context manager handling SQLite and PostgreSQL transaction safety."""

    def __init__(self) -> None:
        self.conn = None
        self.cursor = None
        self.last_inserted_id = None

    def __enter__(self) -> DBContext:
        try:
            if is_postgres():
                self.conn = psycopg2.connect(DATABASE_URL)
                self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            else:
                self.conn = sqlite3.connect(DB_PATH)
                self.conn.row_factory = sqlite3.Row
                self.cursor = self.conn.cursor()
        except Exception:
            logger.exception("Failed to connect to database")
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.conn:
            try:
                if exc_type is not None:
                    self.conn.rollback()
                else:
                    self.conn.commit()
            except Exception:
                logger.exception("Database transaction commit/rollback failed")
            finally:
                if self.cursor:
                    self.cursor.close()
                self.conn.close()

    def execute(self, query: str, params: tuple = ()) -> DBContext:
        """Execute a query, adapting placeholders and syntax dynamic modifications."""
        self.last_inserted_id = None
        if is_postgres():
            # Translate SQL dialects
            query = query.replace("?", "%s")
            query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            query = query.replace("strftime('%Y-W%W', timestamp)", "to_char(timestamp, 'IYYY-\"W\"IW')")
            query = query.replace("DATETIME", "TIMESTAMP")
            
            stripped_query = query.strip()
            if stripped_query.upper().startswith("INSERT INTO"):
                # Append RETURNING id to insert query to fetch generated serial key
                query = stripped_query.rstrip(";") + " RETURNING id"
                self.cursor.execute(query, params)
                row = self.cursor.fetchone()
                if row:
                    self.last_inserted_id = row.get("id") or list(row.values())[0]
            else:
                self.cursor.execute(query, params)
        else:
            self.cursor.execute(query, params)
            stripped_query = query.strip()
            if stripped_query.upper().startswith("INSERT INTO"):
                self.last_inserted_id = self.cursor.lastrowid
        return self

    def fetchall(self) -> list[Any]:
        if self.cursor:
            return self.cursor.fetchall()
        return []

    def fetchone(self) -> Any:
        if self.cursor:
            return self.cursor.fetchone()
        return None


def init_db() -> None:
    """Create ReviewMind database tables if they do not already exist."""
    try:
        with DBContext() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    suggestion_text TEXT NOT NULL,
                    code_context TEXT,
                    accepted INTEGER NOT NULL DEFAULT 0,
                    fix_pr_merged INTEGER NOT NULL DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    diff TEXT NOT NULL,
                    suggestions TEXT NOT NULL,
                    fix_branch TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS style_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo TEXT NOT NULL,
                    style_md TEXT NOT NULL,
                    acceptance_rate REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
    except Exception:
        logger.exception("Failed to initialize database")


def save_feedback(
    repo: str,
    pr_number: int,
    suggestion_text: str,
    code_context: str | None = None,
    accepted: int = 0,
) -> int | None:
    """Insert one feedback row and return its new id."""
    try:
        with DBContext() as db:
            db.execute(
                """
                INSERT INTO feedback (
                    repo, pr_number, suggestion_text, code_context, accepted
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (repo, pr_number, suggestion_text, code_context, int(bool(accepted))),
            )
            return db.last_inserted_id
    except Exception:
        logger.exception("Failed to save feedback for %s PR #%s", repo, pr_number)
        return None


def get_accepted_patterns(repo: str, limit: int = 10) -> list[str]:
    """Return recent accepted suggestion texts for a repository."""
    try:
        with DBContext() as db:
            rows = db.execute(
                """
                SELECT suggestion_text
                FROM feedback
                WHERE repo = ? AND accepted = 1
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (repo, limit),
            ).fetchall()
            return [str(row["suggestion_text"]) for row in rows]
    except Exception:
        logger.exception("Failed to fetch accepted patterns for %s", repo)
        return []


def get_rejected_patterns(repo: str, limit: int = 5) -> list[str]:
    """Return recent rejected suggestion texts for a repository."""
    try:
        with DBContext() as db:
            rows = db.execute(
                """
                SELECT suggestion_text
                FROM feedback
                WHERE repo = ? AND accepted = 0
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (repo, limit),
            ).fetchall()
            return [str(row["suggestion_text"]) for row in rows]
    except Exception:
        logger.exception("Failed to fetch rejected patterns for %s", repo)
        return []


def save_review(
    repo: str,
    pr_number: int,
    diff: str,
    suggestions_json: str,
    fix_branch: str | None = None,
) -> int | None:
    """Save a completed review and return its new id."""
    try:
        with DBContext() as db:
            db.execute(
                """
                INSERT INTO reviews (
                    repo, pr_number, diff, suggestions, fix_branch
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (repo, pr_number, diff, suggestions_json, fix_branch),
            )
            return db.last_inserted_id
    except Exception:
        logger.exception("Failed to save review for %s PR #%s", repo, pr_number)
        return None


def get_acceptance_rate(repo: str) -> float:
    """Return accepted feedback divided by total feedback for a repository."""
    try:
        with DBContext() as db:
            row = db.execute(
                """
                SELECT COUNT(*) AS total, SUM(accepted) AS accepted_count
                FROM feedback
                WHERE repo = ?
                """,
                (repo,),
            ).fetchone()
            if not row:
                return 0.0
            total = int(row["total"] or 0)
            if total == 0:
                return 0.0
            accepted_count = int(row["accepted_count"] or 0)
            return accepted_count / total
    except Exception:
        logger.exception("Failed to calculate acceptance rate for %s", repo)
        return 0.0


def get_all_feedback(repo: str) -> list[dict[str, Any]]:
    """Return all feedback rows for a repository as dictionaries."""
    try:
        with DBContext() as db:
            rows = db.execute(
                """
                SELECT *
                FROM feedback
                WHERE repo = ?
                ORDER BY timestamp DESC, id DESC
                """,
                (repo,),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to fetch all feedback for %s", repo)
        return []


def get_feedback_count(repo: str) -> int:
    """Return the total feedback count for a repository."""
    try:
        with DBContext() as db:
            row = db.execute(
                "SELECT COUNT(*) AS total FROM feedback WHERE repo = ?",
                (repo,),
            ).fetchone()
            if not row:
                return 0
            return int(row["total"] or 0)
    except Exception:
        logger.exception("Failed to count feedback for %s", repo)
        return 0


def get_weekly_acceptance_rates(repo: str) -> list[dict[str, Any]]:
    """Return weekly feedback acceptance rates for a repository."""
    try:
        with DBContext() as db:
            rows = db.execute(
                """
                SELECT
                    strftime('%Y-W%W', timestamp) AS week,
                    COUNT(*) AS total,
                    SUM(accepted) AS accepted_count
                FROM feedback
                WHERE repo = ?
                GROUP BY week
                ORDER BY week ASC
                """,
                (repo,),
            ).fetchall()
            return [
                {
                    "week": str(row["week"]),
                    "rate": (int(row["accepted_count"] or 0) / int(row["total"])),
                }
                for row in rows
                if row and int(row["total"] or 0) > 0
            ]
    except Exception:
        logger.exception("Failed to fetch weekly acceptance rates for %s", repo)
        return []


def mark_pr_feedback(repo: str, pr_number: int, accepted: bool) -> bool:
    """Mark all feedback for a PR as accepted or rejected."""
    try:
        accepted_value = 1 if accepted else 0
        fix_merged_value = 1 if accepted else 0
        with DBContext() as db:
            db.execute(
                """
                UPDATE feedback
                SET accepted = ?, fix_pr_merged = ?
                WHERE repo = ? AND pr_number = ?
                """,
                (accepted_value, fix_merged_value, repo, pr_number),
            )
            return True
    except Exception:
        logger.exception("Failed to mark feedback for %s PR #%s", repo, pr_number)
        return False


def save_style_snapshot(
    repo: str,
    style_md: str,
    acceptance_rate: float | None = None,
) -> int | None:
    """Save a generated TEAM_STYLE.md snapshot and return its new id."""
    try:
        with DBContext() as db:
            db.execute(
                """
                INSERT INTO style_snapshots (repo, style_md, acceptance_rate)
                VALUES (?, ?, ?)
                """,
                (repo, style_md, acceptance_rate),
            )
            return db.last_inserted_id
    except Exception:
        logger.exception("Failed to save style snapshot for %s", repo)
        return None


def get_latest_style_snapshot(repo: str) -> dict[str, Any] | None:
    """Return the latest style snapshot for a repository if one exists."""
    try:
        with DBContext() as db:
            row = db.execute(
                """
                SELECT *
                FROM style_snapshots
                WHERE repo = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (repo,),
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        logger.exception("Failed to fetch latest style snapshot for %s", repo)
        return None


def get_review_count(repo: str) -> int:
    """Return the number of stored reviews for a repository."""
    try:
        with DBContext() as db:
            row = db.execute(
                "SELECT COUNT(*) AS total FROM reviews WHERE repo = ?",
                (repo,),
            ).fetchone()
            if not row:
                return 0
            return int(row["total"] or 0)
    except Exception:
        logger.exception("Failed to count reviews for %s", repo)
        return 0


def get_fix_pr_opened_count(repo: str) -> int:
    """Return the number of reviews with fix branches for a repository."""
    try:
        with DBContext() as db:
            row = db.execute(
                """
                SELECT COUNT(*) AS total
                FROM reviews
                WHERE repo = ? AND fix_branch IS NOT NULL AND fix_branch != ''
                """,
                (repo,),
            ).fetchone()
            if not row:
                return 0
            return int(row["total"] or 0)
    except Exception:
        logger.exception("Failed to count fix PRs opened for %s", repo)
        return 0


def get_fix_pr_merged_count(repo: str) -> int:
    """Return the number of merged fix PR feedback rows for a repository."""
    try:
        with DBContext() as db:
            row = db.execute(
                """
                SELECT COUNT(*) AS total
                FROM feedback
                WHERE repo = ? AND fix_pr_merged = 1
                """,
                (repo,),
            ).fetchone()
            if not row:
                return 0
            return int(row["total"] or 0)
    except Exception:
        logger.exception("Failed to count merged fix PRs for %s", repo)
        return 0
