import os
import tempfile
import unittest
from pathlib import Path

from audit_log import append_appeal, append_submission, find_latest_submission, read_log
from detection import analyze_stylometrics, classify_with_groq
from labels import HIGH_CONFIDENCE_AI_LABEL, HIGH_CONFIDENCE_HUMAN_LABEL, UNCERTAIN_LABEL, label_for_attribution
from scoring import attribution_for_score, combine_scores


class ScoringTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(attribution_for_score(0.2), "likely_human")
        self.assertEqual(attribution_for_score(0.5), "uncertain")
        self.assertEqual(attribution_for_score(0.9), "likely_ai")

    def test_fallback_is_logged_without_changing_score(self):
        normal = combine_scores(0.9, 0.9)
        fallback = combine_scores(0.9, 0.9, {"groq": "fallback"})
        self.assertEqual(fallback["confidence"], normal["confidence"])
        self.assertTrue(fallback["notes"])

    def test_labels_are_exact(self):
        self.assertEqual(label_for_attribution("likely_ai"), HIGH_CONFIDENCE_AI_LABEL)
        self.assertEqual(label_for_attribution("likely_human"), HIGH_CONFIDENCE_HUMAN_LABEL)
        self.assertEqual(label_for_attribution("uncertain"), UNCERTAIN_LABEL)


class DetectionTests(unittest.TestCase):
    def test_stylometrics_return_metrics(self):
        result = analyze_stylometrics(
            "Artificial intelligence represents a transformative paradigm shift. "
            "Furthermore, organizations must collaborate responsibly."
        )
        self.assertIn("ai_score", result)
        self.assertIn("sentence_length_variance", result["metrics"])
        self.assertIn("type_token_ratio", result["metrics"])
        self.assertIn("punctuation_density", result["metrics"])

    def test_groq_fallback_without_key(self):
        old_key = os.environ.pop("GROQ_API_KEY", None)
        try:
            result = classify_with_groq("ok so i wrote this myself and honestly it is messy")
        finally:
            if old_key:
                os.environ["GROQ_API_KEY"] = old_key
        self.assertEqual(result["status"], "fallback")
        self.assertGreaterEqual(result["ai_score"], 0)
        self.assertLessEqual(result["ai_score"], 1)


class AuditLogTests(unittest.TestCase):
    def test_submission_and_appeal_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.jsonl"
            submission = append_submission(
                {
                    "content_id": "content-1",
                    "creator_id": "creator-1",
                    "attribution": "uncertain",
                    "confidence": 0.51,
                    "label": "label",
                    "groq_score": 0.5,
                    "stylometric_score": 0.52,
                    "stylometric_metrics": {"word_count": 10},
                    "status": "classified",
                },
                path=path,
            )
            self.assertEqual(submission["event_type"], "submission")
            found = find_latest_submission("content-1", path=path)
            self.assertEqual(found["creator_id"], "creator-1")
            appeal = append_appeal("content-1", "I wrote this.", found, path=path)
            self.assertEqual(appeal["status"], "under_review")
            self.assertEqual(len(read_log(path=path)), 2)


if __name__ == "__main__":
    unittest.main()
