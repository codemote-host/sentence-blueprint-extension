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
        self.assertEqual(result["semantic_skeleton"], "it can be monitored and governed")
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
        self.assertEqual(result["pattern"], "复合句（主句 SVC）")
        self.assertEqual(
            result["skeleton"],
            "The real answer + is + that every single reasoning effort change completely destroys the cache",
        )
        self.assertEqual(
            result["semantic_skeleton"],
            "The answer is that change destroys the cache; switching fast mode on or off does so",
        )
        self.assertEqual(
            [(item["text"], item["role"]) for item in result["components"]],
            [
                ("The real answer", "S"),
                ("is", "V"),
                ("actually", "Adv"),
                ("that every single reasoning effort change completely destroys the cache", "SC"),
                ("every single one", "App"),
            ],
        )
        self.assertEqual([item["text"] for item in result["predicates"]], ["is", "destroys", "does"])
        self.assertEqual(
            {item["type"] for item in result["clauses"]},
            {"表语从句", "并列省略分句"},
        )
        elliptical_clause = next(item for item in result["clauses"] if item["type"] == "并列省略分句")
        self.assertEqual(elliptical_clause["connector"], "and")
        self.assertIn("does 代替", elliptical_clause["function"])

    def test_doris_nominal_list_is_not_forced_into_an_sv_sentence(self):
        result = server.analyze_with_stanza(
            "Internal and external real-time reports, dashboards, user behavior analysis, "
            "A/B testing platforms, and log search and analysis.",
            self.config,
        )

        self.assertEqual(result["pattern"], "句子片段（名词短语）")
        self.assertEqual(result["predicates"], [])
        self.assertNotIn("V", {item["role"] for item in result["components"]})
        self.assertTrue(any("没有限定谓语" in item for item in result["warnings"]))

    def test_doris_plain_svc_keeps_the_subject_out_of_the_complement(self):
        result = server.analyze_with_stanza(
            "Apache Doris is a high-performance, real-time analytical database "
            "based on the MPP architecture.",
            self.config,
        )

        components = {item["role"]: item for item in result["components"]}
        self.assertEqual(result["pattern"], "SVC")
        self.assertEqual(components["S"]["text"], "Apache Doris")
        self.assertEqual(components["V"]["text"], "is")
        self.assertTrue(components["SC"]["text"].startswith("a high-performance"))
        self.assertNotIn("Apache Doris", components["SC"]["text"])
        self.assertEqual([item["text"] for item in result["predicates"]], ["is"])
        self.assertEqual(result["semantic_skeleton"], "Apache Doris is a database")

    def test_doris_fronted_participle_and_coordinated_main_clause_keep_both_propositions(self):
        result = server.analyze_with_stanza(
            "Known for being efficient, simple, and unified, it returns query results over massive "
            "datasets within sub-second latency, and a single system supports both high-concurrency "
            "point queries and high-throughput complex analytics.",
            self.config,
        )

        predicate_texts = {item["text"] for item in result["predicates"]}
        self.assertIn("returns", predicate_texts)
        self.assertIn("supports", predicate_texts)
        coordinated = next(item for item in result["clauses"] if item["type"] == "并列主句")
        self.assertEqual(coordinated["connector"], "and")
        self.assertIn("a single system supports", coordinated["text"])
        semantic = result["semantic_skeleton"].lower()
        self.assertIn("returns", semantic)
        self.assertIn("supports", semantic)
        self.assertIn("analytics", semantic)
        self.assertIn(";", semantic)
        known_component = next(item for item in result["components"] if item["text"].startswith("Known for"))
        self.assertEqual(known_component["role"], "Adv")
        self.assertNotEqual(known_component["label"], "评注性状语")

    def test_doris_reduced_when_clause_and_either_or_object_are_kept_distinct(self):
        result = server.analyze_with_stanza(
            "When deploying Apache Doris, you can choose either the integrated storage and compute "
            "architecture or the decoupled storage and compute architecture based on business needs.",
            self.config,
        )

        reduced = next(item for item in result["clauses"] if "状语从句（省略）" in item["type"])
        self.assertEqual(reduced["marker"].lower(), "when")
        self.assertIn("When deploying Apache Doris", reduced["text"])
        self.assertFalse(any(item.get("connector") == "or" for item in result["clauses"]))

        opening = next(item for item in result["components"] if item["text"].startswith("When deploying"))
        self.assertEqual(opening["role"], "Adv")
        self.assertNotEqual(opening["label"], "评注性状语")

        paired = next(
            item for item in result["parallel_structures"]
            if "either" in item["connector"].lower() and "or" in item["connector"].lower()
        )
        self.assertEqual(len(paired["members"]), 2)
        self.assertIn("integrated", paired["members"][0])
        self.assertIn("decoupled", paired["members"][1])
        self.assertNotIn("based on business needs", paired["text"])
        object_component = next(item for item in result["components"] if item["role"] == "O")
        self.assertNotIn("based on business needs", object_component["text"])
        basis = next(item for item in result["components"] if item["label"] == "依据状语")
        self.assertEqual(basis["text"], "based on business needs")
        self.assertEqual(basis["role"], "Adv")

        deploying = next(item for item in result["non_finite"] if item["text"].startswith("deploying"))
        self.assertEqual(deploying["form"], "doing")
        self.assertEqual(deploying["logical_subject"], "you")

    def test_doris_so_introduces_a_result_coordinate_with_its_own_subject(self):
        result = server.analyze_with_stanza(
            "Storage and compute are separated, so you can scale storage capacity and compute "
            "resources independently.",
            self.config,
        )

        result_clause = next(
            item for item in result["clauses"]
            if "并列" in item["type"] and "结果" in item["type"]
        )
        self.assertEqual(result_clause["connector"].lower(), "so")
        self.assertIn("you can scale", result_clause["text"])
        self.assertNotIn("状语从句", result_clause["type"])
        semantic = result["semantic_skeleton"].lower()
        self.assertIn("storage and compute", semantic)
        self.assertIn("separated", semantic)
        self.assertIn("you", semantic)
        self.assertIn("scale", semantic)
        self.assertIn(";", semantic)

    def test_doris_trailing_ing_series_is_separate_from_the_object(self):
        result = server.analyze_with_stanza(
            "Apache Doris uses columnar storage technology, encoding, compressing, and reading "
            "data column by column.",
            self.config,
        )

        object_component = next(item for item in result["components"] if item["role"] == "O")
        self.assertEqual(object_component["text"], "columnar storage technology")
        supplement = next(item for item in result["components"] if item["label"] == "并列非谓语状语")
        self.assertEqual(
            supplement["text"],
            "encoding, compressing, and reading data column by column",
        )
        series = next(item for item in result["non_finite"] if item["form"] == "doing 并列")
        self.assertEqual(series["text"], supplement["text"])
        self.assertEqual(series["logical_subject"], "Apache Doris")
        display_pos = {item["text"]: item["pos"] for item in result["word_classes"]}
        for word in ("encoding", "compressing", "reading"):
            self.assertTrue(display_pos[word].startswith("动词"))
        self.assertEqual(result["clauses"], [])

    def test_doris_ensuring_is_hoisted_out_of_the_prepositional_phrase(self):
        result = server.analyze_with_stanza(
            "Doris is deeply optimized for ultra-wide table scenarios (10,000+ columns), "
            "ensuring efficient storage and queries for sparse columns.",
            self.config,
        )

        self.assertEqual([item["text"] for item in result["predicates"]], ["is optimized"])
        predicate_component = next(item for item in result["components"] if item["role"] == "V")
        self.assertEqual(predicate_component["text"], "is optimized")
        self.assertIn(("deeply", "Adv"), {(item["text"], item["role"]) for item in result["components"]})
        main_pp = next(
            item for item in result["components"]
            if item["role"] == "Adv" and item["text"].startswith("for ultra-wide")
        )
        self.assertNotIn("ensuring", main_pp["text"])
        supplement = next(item for item in result["components"] if item["label"] == "非谓语状语")
        self.assertEqual(
            supplement["text"],
            "ensuring efficient storage and queries for sparse columns",
        )
        ensuring = next(item for item in result["non_finite"] if item["text"].startswith("ensuring"))
        self.assertEqual(ensuring["form"], "doing")
        self.assertEqual(ensuring["logical_subject"], "Doris")
        self.assertFalse(any("ensuring" in item["text"] for item in result["clauses"]))
        self.assertEqual(result["semantic_skeleton"], "Doris is optimized")

    def test_doris_building_supplement_keeps_its_nested_relative_clause_separate(self):
        result = server.analyze_with_stanza(
            "In the era of large models, Apache Doris deeply integrates full-text search, "
            "vector search, and AI function capabilities, building a complete AI data stack "
            "that spans data storage, retrieval, and analytics.",
            self.config,
        )

        building = next(item for item in result["non_finite"] if item["text"].startswith("building"))
        self.assertEqual(building["text"], "building a complete AI data stack")
        self.assertEqual(building["form"], "doing")
        self.assertEqual(building["function"], "伴随或结果状语")
        self.assertEqual(building["logical_subject"], "Apache Doris")

        relative = next(item for item in result["clauses"] if item["type"] == "定语从句")
        self.assertEqual(
            relative["text"],
            "that spans data storage, retrieval, and analytics",
        )
        self.assertEqual(relative["function"], "修饰先行词 stack")
        self.assertEqual(relative["marker"].lower(), "that")
        self.assertNotIn("building", {item["text"] for item in result["predicates"]})

    def test_doris_frontend_bullet_preserves_all_shared_subject_predicates(self):
        result = server.analyze_with_stanza(
            "Frontend (FE): receives requests, parses queries, manages metadata, and manages nodes",
            self.config,
        )

        subject = next(item for item in result["components"] if item["role"] == "S")
        self.assertEqual(subject["text"], "Frontend (FE)")
        self.assertEqual(
            [item["text"] for item in result["predicates"]],
            ["receives", "parses", "manages", "manages"],
        )
        self.assertEqual(
            [item["text"] for item in result["components"] if item["role"] == "O"],
            ["requests", "queries", "metadata", "nodes"],
        )
        self.assertFalse(
            any(item["type"] in {"独立分句", "并列主句"} for item in result["clauses"]),
            "冒号后的四个谓语共享 Frontend，不应拆成四个独立分句。",
        )
        for phrase in ("receives requests", "parses queries", "manages metadata", "manages nodes"):
            self.assertIn(phrase, result["semantic_skeleton"])

    def test_doris_compute_layer_stays_a_nominal_fragment_with_a_relative_clause(self):
        result = server.analyze_with_stanza(
            "Compute layer: multiple compute groups, each of which can serve as an independent tenant",
            self.config,
        )

        self.assertEqual(result["pattern"], "句子片段（名词短语）")
        self.assertEqual(result["predicates"], [])
        self.assertEqual(
            [(item["text"], item["role"], item["label"]) for item in result["components"]],
            [("Compute layer: multiple compute groups", "C", "名词性片段")],
        )
        self.assertEqual(result["skeleton"], "Compute layer: multiple compute groups")
        self.assertEqual(len(result["clauses"]), 1)
        relative = result["clauses"][0]
        self.assertEqual(relative["text"], "each of which can serve as an independent tenant")
        self.assertEqual(relative["type"], "定语从句")
        self.assertEqual(relative["function"], "修饰先行词 groups")
        self.assertEqual(relative["marker"].lower(), "which")

    def test_doris_passive_deployment_keeps_both_adverbials_out_of_the_predicate(self):
        result = server.analyze_with_stanza(
            "In production, multiple FE nodes are deployed for high availability.",
            self.config,
        )

        self.assertEqual(result["pattern"], "SV")
        self.assertEqual(
            [(item["text"], item["role"]) for item in result["components"]],
            [
                ("In production", "Adv"),
                ("multiple FE nodes", "S"),
                ("are deployed", "V"),
                ("for high availability", "Adv"),
            ],
        )
        self.assertEqual(len(result["predicates"]), 1)
        self.assertEqual(result["predicates"][0]["text"], "are deployed")
        self.assertEqual(result["predicates"][0]["voice"], "被动")
        self.assertEqual(result["clauses"], [])
        self.assertEqual(result["semantic_skeleton"], "FE nodes are deployed")

    def test_comma_before_gerund_subject_is_not_a_parallel_participle_series(self):
        result = server.analyze_with_stanza(
            "He said, building trust requires listening.",
            self.config,
        )

        self.assertFalse(any(item["label"] == "并列非谓语状语" for item in result["components"]))
        self.assertFalse(any(item["form"] == "doing 并列" for item in result["non_finite"]))
        complement = next(item for item in result["clauses"] if item["text"].startswith("building trust"))
        self.assertEqual(complement["type"], "名词性从句")
        self.assertIn("requires", {item["text"] for item in result["predicates"]})

    def test_correlative_conjunctions_only_use_their_matching_partner(self):
        doris = server.analyze_with_stanza(
            "When deploying Apache Doris, you can choose either the integrated storage and compute "
            "architecture or the decoupled storage and compute architecture based on business needs.",
            self.config,
        )
        either_connectors = [
            item["connector"].lower()
            for item in doris["parallel_structures"]
            if item["connector"].lower().startswith("either")
        ]
        self.assertEqual(either_connectors, ["either ... or"])

        cases = [
            ("Neither Alice nor Bob attended.", "neither ... nor"),
            ("Both Alice and Bob attended.", "both ... and"),
        ]
        for sentence, expected in cases:
            with self.subTest(sentence=sentence):
                result = server.analyze_with_stanza(sentence, self.config)
                connectors = [
                    item["connector"].lower()
                    for item in result["parallel_structures"]
                    if item["connector"].lower().startswith(expected.split()[0])
                ]
                self.assertEqual(connectors, [expected])

    def test_doris_copular_clause_does_not_swallow_shared_subject_predicates(self):
        result = server.analyze_with_stanza(
            "Apache Doris is highly compatible with the MySQL protocol, supports standard SQL, "
            "can be accessed by various client tools, and integrates seamlessly with BI tools.",
            self.config,
        )

        complement = next(item for item in result["components"] if item["role"] == "SC")
        for leaked_predicate in ("supports", "accessed", "integrates"):
            self.assertNotIn(leaked_predicate, complement["text"])

        predicate_texts = [item["text"] for item in result["predicates"]]
        self.assertEqual(predicate_texts, ["is", "supports", "can be accessed", "integrates"])
        component_labels = {
            (item["text"], item["label"])
            for item in result["components"]
        }
        self.assertIn(("by various client tools", "施事状语"), component_labels)
        self.assertIn(("seamlessly", "状语"), component_labels)
        self.assertIn(("with BI tools", "状语"), component_labels)
        self.assertFalse(
            any(
                item["type"] in {"独立分句", "并列主句"}
                and any(word in item["text"] for word in ("supports", "accessed", "integrates"))
                for item in result["clauses"]
            ),
            "后三个谓语共享 Apache Doris，不应拆成独立主句。",
        )
        semantic = result["semantic_skeleton"].lower()
        for verb in ("compatible", "supports", "accessed", "integrates"):
            self.assertIn(verb, semantic)

    def test_choice_basis_recovery_does_not_steal_nominal_modifiers(self):
        object_modifier = server.analyze_with_stanza(
            "Choose a database based on the MPP architecture.",
            self.config,
        )
        database = next(item for item in object_modifier["components"] if item["role"] == "O")
        self.assertEqual(database["text"], "a database based on the MPP architecture")
        self.assertFalse(any(item["label"] == "依据状语" for item in object_modifier["components"]))
        based = next(item for item in object_modifier["non_finite"] if item["text"].startswith("based"))
        self.assertEqual(based["function"], "分词定语")

        subject_modifier = server.analyze_with_stanza(
            "Candidates based on experience choose a plan.",
            self.config,
        )
        subject = next(item for item in subject_modifier["components"] if item["role"] == "S")
        self.assertEqual(subject["text"], "Candidates based on experience")
        self.assertFalse(any(item["label"] == "依据状语" for item in subject_modifier["components"]))
        self.assertEqual(
            sum("based on experience" in item["text"] for item in subject_modifier["components"]),
            1,
        )

    def test_doris_distributed_remains_a_modifier_inside_the_object_list(self):
        result = server.analyze_with_stanza(
            "In complex multi-table join scenarios, Doris uses global query planning, distributed "
            "join strategies, and Runtime Filter technology to greatly reduce data transfer and "
            "accelerate join performance.",
            self.config,
        )

        object_component = next(item for item in result["components"] if item["role"] == "O")
        self.assertIn("distributed join strategies", object_component["text"])
        self.assertFalse(
            any(item["text"] == "distributed" and item["role"] == "Adv" for item in result["components"])
        )
        distributed = next(item for item in result["non_finite"] if item["text"] == "distributed")
        self.assertEqual(distributed["function"], "分词定语")

    def test_so_coordination_requires_comma_and_excludes_so_that(self):
        coordinated = server.analyze_with_stanza(
            "I was tired, so I went home.",
            self.config,
        )
        result_clauses = [
            item for item in coordinated["clauses"]
            if "并列" in item["type"] and "结果" in item["type"]
        ]
        self.assertEqual(len(result_clauses), 1)
        result_clause = result_clauses[0]
        self.assertEqual(result_clause["connector"].lower(), "so")

        subordinate_cases = [
            "I left early so I could catch the bus.",
            "He spoke softly so that the baby could sleep.",
        ]
        for sentence in subordinate_cases:
            with self.subTest(sentence=sentence):
                result = server.analyze_with_stanza(sentence, self.config)
                self.assertFalse(
                    any("并列" in item["type"] and "结果" in item["type"] for item in result["clauses"])
                )

    def test_two_coordinated_copular_clauses_keep_separate_complements(self):
        result = server.analyze_with_stanza(
            "John is a teacher and Mary is a doctor.",
            self.config,
        )

        first_complement = next(item for item in result["components"] if item["role"] == "SC")
        self.assertEqual(first_complement["text"], "a teacher")
        self.assertEqual([item["text"] for item in result["predicates"]], ["is", "is"])
        second = next(item for item in result["clauses"] if item["type"] == "并列主句")
        self.assertEqual(second["connector"].lower(), "and")
        self.assertEqual(second["text"], "and Mary is a doctor")
        semantic = result["semantic_skeleton"].lower()
        self.assertIn("john is a teacher", semantic)
        self.assertIn("mary is a doctor", semantic)
        self.assertIn(";", semantic)

    def test_repeated_tokens_in_a_proper_name_are_not_semantically_deduplicated(self):
        result = server.analyze_with_stanza(
            "Duran Duran performs tonight.",
            self.config,
        )

        subject = next(item for item in result["components"] if item["role"] == "S")
        self.assertEqual(subject["text"], "Duran Duran")
        self.assertTrue(result["semantic_skeleton"].startswith("Duran Duran performs"))

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
        self.assertIn(
            ("in mind", "Adv"),
            {(item["text"], item["role"]) for item in first["components"]},
        )
        self.assertIn(
            ("it", "O", "形式宾语"),
            {(item["text"], item["role"], item["label"]) for item in first["components"]},
        )
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
