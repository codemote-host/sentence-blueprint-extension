import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "local_service"))

import server  # noqa: E402


class HeuristicAnalysisTests(unittest.TestCase):
    def test_object_complement_with_infinitive(self):
        result = server.analyze_heuristic(
            "The teacher asked the students to review the lesson before the test."
        )
        self.assertEqual(result["pattern"], "SVOC")
        roles = [item["role"] for item in result["components"]]
        self.assertEqual(roles, ["S", "V", "O", "OC", "Adv"])
        self.assertEqual(result["predicates"][0]["text"], "asked")
        self.assertTrue(any(item["text"] == "to review" for item in result["non_finite"]))
        self.assertEqual(result["clauses"], [])
        before = next(item for item in result["word_classes"] if item["text"] == "before")
        asked = next(item for item in result["word_classes"] if item["text"] == "asked")
        self.assertEqual(before["pos"], "介词")
        self.assertIn("有限谓语", asked["form"])

    def test_double_object(self):
        result = server.analyze_heuristic("My father bought me a new phone.")
        self.assertEqual(result["pattern"], "SVOO")
        roles = [item["role"] for item in result["components"]]
        self.assertEqual(roles, ["S", "V", "IO", "DO"])

    def test_adjective_object_complement(self):
        result = server.analyze_heuristic("The news made me excited.")
        self.assertEqual(result["pattern"], "SVOC")
        roles = [item["role"] for item in result["components"]]
        self.assertEqual(roles, ["S", "V", "O", "OC"])

    def test_gerund_subject_and_infinitive(self):
        result = server.analyze_heuristic(
            "Reading short articles every day improves your ability to find the main idea."
        )
        self.assertEqual(result["pattern"], "SVO")
        self.assertTrue(result["components"][0]["text"].startswith("Reading"))
        non_finite_texts = {item["text"] for item in result["non_finite"]}
        self.assertIn("Reading", non_finite_texts)
        self.assertIn("to find", non_finite_texts)

    def test_complete_modal_predicate(self):
        result = server.analyze_heuristic(
            "She must have forgotten the meeting because she did not reply to my message."
        )
        predicate_texts = [item["text"] for item in result["predicates"]]
        self.assertIn("must have forgotten", predicate_texts)
        self.assertIn("did not reply", predicate_texts)


if __name__ == "__main__":
    unittest.main()
