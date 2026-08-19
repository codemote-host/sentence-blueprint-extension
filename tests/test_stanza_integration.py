import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "local_service"))

import server  # noqa: E402


STANZA_READY = importlib.util.find_spec("stanza") is not None and Path(
    r"D:\sentence-blueprint-runtime\stanza_resources"
).exists()


@unittest.skipUnless(STANZA_READY, "需要 D 盘 Stanza 专用运行环境")
class StanzaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = server.load_config()

    def test_nested_clauses_and_shared_passive_predicate(self):
        result = server.analyze_with_stanza(
            "Because Docker controls the virtualization layer, it can be monitored and governed "
            "in ways that aren't possible with third-party backends.",
            self.config,
        )
        self.assertEqual(result["pattern"], "复合句（主句 SV）")
        self.assertEqual(result["skeleton"], "it + can be monitored and governed")
        self.assertEqual(
            [item["text"] for item in result["predicates"]],
            ["can be monitored and governed", "controls", "aren't possible"],
        )
        self.assertEqual([item["type"] for item in result["clauses"]], ["原因状语从句", "定语从句"])

    def test_multiple_sentences_are_analyzed_separately(self):
        result = server.analyze_with_stanza(
            "Docker controls the layer. Docker VMM provides a stable alternative.",
            self.config,
        )
        self.assertEqual(result["pattern"], "2 句文本")
        self.assertEqual(len(result["sentence_analyses"]), 2)

    def test_object_complement(self):
        result = server.analyze_with_stanza(
            "The teacher asked the students to review the lesson before the test.",
            self.config,
        )
        self.assertEqual(result["pattern"], "SVOC")
        self.assertEqual([item["role"] for item in result["components"]], ["S", "V", "O", "OC"])

    def test_gerund_subject_is_not_a_finite_clause(self):
        result = server.analyze_with_stanza(
            "Reading short articles every day improves your ability to find the main idea.",
            self.config,
        )
        self.assertEqual(result["pattern"], "SVO")
        self.assertEqual(result["clauses"], [])

    def test_hyphenated_modifiers_are_merged_for_teaching(self):
        result = server.analyze_with_stanza(
            "Apache Doris is a high-performance, real-time analytical database.",
            self.config,
        )
        display_items = {item["text"]: item["pos"] for item in result["word_classes"]}
        self.assertEqual(display_items["high-performance"], "复合形容词（作定语）")
        self.assertEqual(display_items["real-time"], "复合形容词（作定语）")
        self.assertNotIn("high", display_items)
        self.assertNotIn("performance", display_items)

        raw_items = {item["text"]: item["pos"] for item in result["raw_word_classes"]}
        self.assertEqual(raw_items["high"], "形容词")
        self.assertEqual(raw_items["performance"], "名词")

    def test_parallel_on_or_off_is_reconciled_without_changing_raw_stanza_pos(self):
        result = server.analyze_with_stanza(
            "The real answer is actually that every single reasoning effort change completely destroys "
            "the cache—every single one, and so does switching fast mode on or off.",
            self.config,
        )

        display_items = {item["text"]: item["pos"] for item in result["word_classes"]}
        self.assertEqual(display_items["on"], "副词")
        self.assertEqual(display_items["off"], "副词")
        self.assertNotIn("cache—every", display_items)
        self.assertIn("cache", display_items)
        self.assertIn("every", display_items)

        raw_items = {item["text"]: item["pos"] for item in result["raw_word_classes"]}
        self.assertEqual(raw_items["on"], "介词")
        self.assertEqual(raw_items["off"], "副词")
        self.assertIn(
            {"text": "on or off", "connector": "or", "category": "副词", "members": ["on", "off"],
             "explanation": "or 连接两个并列状态词；on/off 在此都作副词。"},
            result["parallel_structures"],
        )

    def test_comment_adverbs_and_independent_clauses(self):
        result = server.analyze_with_stanza(
            "Personally, I had it in mind that OpenAI's infra was better than that, and more: "
            "why not warn us when we change reasoning? "
            "Win-win for everybody, and the feature takes 15min to add. "
            "Again, I apologize and I was wrong here.",
            self.config,
        )
        self.assertEqual(result["pattern"], "3 句文本")

        first, second, third = result["sentence_analyses"]
        first_components = {(item["text"], item["label"]) for item in first["components"]}
        self.assertIn(("Personally", "评注性状语"), first_components)
        first_clause_types = {item["type"] for item in first["clauses"]}
        self.assertIn("名词性从句", first_clause_types)
        self.assertIn("时间状语从句", first_clause_types)
        self.assertIn("独立省略问句", first_clause_types)

        self.assertIn("并列主句", {item["type"] for item in second["clauses"]})
        third_components = {(item["text"], item["label"]) for item in third["components"]}
        self.assertIn(("Again", "评注性状语"), third_components)
        self.assertIn("并列主句", {item["type"] for item in third["clauses"]})


if __name__ == "__main__":
    unittest.main()
