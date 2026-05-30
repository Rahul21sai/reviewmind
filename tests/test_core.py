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


if __name__ == "__main__":
    unittest.main()
