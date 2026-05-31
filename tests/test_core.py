"""Basic tests for ReviewMind core functionality."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

# Override DB_PATH before importing modules
_test_db = os.path.join(tempfile.gettempdir(), "reviewmind_test.db")
os.environ.setdefault("OPENAI_API_KEY", "mock")

import reviewmind.db as db

db.DB_PATH = _test_db


class TestDatabase(unittest.TestCase):
    """Tests for database persistence helpers."""

    def setUp(self) -> None:
        """Recreate a clean test database before each test."""
        if os.path.exists(_test_db):
            os.remove(_test_db)
        db.init_db()

    def tearDown(self) -> None:
        if os.path.exists(_test_db):
            os.remove(_test_db)

    def test_init_db_creates_tables(self) -> None:
        """init_db should create feedback, reviews, and style_snapshots tables."""
        conn = sqlite3.connect(_test_db)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        self.assertIn("feedback", tables)
        self.assertIn("reviews", tables)
        self.assertIn("style_snapshots", tables)

    def test_save_and_get_feedback(self) -> None:
        """save_feedback + get_accepted_patterns should round-trip correctly."""
        db.save_feedback("test/repo", 1, "Use descriptive names", accepted=1)
        db.save_feedback("test/repo", 2, "Add generic comment", accepted=0)

        accepted = db.get_accepted_patterns("test/repo")
        self.assertIn("Use descriptive names", accepted)

        rejected = db.get_rejected_patterns("test/repo")
        self.assertIn("Add generic comment", rejected)

    def test_acceptance_rate(self) -> None:
        """get_acceptance_rate should return correct ratio."""
        db.save_feedback("test/repo", 1, "Pattern A", accepted=1)
        db.save_feedback("test/repo", 2, "Pattern B", accepted=1)
        db.save_feedback("test/repo", 3, "Pattern C", accepted=0)

        rate = db.get_acceptance_rate("test/repo")
        self.assertAlmostEqual(rate, 2 / 3, places=4)

    def test_feedback_count(self) -> None:
        """get_feedback_count should return correct total."""
        for i in range(5):
            db.save_feedback("test/repo", i + 1, f"Suggestion {i}", accepted=1)
        self.assertEqual(db.get_feedback_count("test/repo"), 5)

    def test_get_recent_feedback(self) -> None:
        """get_recent_feedback should return limited recent rows."""
        for i in range(10):
            db.save_feedback("test/repo", i + 1, f"Suggestion {i}", accepted=i % 2)
        recent = db.get_recent_feedback("test/repo", limit=3)
        self.assertEqual(len(recent), 3)
        self.assertIn("suggestion_text", recent[0])

    def test_mark_pr_feedback(self) -> None:
        """mark_pr_feedback should update acceptance status."""
        db.save_feedback("test/repo", 1, "Test", accepted=0)
        db.mark_pr_feedback("test/repo", 1, accepted=True)
        accepted = db.get_accepted_patterns("test/repo")
        self.assertIn("Test", accepted)

    def test_save_review(self) -> None:
        """save_review should store and count reviews correctly."""
        db.save_review("test/repo", 1, "diff content", '[]', fix_branch="fix-1")
        self.assertEqual(db.get_review_count("test/repo"), 1)
        self.assertEqual(db.get_fix_pr_opened_count("test/repo"), 1)


class TestReviewer(unittest.TestCase):
    """Tests for reviewer utilities."""

    def test_classify_risk_high(self) -> None:
        from reviewmind.reviewer import classify_risk
        self.assertEqual(classify_risk("SQL injection via string concat"), "High")
        self.assertEqual(classify_risk("Hardcoded password in config"), "High")

    def test_classify_risk_medium(self) -> None:
        from reviewmind.reviewer import classify_risk
        self.assertEqual(classify_risk("Missing input validation check"), "Medium")
        self.assertEqual(classify_risk("No null handling for response"), "Medium")

    def test_classify_risk_low(self) -> None:
        from reviewmind.reviewer import classify_risk
        self.assertEqual(classify_risk("Variable name is not descriptive"), "Low")
        self.assertEqual(classify_risk("Use f-string instead of concat"), "Low")

    def test_format_suggestions(self) -> None:
        from reviewmind.reviewer import format_suggestions_as_comment
        suggestions = [
            {"line": 1, "issue": "Test issue", "suggestion": "Fix it", "fix_code": "fixed()"}
        ]
        result = format_suggestions_as_comment(suggestions)
        self.assertIn("ReviewMind suggestions", result)
        self.assertIn("Line 1", result)
        self.assertIn("Test issue", result)

    def test_build_pattern_section_empty(self) -> None:
        from reviewmind.reviewer import _build_pattern_section
        self.assertEqual(_build_pattern_section("Title", []), "")

    def test_build_pattern_section_populated(self) -> None:
        from reviewmind.reviewer import _build_pattern_section
        result = _build_pattern_section("Title:", ["A", "B"])
        self.assertIn("Title:", result)
        self.assertIn("- A", result)
        self.assertIn("- B", result)


class TestDemoData(unittest.TestCase):
    """Tests for demo data seeder."""

    def setUp(self) -> None:
        if os.path.exists(_test_db):
            os.remove(_test_db)
        db.init_db()

    def tearDown(self) -> None:
        if os.path.exists(_test_db):
            os.remove(_test_db)

    def test_seed_creates_records(self) -> None:
        from reviewmind.demo_data import seed_learning_data
        result = seed_learning_data("test/repo")
        self.assertEqual(result["accepted"], 14)
        self.assertEqual(result["rejected"], 6)
        self.assertEqual(result["total"], 20)
        self.assertEqual(db.get_feedback_count("test/repo"), 20)


class TestAppRoutes(unittest.TestCase):
    """Tests for basic application routes and custom error handlers."""

    def setUp(self) -> None:
        from reviewmind.app import app
        from reviewmind.app import _rate_limits as app_rate_limits
        from reviewmind.dashboard import _rate_limits as dashboard_rate_limits
        app.config["TESTING"] = True
        self.client = app.test_client()
        # Reset rate limiter history to avoid cross-test contamination
        app_rate_limits.clear()
        dashboard_rate_limits.clear()

    def tearDown(self) -> None:
        from reviewmind.app import _rate_limits as app_rate_limits
        from reviewmind.dashboard import _rate_limits as dashboard_rate_limits
        app_rate_limits.clear()
        dashboard_rate_limits.clear()

    def test_landing_page(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ReviewMind", response.data)

    def test_setup_page(self) -> None:
        response = self.client.get("/setup")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Setup Status", response.data)

    def test_404_page(self) -> None:
        response = self.client.get("/invalid-page-for-test-404")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"404", response.data)
        self.assertIn(b"neural pathways", response.data)

    def test_health_check_healthy(self) -> None:
        """Health endpoint should return 200 when database is connected."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "connected")

    def test_health_check_unhealthy(self) -> None:
        """Health endpoint should return 503 when database connection fails."""
        # Force DBContext failure
        from unittest.mock import patch
        with patch("reviewmind.db.DBContext.__enter__", side_effect=Exception("DB Failure")):
            response = self.client.get("/health")
            self.assertEqual(response.status_code, 503)
            data = response.get_json()
            self.assertEqual(data["status"], "unhealthy")
            self.assertEqual(data["database"], "disconnected")

    def test_repo_validation_on_dashboard(self) -> None:
        """Dashboard should reject invalid repository names with a 404."""
        response = self.client.get("/dashboard?repo=invalid-format")
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/dashboard?repo=valid-owner/valid-repo")
        self.assertEqual(response.status_code, 200)

    def test_input_validation_feedback_route(self) -> None:
        """Feedback route should enforce validation for repository and PR."""
        # Invalid repo format
        response = self.client.post("/feedback", json={"repo": "invalid-format", "pr_number": 1, "accepted": True})
        self.assertEqual(response.status_code, 400)

        # Invalid PR number
        response = self.client.post("/feedback", json={"repo": "owner/repo", "pr_number": 0, "accepted": True})
        self.assertEqual(response.status_code, 400)

    def test_input_validation_review_pr_route(self) -> None:
        """Review PR route should validate repo name format and PR number."""
        response = self.client.post("/review-pr", json={"repo": "invalid-format", "pr_number": 1})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/review-pr", json={"repo": "owner/repo", "pr_number": -5})
        self.assertEqual(response.status_code, 400)

    def test_input_validation_simulate_learning(self) -> None:
        """Simulate learning route should validate repo name."""
        response = self.client.post("/simulate-learning", json={"repo": "invalid-format"})
        self.assertEqual(response.status_code, 400)

    def test_input_validation_style_preview(self) -> None:
        """Style preview route should validate repo name."""
        response = self.client.post("/style-preview", json={"repo": "invalid-format"})
        self.assertEqual(response.status_code, 400)

    def test_input_validation_style_commit(self) -> None:
        """Style commit route should validate repo name."""
        response = self.client.post("/style-commit", json={"repo": "invalid-format"})
        self.assertEqual(response.status_code, 400)

    def test_input_validation_demo_review(self) -> None:
        """Demo review route should validate repo name, empty diff, and diff size limit."""
        # Empty diff
        response = self.client.post("/demo-review", json={"repo": "owner/repo", "diff": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"cannot be empty", response.data)

        # Invalid repo
        response = self.client.post("/demo-review", json={"repo": "invalid-format", "diff": "some diff"})
        self.assertEqual(response.status_code, 400)

        # Giant diff
        giant_diff = "a" * 1000005
        response = self.client.post("/demo-review", json={"repo": "owner/repo", "diff": giant_diff})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"exceeds size limit", response.data)

    def test_rate_limiting_demo_review(self) -> None:
        """Rate limiter should trigger 429 Too Many Requests after limit exceeded."""
        # The limit on /demo-review is 10 requests per 60 seconds
        for _ in range(10):
            response = self.client.post("/demo-review", json={"repo": "owner/repo", "diff": "dummy diff"})
            self.assertEqual(response.status_code, 200)

        # 11th request should be rate limited
        response = self.client.post("/demo-review", json={"repo": "owner/repo", "diff": "dummy diff"})
        self.assertEqual(response.status_code, 429)
        data = response.get_json()
        self.assertIn("Too many requests", data["error"])


class TestOpenAIRetryLogic(unittest.TestCase):
    """Tests for the retry_openai exponential backoff decorator."""

    def test_retry_openai_success_after_retries(self) -> None:
        from reviewmind.reviewer import retry_openai

        calls = []
        @retry_openai(max_retries=3, initial_delay=0.001, backoff_factor=2.0)
        def dummy_func():
            calls.append(1)
            if len(calls) < 3:
                raise Exception("Transient rate_limit error")
            return "success"

        result = dummy_func()
        self.assertEqual(result, "success")
        self.assertEqual(len(calls), 3)

    def test_retry_openai_non_transient_failure(self) -> None:
        from reviewmind.reviewer import retry_openai

        calls = []
        @retry_openai(max_retries=3, initial_delay=0.001, backoff_factor=2.0)
        def dummy_func():
            calls.append(1)
            raise Exception("Fatal syntax error")

        with self.assertRaises(Exception) as ctx:
            dummy_func()
        self.assertIn("Fatal syntax error", str(ctx.exception))
        self.assertEqual(len(calls), 1)


class TestDatabaseConnectionPool(unittest.TestCase):
    """Tests for PostgreSQL ThreadedConnectionPool integration."""

    def test_is_postgres_disabled_by_default(self) -> None:
        self.assertFalse(db.is_postgres())
        self.assertIsNone(db.get_pg_pool())

    def test_postgres_pool_initialization(self) -> None:
        from unittest.mock import MagicMock

        old_url = db.DATABASE_URL
        old_has = db.HAS_POSTGRES
        old_pool_instance = db._pg_pool

        db.DATABASE_URL = "postgresql://user:pass@localhost:5432/dbname"
        db.HAS_POSTGRES = True
        db._pg_pool = None

        mock_pool_cls = MagicMock()
        mock_pool_instance = MagicMock()
        mock_pool_cls.return_value = mock_pool_instance

        import reviewmind.db as db_mod
        original_pool_cls = getattr(db_mod, "ThreadedConnectionPool", None)
        db_mod.ThreadedConnectionPool = mock_pool_cls

        try:
            pool = db.get_pg_pool()
            self.assertEqual(pool, mock_pool_instance)
            mock_pool_cls.assert_called_once_with(1, 20, dsn=db.DATABASE_URL)
        finally:
            db.DATABASE_URL = old_url
            db.HAS_POSTGRES = old_has
            db._pg_pool = old_pool_instance
            if original_pool_cls:
                db_mod.ThreadedConnectionPool = original_pool_cls
            else:
                delattr(db_mod, "ThreadedConnectionPool")

    def test_db_context_uses_postgres_pool(self) -> None:
        from unittest.mock import MagicMock

        old_url = db.DATABASE_URL
        old_has = db.HAS_POSTGRES
        old_pool_instance = db._pg_pool

        db.DATABASE_URL = "postgresql://user:pass@localhost:5432/dbname"
        db.HAS_POSTGRES = True

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        db._pg_pool = mock_pool

        try:
            with db.DBContext() as ctx:
                self.assertEqual(ctx.conn, mock_conn)
                self.assertEqual(ctx.cursor, mock_cursor)
                ctx.execute("INSERT INTO feedback (repo) VALUES (?)", ("test/repo",))

            mock_pool.getconn.assert_called_once()
            mock_conn.cursor.assert_called_once()
            # Verify translation of ? to %s and RETURNING id
            mock_cursor.execute.assert_called_once_with(
                "INSERT INTO feedback (repo) VALUES (%s) RETURNING id",
                ("test/repo",)
            )
            # Verify putconn was called to release the connection back to the pool
            mock_pool.putconn.assert_called_once_with(mock_conn)
        finally:
            db.DATABASE_URL = old_url
            db.HAS_POSTGRES = old_has
            db._pg_pool = old_pool_instance


if __name__ == "__main__":
    unittest.main()
