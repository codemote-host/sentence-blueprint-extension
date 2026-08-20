from __future__ import annotations

from statistics import mean
from typing import Any, Iterable


POS_ZH = {
    "NOUN": "名词", "PROPN": "专有名词", "PRON": "代词", "VERB": "动词",
    "AUX": "助动词/系动词", "ADJ": "形容词", "ADV": "副词", "ADP": "介词",
    "DET": "限定词", "CCONJ": "并列连词", "SCONJ": "从属连接词",
    "NUM": "数词", "PUNCT": "标点", "PART": "小品词", "X": "其他",
}

ROLE_LABELS = {
    "S": "主语", "V": "谓语", "O": "宾语", "IO": "间接宾语", "DO": "直接宾语",
    "SC": "表语/主补", "OC": "宾语补足语", "C": "补语", "Atr": "定语",
    "Adv": "状语", "App": "同位语", "Conj": "连接成分",
}

ADVERBIAL_TYPES = {
    "because": "原因状语从句", "since": "时间/原因状语从句", "as": "方式/时间/原因状语从句",
    "if": "条件状语从句", "unless": "条件状语从句", "although": "让步状语从句",
    "though": "让步状语从句", "when": "时间状语从句", "while": "时间/对比状语从句",
    "before": "时间状语从句", "after": "时间状语从句", "until": "时间状语从句",
    "once": "时间状语从句", "where": "地点状语从句", "wherever": "地点状语从句",
    "so": "结果状语从句", "than": "比较状语从句",
}

MODALS = {"can", "could", "may", "might", "must", "shall", "should", "will", "would", "ought"}
CLAUSE_RELATIONS = {"advcl", "acl:relcl", "ccomp", "csubj", "csubj:pass"}
INDEPENDENT_CLAUSE_RELATIONS = {"conj", "parataxis"}
# Only characters that can join a written compound belong here. Figure/en/em
# dashes separate phrases and must not turn ``cache—every`` into one word unit.
HYPHEN_CHARS = {"-", "‐", "‑"}
COMPOUND_MODIFIER_RELATIONS = {"amod", "compound", "acl"}
COMMENT_ADVERBS = {
    "personally", "again", "frankly", "honestly", "fortunately", "unfortunately",
    "obviously", "apparently", "admittedly", "seriously", "technically", "basically",
}


def _children(words: list[Any]) -> dict[int, list[Any]]:
    result: dict[int, list[Any]] = {word.id: [] for word in words}
    for word in words:
        if word.head in result:
            result[word.head].append(word)
    return result


def _descendant_ids(root_id: int, children: dict[int, list[Any]]) -> set[int]:
    found: set[int] = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(child.id for child in children.get(current, []))
    return found


def _span_text(source: str, words_by_id: dict[int, Any], ids: Iterable[int]) -> str:
    selected = [words_by_id[word_id] for word_id in sorted(set(ids)) if word_id in words_by_id]
    if not selected:
        return ""
    start = min(word.start_char for word in selected)
    end = max(word.end_char for word in selected)
    return source[start:end].strip(" \t\r\n,;:.!?")


def _component(text: str, role: str, ids: Iterable[int], explanation: str, label: str | None = None) -> dict[str, Any]:
    return {
        "text": text,
        "role": role,
        "label": label or ROLE_LABELS[role],
        "explanation": explanation,
        "_word_ids": sorted(set(ids)),
    }


def _predicate_ids(head: Any, words: list[Any], children: dict[int, list[Any]], include_shared_conj: bool = True) -> set[int]:
    ids = {head.id}
    for child in children.get(head.id, []):
        if child.deprel in {"aux", "aux:pass", "cop"}:
            ids.add(child.id)
        elif child.deprel == "advmod" and child.lemma in {"not", "never"}:
            ids.add(child.id)

    feats = head.feats or ""
    if include_shared_conj and ("Voice=Pass" in feats or any(child.deprel == "aux:pass" for child in children.get(head.id, []))):
        for child in children.get(head.id, []):
            if child.deprel == "conj" and child.upos in {"VERB", "ADJ"}:
                ids.add(child.id)
                ids.update(grandchild.id for grandchild in children.get(child.id, []) if grandchild.deprel == "cc")
    return ids


def _predicate_info(source: str, head: Any, words: list[Any], children: dict[int, list[Any]], ids: set[int] | None = None) -> dict[str, Any]:
    words_by_id = {word.id: word for word in words}
    predicate_ids = ids or _predicate_ids(head, words, children)
    predicate_words = [words_by_id[word_id] for word_id in sorted(predicate_ids)]
    lemmas = {word.lemma for word in predicate_words}
    feats = "|".join(filter(None, (word.feats for word in predicate_words)))
    tense = "一般现在时"
    if lemmas & MODALS:
        tense = "情态动词结构"
    elif "Tense=Past" in feats:
        tense = "过去时间结构"
    elif "Tense=Pres" in feats:
        tense = "一般现在时"
    if "have" in lemmas and any((word.feats or "").find("VerbForm=Part") >= 0 for word in predicate_words):
        tense += " · 完成结构"
    voice = "被动" if "Voice=Pass" in feats or any(word.deprel == "aux:pass" for word in predicate_words) else "主动"
    kind = "系动词谓语" if any(word.deprel == "cop" for word in predicate_words) else "动词谓语"
    return {
        "text": _join_core_words(words_by_id, predicate_ids),
        "tense": tense,
        "voice": voice,
        "type": kind,
        "_word_ids": sorted(predicate_ids),
    }


def _finite_head(word: Any, children: dict[int, list[Any]]) -> bool:
    feats = word.feats or ""
    if "VerbForm=Fin" in feats:
        return True
    return any("VerbForm=Fin" in (child.feats or "") for child in children.get(word.id, []) if child.deprel in {"aux", "aux:pass", "cop"})


def _do_so_ellipsis(word: Any, children: dict[int, list[Any]]) -> bool:
    dependents = children.get(word.id, [])
    has_do = any(child.deprel in {"aux", "cop"} and str(child.lemma or "").lower() == "do" for child in dependents)
    has_so = any(child.deprel == "advmod" and str(child.lemma or "").lower() == "so" for child in dependents)
    return word.deprel == "conj" and has_do and has_so


def _coordinated_result_clause(source: str, word: Any, children: dict[int, list[Any]]) -> bool:
    """Treat comma + ``so`` + finite clause as a coordinated result.

    Stanza may attach the second proposition as ``advcl``, ``conj`` or
    ``parataxis``.  The learner-facing distinction therefore also uses the
    written comma and requires ``so`` to modify the second clause itself.  The
    latter condition keeps ``so ... that`` result clauses subordinate.
    """
    dependents = children.get(word.id, [])
    so_marker = next((
        child
        for child in dependents
        if child.deprel in {"mark", "cc", "advmod"}
        and str(child.lemma or "").lower() == "so"
    ), None)
    if so_marker is None:
        return False
    after_so = source[so_marker.end_char:].lstrip().lower()
    if after_so == "that" or after_so.startswith("that "):
        return False
    has_preceding_comma = source[:so_marker.start_char].rstrip().endswith(",")
    has_subject = any(child.deprel.startswith("nsubj") for child in dependents)
    return (
        word.deprel in {"advcl", "conj", "parataxis"}
        and has_preceding_comma
        and has_subject
        and _finite_head(word, children)
    )


def _reduced_adverbial_clause(word: Any, children: dict[int, list[Any]]) -> bool:
    feats = str(word.feats or "")
    markers = {
        str(child.lemma or "").lower()
        for child in children.get(word.id, [])
        if child.deprel in {"mark", "advmod"}
    }
    return word.deprel == "advcl" and "VerbForm=Fin" not in feats and bool(markers & set(ADVERBIAL_TYPES))


def _independent_clause_head(source: str, word: Any, children: dict[int, list[Any]]) -> bool:
    coordinated_result = _coordinated_result_clause(source, word, children)
    if (
        word.deprel not in INDEPENDENT_CLAUSE_RELATIONS
        and not coordinated_result
    ) or word.upos not in {"VERB", "ADJ", "NOUN", "PROPN", "PRON"}:
        return False
    own_subject = any(
        child.deprel in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}
        for child in children.get(word.id, [])
    )
    why_ellipsis = any(child.lemma == "why" and child.deprel == "advmod" for child in children.get(word.id, []))
    if why_ellipsis or _do_so_ellipsis(word, children) or coordinated_result:
        return True
    return own_subject and _finite_head(word, children)


def _shared_predicate_heads(root: Any, words: list[Any], children: dict[int, list[Any]]) -> list[Any]:
    """Return finite ``conj/parataxis`` predicates inheriting the root subject.

    Technical prose often mixes a copular predicate, active verbs and a
    passive verb in one comma-delimited predicate list.  Stanza can label the
    passive member ``parataxis`` even though it has no local subject.  Walk the
    coordination chain recursively so later predicates remain attached to the
    matrix subject.
    """
    root_predicate_ids = _predicate_ids(root, words, children, include_shared_conj=True)
    results: list[Any] = []
    queue = [
        child
        for child in children.get(root.id, [])
        if child.deprel in {"conj", "parataxis"}
    ]
    visited: set[int] = set()
    while queue:
        candidate = queue.pop(0)
        if candidate.id in visited:
            continue
        visited.add(candidate.id)
        own_subject = any(
            dependent.deprel in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}
            for dependent in children.get(candidate.id, [])
        )
        if own_subject:
            # This is another proposition, so predicates coordinated inside it
            # belong to that proposition rather than to the matrix subject.
            continue
        queue.extend(
            child
            for child in children.get(candidate.id, [])
            if child.deprel in {"conj", "parataxis"}
        )
        if (
            candidate.upos in {"VERB", "ADJ", "AUX"}
            and candidate.id not in root_predicate_ids
            and _finite_head(candidate, children)
            and not _do_so_ellipsis(candidate, children)
        ):
            results.append(candidate)
    return sorted(results, key=lambda item: item.start_char)


def _comment_adverb(word: Any, children: dict[int, list[Any]]) -> bool:
    return (
        word.deprel == "discourse"
        or str(word.lemma or "").lower() in COMMENT_ADVERBS
    )


def _is_hyphen(word: Any) -> bool:
    return str(word.text) in HYPHEN_CHARS


def _touches_in_source(source: str, left: Any, right: Any) -> bool:
    """Return true only for a contiguous written form such as high-performance."""
    return source[left.end_char:right.start_char] == ""


def _hyphenated_groups(source: str, words: list[Any], children: dict[int, list[Any]]) -> list[dict[str, Any]]:
    """Create learner-facing units for contiguous hyphenated compounds.

    Universal Dependencies intentionally keeps the members of a compound separate
    (for example, high/ADJ + -/PUNCT + performance/NOUN).  That is valuable raw
    parsing data, but it is confusing when teaching the phrase as one modifier.
    """
    groups: list[dict[str, Any]] = []
    ordered = sorted(words, key=lambda item: item.start_char)
    cursor = 0
    while cursor < len(ordered):
        first = ordered[cursor]
        if _is_hyphen(first) or first.upos == "PUNCT":
            cursor += 1
            continue

        end_index = cursor
        has_hyphen = False
        while end_index + 2 < len(ordered):
            hyphen = ordered[end_index + 1]
            following = ordered[end_index + 2]
            if (
                not _is_hyphen(hyphen)
                or following.upos == "PUNCT"
                or not _touches_in_source(source, ordered[end_index], hyphen)
                or not _touches_in_source(source, hyphen, following)
            ):
                break
            end_index += 2
            has_hyphen = True

        if not has_hyphen:
            cursor += 1
            continue

        members = ordered[cursor:end_index + 1]
        lexical_members = [item for item in members if not _is_hyphen(item)]
        member_ids = {item.id for item in members}
        external_head = next(
            (item for item in reversed(lexical_members) if item.head not in member_ids),
            lexical_members[-1],
        )
        relation = str(external_head.deprel or "")
        has_copula = any(child.deprel == "cop" for child in children.get(external_head.id, []))
        adjective_like = any(item.upos == "ADJ" for item in lexical_members) or external_head.upos == "VERB"
        if relation in COMPOUND_MODIFIER_RELATIONS:
            label = "复合形容词（作定语）"
        elif has_copula or adjective_like:
            label = "复合形容词"
        else:
            label = "连字符复合词"

        groups.append({
            "start": first.start_char,
            "end": members[-1].end_char,
            "text": source[first.start_char:members[-1].end_char],
            "pos": label,
            "parts": [
                {"text": item.text, "pos": POS_ZH.get(item.upos, item.upos)}
                for item in lexical_members
            ],
        })
        cursor = end_index + 1
    return groups


def _trailing_ing_series(source: str, root: Any, words: list[Any]) -> list[Any]:
    """Recover comma-separated -ing series that Stanza occasionally tags NOUN."""
    children = _children(words)
    candidates = [
        word
        for word in words
        if word.start_char > root.end_char
        and str(word.text).lower().endswith("ing")
        and word.upos in {"NOUN", "VERB"}
    ]
    if len(candidates) < 2:
        return []
    first = min(candidates, key=lambda item: item.start_char)
    if "," not in source[root.end_char:first.start_char]:
        return []
    ordered = sorted(candidates, key=lambda item: item.start_char)
    if not all(
        "," in source[left.end_char:right.start_char]
        or " and " in source[left.end_char:right.start_char].lower()
        or " or " in source[left.end_char:right.start_char].lower()
        for left, right in zip(ordered, ordered[1:])
    ):
        return []
    tail = source[first.start_char:].lower()
    if " and " not in tail and " or " not in tail:
        return []
    # Do not reinterpret a genuine finite clause merely because it happens to
    # contain two words ending in -ing (for example, "building ... requires
    # listening").  The Doris documentation case has no finite predicate in
    # the comma-delimited suffix.
    if any(
        word.id != root.id
        and word.start_char >= first.start_char
        and word not in ordered
        and _finite_head(word, children)
        for word in words
    ):
        return []
    return ordered


def _detached_nonfinite_heads(source: str, words: list[Any]) -> list[Any]:
    ordered = sorted(words, key=lambda item: item.start_char)
    results: list[Any] = []
    for index, word in enumerate(ordered):
        feats = str(word.feats or "")
        if word.upos not in {"VERB", "AUX"} or not any(
            flag in feats for flag in {"VerbForm=Inf", "VerbForm=Ger", "VerbForm=Part"}
        ):
            continue
        # Punctuation is represented as a token of its own, so checking only
        # the immediately preceding token misses `, ensuring ...`.  Look back
        # to the previous lexical word and inspect the complete surface gap.
        previous_lexical = next(
            (candidate for candidate in reversed(ordered[:index]) if candidate.upos != "PUNCT"),
            None,
        )
        if (
            previous_lexical
            and word.deprel not in {"conj", "amod"}
            and "," in source[previous_lexical.end_char:word.start_char]
        ):
            results.append(word)
    return results


def _matching_correlative_pair(
    right: Any,
    words_by_id: dict[int, Any],
    children: dict[int, list[Any]],
) -> tuple[Any, Any, Any] | None:
    """Return ``left, preconnector, connector`` for a valid fixed pair."""
    if right.deprel != "conj" or right.head not in words_by_id:
        return None
    left = words_by_id[right.head]
    connector = next(
        (
            child
            for child in children.get(right.id, [])
            if child.deprel == "cc"
            and str(child.lemma or child.text).lower() in {"and", "or", "nor"}
        ),
        None,
    )
    preconnector = next(
        (
            child
            for child in children.get(left.id, [])
            if child.deprel == "cc:preconj"
            and str(child.lemma or child.text).lower() in {"either", "both", "neither"}
        ),
        None,
    )
    if connector is None or preconnector is None:
        return None
    expected_partner = {"either": "or", "both": "and", "neither": "nor"}
    preconnector_text = str(preconnector.lemma or preconnector.text).lower()
    connector_text = str(connector.lemma or connector.text).lower()
    if expected_partner.get(preconnector_text) != connector_text:
        return None
    return left, preconnector, connector


def _choice_basis_heads(root: Any, words: list[Any], children: dict[int, list[Any]]) -> list[Any]:
    """Recover trailing `based on ...` as the basis for a choice, not part of option B."""
    if str(root.lemma or "").lower() not in {"choose", "select", "pick", "decide"}:
        return []
    words_by_id = {word.id: word for word in words}
    object_ids: set[int] = set()
    for direct_object in children.get(root.id, []):
        if direct_object.deprel == "obj":
            object_ids.update(_descendant_ids(direct_object.id, children))
    if not object_ids:
        return []
    correlative_pairs = [
        (right, pair)
        for right in words
        if right.id in object_ids
        and (pair := _matching_correlative_pair(right, words_by_id, children)) is not None
    ]
    if not correlative_pairs:
        return []
    results: list[Any] = []
    for word in words:
        if (
            word.id not in object_ids
            or word.deprel != "acl"
            or str(word.lemma or "").lower() != "base"
        ):
            continue
        ids = _descendant_ids(word.id, children)
        has_basis_marker = any(
            item.id in ids
            and item.deprel == "case"
            and str(item.lemma or item.text).lower() in {"on", "upon"}
            for item in words
        )
        if not has_basis_marker:
            continue
        belongs_to_option_b = False
        for right, _pair in correlative_pairs:
            right_ids = _descendant_ids(right.id, children)
            if word.id not in right_ids:
                continue
            option_core_ids = right_ids - ids
            option_end = max(
                (words_by_id[word_id].end_char for word_id in option_core_ids),
                default=right.end_char,
            )
            if word.start_char >= option_end:
                belongs_to_option_b = True
                break
        if belongs_to_option_b:
            results.append(word)
    return results


def _parallel_pos_reconciliation(
    source: str,
    words: list[Any],
    children: dict[int, list[Any]],
) -> tuple[dict[int, str], list[dict[str, Any]]]:
    """Reconcile safe learner-facing POS mismatches inside coordination.

    Stanza keeps its original UPOS output in ``raw_word_classes``. This pass
    uses the dependency tree to improve the high-school-grammar presentation.
    It deliberately handles only high-confidence cases instead of assuming
    that every pair joined by a conjunction must share a lexical category.
    """
    words_by_id = {word.id: word for word in words}
    overrides: dict[int, str] = {}
    structures: list[dict[str, Any]] = []
    for right in words:
        if right.deprel != "conj" or right.head not in words_by_id:
            continue
        left = words_by_id[right.head]
        connector = next(
            (
                child
                for child in children.get(right.id, [])
                if child.deprel == "cc" and str(child.lemma or child.text).lower() in {"and", "or", "nor", "but"}
            ),
            None,
        )
        if connector is None:
            continue

        correlative_pair = _matching_correlative_pair(right, words_by_id, children)
        if correlative_pair:
            _left, preconnector, connector = correlative_pair
            right_ids = _descendant_ids(right.id, children)
            for modifier in (word for word in words if word.id in right_ids and word.deprel in {"acl", "advcl"}):
                right_ids -= _descendant_ids(modifier.id, children)
            end = max(words_by_id[word_id].end_char for word_id in right_ids)
            left_member = source[preconnector.end_char:connector.start_char].strip(" \t\r\n,;:.!?")
            right_member = source[connector.end_char:end].strip(" \t\r\n,;:.!?")
            structures.append({
                "text": source[preconnector.start_char:end].strip(" \t\r\n,;:.!?"),
                "connector": f"{preconnector.text} ... {connector.text}",
                "category": "同一成分位置",
                "members": [left_member, right_member],
                "explanation": f"{preconnector.text} ... {connector.text} 连接同一语法位置上的并列选项，不切分为两个主句。",
            })

        # In expressions such as "switch ... on or off", Stanza may label the
        # first item ADP and the second ADV. The tree supplies stronger evidence:
        # both are coordinated, and the ADP-shaped item functions adverbially
        # without a nominal complement.
        if {left.upos, right.upos} != {"ADP", "ADV"}:
            continue
        adposition = left if left.upos == "ADP" else right
        has_nominal_complement = any(
            child.deprel in {"case", "fixed", "nmod", "obl", "obj"}
            and child.upos in {"NOUN", "PROPN", "PRON", "NUM"}
            for child in children.get(adposition.id, [])
        )
        if adposition.deprel not in {"advmod", "compound:prt"} or has_nominal_complement:
            continue

        overrides[left.id] = "副词"
        overrides[right.id] = "副词"
        structures.append({
            "text": _span_text(source, words_by_id, {left.id, connector.id, right.id}),
            "connector": connector.text,
            "category": "副词",
            "members": [left.text, right.text],
            "explanation": f"{connector.text} 连接两个并列状态词；{left.text}/{right.text} 在此都作副词。",
        })
    return overrides, structures


def _teaching_word_classes(
    source: str,
    sentence: Any,
    words: list[Any],
    children: dict[int, list[Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return display units plus the unmodified Stanza token-level word classes."""
    raw: list[dict[str, Any]] = []
    token_units: list[dict[str, Any]] = []
    for token in sentence.tokens:
        token_words = list(token.words)
        primary = next((word for word in token_words if word.upos not in {"PUNCT", "PART"}), token_words[0])
        if primary.upos == "PUNCT":
            continue
        item = {
            "text": token.text,
            "pos": POS_ZH.get(primary.upos, primary.upos),
        }
        raw.append(item)
        token_units.append({
            **item,
            "word_id": primary.id,
            "start": token.start_char,
            "end": token.end_char,
        })

    pos_overrides, parallel_structures = _parallel_pos_reconciliation(source, words, children)
    root = next((word for word in words if word.head == 0), words[0])
    surface_ing_ids = {word.id for word in _trailing_ing_series(source, root, words)}
    for item in token_units:
        if item["word_id"] in pos_overrides:
            item["pos"] = pos_overrides[item["word_id"]]
        elif item["word_id"] in surface_ing_ids:
            item["pos"] = "动词（doing）"

    groups = _hyphenated_groups(source, words, children)
    groups_by_start = {item["start"]: item for item in groups}
    display: list[dict[str, Any]] = []
    for item in token_units:
        group = groups_by_start.get(item["start"])
        if group:
            display.append({key: value for key, value in group.items() if key not in {"start", "end"}})
            continue
        if any(group["start"] < item["start"] < group["end"] for group in groups):
            continue
        display.append({"text": item["text"], "pos": item["pos"]})
    return display, raw, parallel_structures


def _nominal_core_ids(
    head: Any,
    children: dict[int, list[Any]],
    include_coordination: bool = False,
    seen_ids: set[int] | None = None,
) -> set[int]:
    """Keep the semantic head of a noun phrase and only indispensable framing."""
    ids = {head.id}
    seen = seen_ids if seen_ids is not None else set()
    if head.id in seen:
        return set()
    seen.add(head.id)
    for child in children.get(head.id, []):
        lemma = str(child.lemma or child.text).lower()
        if child.deprel == "det" and lemma in {"a", "an", "the"}:
            ids.add(child.id)
        elif child.deprel in {"flat", "flat:name"}:
            ids.add(child.id)
        elif child.deprel == "compound" and (head.upos == "PROPN" or child.upos == "PROPN"):
            ids.add(child.id)
        elif include_coordination and child.deprel == "conj" and child.upos in {"NOUN", "PROPN", "PRON", "NUM"}:
            ids.update(
                coordinator.id
                for coordinator in children.get(child.id, [])
                if coordinator.deprel == "cc"
            )
            ids.update(_nominal_core_ids(child, children, True, seen))
    return ids


def _join_core_words(words_by_id: dict[int, Any], ids: Iterable[int]) -> str:
    selected = [words_by_id[word_id] for word_id in sorted(set(ids)) if word_id in words_by_id]
    text = " ".join(str(word.text) for word in selected)
    return text.replace(" n't", "n't").replace(" 's", "'s")


def _semantic_skeleton(
    root: Any,
    subject: Any | None,
    words: list[Any],
    children: dict[int, list[Any]],
    outer_copular_clause: bool,
    copulas: list[Any],
) -> str:
    """Build a readable proposition from dependency heads, without modifiers."""
    words_by_id = {word.id: word for word in words}
    ids: set[int] = set()
    if subject:
        ids.update(_nominal_core_ids(subject, children, include_coordination=True))

    if outer_copular_clause:
        ids.update(word.id for word in copulas)
        marker = next((child for child in children.get(root.id, []) if child.deprel == "mark"), None)
        if marker:
            ids.add(marker.id)
        inner_subject = next(
            (child for child in children.get(root.id, []) if child.deprel in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}),
            None,
        )
        if inner_subject:
            ids.update(_nominal_core_ids(inner_subject, children, include_coordination=True))
        inner_predicate_ids = _predicate_ids(root, words, children, include_shared_conj=False)
        inner_predicate_ids.difference_update(word.id for word in copulas)
        ids.update(inner_predicate_ids)
        for item in children.get(root.id, []):
            if item.deprel in {"obj", "iobj"}:
                ids.update(_nominal_core_ids(item, children, include_coordination=True))
        core = _join_core_words(words_by_id, ids)
        elliptical = next((word for word in words if _do_so_ellipsis(word, children)), None)
        if elliptical:
            second_ids = _descendant_ids(elliptical.id, children)
            for item in children.get(elliptical.id, []):
                is_pro_verb_frame = (
                    item.deprel in {"cc", "punct"}
                    or (item.deprel in {"aux", "cop"} and str(item.lemma or "").lower() == "do")
                    or (item.deprel == "advmod" and str(item.lemma or "").lower() == "so")
                )
                if is_pro_verb_frame:
                    second_ids -= _descendant_ids(item.id, children)
            second_subject = _join_core_words(words_by_id, second_ids)
            if second_subject:
                core = f"{core}; {second_subject} does so"
        return core

    ids.update(_predicate_ids(root, words, children, include_shared_conj=True))
    if copulas and root.upos in {"NOUN", "PROPN", "PRON"}:
        ids.update(_nominal_core_ids(root, children))
    for item in children.get(root.id, []):
        if item.deprel in {"obj", "iobj"}:
            ids.update(_nominal_core_ids(item, children, include_coordination=True))
        elif item.deprel == "xcomp":
            marker = next((child for child in children.get(item.id, []) if child.deprel == "mark"), None)
            if marker:
                ids.add(marker.id)
            ids.add(item.id)
    core = _join_core_words(words_by_id, ids)
    shared_parts: list[str] = []
    for shared in _shared_predicate_heads(root, words, children):
        shared_ids = _predicate_ids(shared, words, children, include_shared_conj=False)
        for item in children.get(shared.id, []):
            if item.deprel in {"obj", "iobj"}:
                shared_ids.update(_nominal_core_ids(item, children, include_coordination=True))
            elif item.deprel == "xcomp":
                shared_ids.add(item.id)
        shared_core = _join_core_words(words_by_id, shared_ids)
        coordinator = next((item for item in children.get(shared.id, []) if item.deprel == "cc"), None)
        if coordinator:
            shared_core = f"{coordinator.text} {shared_core}"
        if shared_core:
            shared_parts.append(shared_core)
    if shared_parts:
        return ", ".join([core, *shared_parts])
    return core


def analyze_sentence(source: str, sentence: Any) -> dict[str, Any]:
    words = list(sentence.words)
    words_by_id = {word.id: word for word in words}
    children = _children(words)
    original_root = next(word for word in words if word.head == 0)
    bullet_subject: Any | None = None
    bullet_predicate = next(
        (
            child
            for child in children.get(original_root.id, [])
            if child.deprel == "parataxis"
            and child.upos in {"VERB", "ADJ", "AUX"}
            and _finite_head(child, children)
            and "Person=3" in str(child.feats or "")
            and ":" in source[original_root.end_char:child.start_char]
            and not any(
                dependent.deprel in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}
                for dependent in children.get(child.id, [])
            )
        ),
        None,
    )
    if bullet_predicate and original_root.upos in {"NOUN", "PROPN", "PRON"}:
        bullet_subject = original_root
        root = bullet_predicate
    else:
        root = original_root
    components: list[dict[str, Any]] = []
    nominal_fragment = root.upos in {"NOUN", "PROPN", "PRON", "NUM"} and not _finite_head(root, children)
    detached_nonfinite = _detached_nonfinite_heads(source, words)
    choice_basis_heads = _choice_basis_heads(root, words, children)
    trailing_ing_series = _trailing_ing_series(source, root, words)
    trailing_ing_start = trailing_ing_series[0].start_char if trailing_ing_series else None

    copulas = [word for word in children.get(root.id, []) if word.deprel == "cop"]
    shared_predicate_heads = _shared_predicate_heads(root, words, children)
    outer_subject = next((word for word in children.get(root.id, []) if word.deprel == "nsubj:outer"), None)
    clause_marker = next((word for word in children.get(root.id, []) if word.deprel == "mark"), None)
    outer_copular_clause = bool(copulas and outer_subject and clause_marker)
    subject = bullet_subject or outer_subject or next(
        (word for word in children.get(root.id, []) if word.deprel in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}),
        None,
    )
    direct_adv = [
        word
        for word in children.get(root.id, [])
        if word.deprel in {"advcl", "obl", "advmod", "discourse"}
        and str(word.lemma or "").lower() not in {"not", "never"}
        and not _coordinated_result_clause(source, word, children)
    ]
    if outer_copular_clause and clause_marker:
        direct_adv = [word for word in direct_adv if word.start_char < clause_marker.start_char]
    for adverbial in sorted((word for word in direct_adv if word.start_char < root.start_char), key=lambda item: item.start_char):
        ids = _descendant_ids(adverbial.id, children)
        for detached in detached_nonfinite:
            if detached.id != adverbial.id and detached.id in ids:
                ids -= _descendant_ids(detached.id, children)
        is_comment = _comment_adverb(adverbial, children)
        components.append(_component(
            _span_text(source, words_by_id, ids), "Adv", ids,
            "位于句首，对整句话表达说话人的态度、视角或衔接关系。" if is_comment
            else "位于主句主干之前，说明原因、时间、地点、条件或背景。",
            "评注性状语" if is_comment else None,
        ))

    if subject:
        subject_ids = _descendant_ids(subject.id, children)
        if bullet_subject:
            subject_ids -= _descendant_ids(root.id, children)
        components.append(_component(
            _span_text(source, words_by_id, subject_ids), "S", subject_ids,
            "由 Stanza 的主语依存关系识别。",
        ))

    main_predicate_ids = _predicate_ids(root, words, children)
    outer_complement_ids: set[int] = set()
    if copulas:
        copula_ids = {word.id for word in copulas}
        copula_ids.update(word.id for word in children.get(root.id, []) if word.deprel == "advmod" and word.lemma in {"not", "never"})
        components.append(_component(
            _span_text(source, words_by_id, copula_ids), "V", copula_ids,
            "系动词及其否定成分构成谓语。",
        ))
        if outer_copular_clause:
            complement_ids = _descendant_ids(root.id, children)
            for child in children.get(root.id, []):
                matrix_adverb = child.deprel in {"advmod", "discourse"} and clause_marker and child.start_char < clause_marker.start_char
                if child.deprel in {"nsubj:outer", "cop", "punct", "conj", "parataxis"} or matrix_adverb:
                    complement_ids -= _descendant_ids(child.id, children)
            for appositive in (word for word in words if word.deprel == "appos" and word.id in complement_ids):
                complement_ids -= _descendant_ids(appositive.id, children)
            complement_ids.add(root.id)
            outer_complement_ids = set(complement_ids)
        else:
            excluded = set(copula_ids)
            if subject:
                excluded.update(_descendant_ids(subject.id, children))
            complement_ids = _descendant_ids(root.id, children) - excluded
            for child in children.get(root.id, []):
                if child.deprel in CLAUSE_RELATIONS or child.deprel in {"obl", "punct"}:
                    complement_ids -= _descendant_ids(child.id, children)
                elif child in shared_predicate_heads or _independent_clause_head(source, child, children):
                    complement_ids -= _descendant_ids(child.id, children)
            complement_ids.discard(root.id) if root.upos == "PUNCT" else None
            complement_ids.add(root.id)
        components.append(_component(
            _span_text(source, words_by_id, complement_ids), "SC", complement_ids,
            "that 引导的从句作表语，说明主语的具体内容。" if outer_copular_clause
            else "说明主语的身份、性质或状态。",
        ))
        if outer_copular_clause:
            for appositive in (word for word in words if word.deprel == "appos"):
                appositive_ids = {
                    word_id
                    for word_id in _descendant_ids(appositive.id, children)
                    if words_by_id[word_id].upos != "PUNCT"
                }
                components.append(_component(
                    _span_text(source, words_by_id, appositive_ids), "App", appositive_ids,
                    "对前面名词再作解释，不进入主干。",
                ))
    else:
        components.append(_component(
            _join_core_words(words_by_id, main_predicate_ids), "V", main_predicate_ids,
            "包含限定助动词、被动标记以及共享助动词的并列谓语。",
        ))

    iobjects = [word for word in children.get(root.id, []) if word.deprel == "iobj"]
    anticipatory_objects = [
        word
        for word in children.get(root.id, [])
        if word.deprel == "expl"
        and str(word.lemma or word.text).lower() == "it"
        and any(child.deprel == "ccomp" for child in children.get(root.id, []))
    ]
    objects = [word for word in children.get(root.id, []) if word.deprel == "obj"] + anticipatory_objects
    xcomps = [word for word in children.get(root.id, []) if word.deprel == "xcomp"]
    for item in ([] if outer_copular_clause else iobjects):
        ids = _descendant_ids(item.id, children)
        for detached in detached_nonfinite:
            if detached.id in ids:
                ids -= _descendant_ids(detached.id, children)
        for basis in choice_basis_heads:
            if basis.id in ids:
                ids -= _descendant_ids(basis.id, children)
        if trailing_ing_start is not None:
            ids = {word_id for word_id in ids if words_by_id[word_id].start_char < trailing_ing_start}
        role = "O" if xcomps else "IO"
        explanation = "后面带有开放补语，当前成分是宾补结构中的宾语。" if role == "O" else "动作的接受者，依存关系为间接宾语。"
        components.append(_component(_span_text(source, words_by_id, ids), role, ids, explanation))
    for item in ([] if outer_copular_clause else objects):
        ids = _descendant_ids(item.id, children)
        for detached in detached_nonfinite:
            if detached.id in ids:
                ids -= _descendant_ids(detached.id, children)
        for basis in choice_basis_heads:
            if basis.id in ids:
                ids -= _descendant_ids(basis.id, children)
        if trailing_ing_start is not None:
            ids = {word_id for word_id in ids if words_by_id[word_id].start_char < trailing_ing_start}
        role = "DO" if iobjects and not xcomps else "O"
        if item in anticipatory_objects:
            components.append(_component(
                _span_text(source, words_by_id, ids), role, ids,
                "先占据宾语位置，后面的 that 从句说明真正的内容。",
                "形式宾语",
            ))
        else:
            components.append(_component(_span_text(source, words_by_id, ids), role, ids, "动作直接涉及的人或事物。"))
    for item in ([] if outer_copular_clause else xcomps):
        ids = _descendant_ids(item.id, children)
        role = "OC" if objects or iobjects else "C"
        explanation = "说明宾语要做什么或处于什么状态，宾语与其构成逻辑主谓。" if role == "OC" else "补充谓语的内容。"
        components.append(_component(_span_text(source, words_by_id, ids), role, ids, explanation))

    for shared in ([] if outer_copular_clause else shared_predicate_heads):
        coordinator = next((item for item in children.get(shared.id, []) if item.deprel == "cc"), None)
        if coordinator:
            components.append(_component(
                coordinator.text, "Conj", {coordinator.id},
                "连接共享同一主语的并列谓语。",
            ))
        shared_predicate_ids = _predicate_ids(shared, words, children, include_shared_conj=False)
        components.append(_component(
            _join_core_words(words_by_id, shared_predicate_ids), "V", shared_predicate_ids,
            "与前一谓语共享同一个主语，属于并列谓语。",
            "并列谓语",
        ))
        for item in children.get(shared.id, []):
            ids = _descendant_ids(item.id, children)
            if item.deprel in {"obj", "iobj"}:
                role = "IO" if item.deprel == "iobj" else "O"
                components.append(_component(
                    _span_text(source, words_by_id, ids), role, ids,
                    "与当前并列谓语配套的宾语。",
                ))
            elif (
                item.deprel in {"obl", "obl:agent", "advmod"}
                and str(item.lemma or "").lower() not in {"not", "never"}
            ):
                components.append(_component(
                    _span_text(source, words_by_id, ids), "Adv", ids,
                    "补充说明当前并列谓语的方式、范围、工具或施事者。",
                    "施事状语" if item.deprel == "obl:agent" else None,
                ))

    for basis in choice_basis_heads:
        ids = _descendant_ids(basis.id, children)
        components.append(_component(
            _span_text(source, words_by_id, ids), "Adv", ids,
            "说明选择所依据的标准，不属于 either/or 的任一选项。",
            "依据状语",
        ))

    occupied_ids = {word_id for component in components for word_id in component["_word_ids"]}
    for adverbial in sorted((word for word in direct_adv if word.start_char >= root.start_char), key=lambda item: item.start_char):
        ids = _descendant_ids(adverbial.id, children)
        for detached in detached_nonfinite:
            if detached.id != adverbial.id and detached.id in ids:
                ids -= _descendant_ids(detached.id, children)
        if trailing_ing_start is not None and adverbial.start_char >= trailing_ing_start:
            continue
        if ids & occupied_ids:
            continue
        components.append(_component(
            _span_text(source, words_by_id, ids), "Adv", ids,
            "修饰主句谓语，说明方式、地点、范围或伴随信息。",
        ))

    occupied_ids = {word_id for component in components for word_id in component["_word_ids"]}
    for detached in sorted(detached_nonfinite, key=lambda item: item.start_char):
        if detached.id in occupied_ids:
            continue
        ids = _descendant_ids(detached.id, children)
        for clause_head in words:
            if clause_head.id != detached.id and clause_head.id in ids and clause_head.deprel in CLAUSE_RELATIONS and _finite_head(clause_head, children):
                ids -= _descendant_ids(clause_head.id, children)
        components.append(_component(
            _span_text(source, words_by_id, ids), "Adv", ids,
            "逗号后的分词短语，表示伴随、方式或结果，不是第二个有限谓语。",
            "非谓语状语",
        ))
        occupied_ids.update(ids)

    if trailing_ing_series:
        ids = {
            word.id
            for word in words
            if word.start_char >= trailing_ing_series[0].start_char and word.upos != "PUNCT"
        }
        components.append(_component(
            _span_text(source, words_by_id, ids), "Adv", ids,
            "多个 -ing 形式共享主句主语，作伴随/方式状语。",
            "并列非谓语状语",
        ))

    components.sort(key=lambda item: min((words_by_id[word_id].start_char for word_id in item["_word_ids"]), default=10**9))

    predicates: list[dict[str, Any]] = []
    predicate_heads = [] if copulas or nominal_fragment else [root]
    if copulas:
        predicates.append(_predicate_info(source, copulas[0], words, children, {word.id for word in copulas}))
    if outer_copular_clause:
        inner_predicate_ids = _predicate_ids(root, words, children, include_shared_conj=False)
        inner_predicate_ids.difference_update(word.id for word in copulas)
        predicates.append(_predicate_info(source, root, words, children, inner_predicate_ids))
    predicate_heads.extend(word for word in words if word.deprel in CLAUSE_RELATIONS and _finite_head(word, children))
    predicate_heads.extend(word for word in words if _independent_clause_head(source, word, children))
    predicate_heads.extend(shared_predicate_heads)
    seen_predicate_ids: set[tuple[int, ...]] = set()
    for head in predicate_heads:
        if _do_so_ellipsis(head, children):
            pro_verb = next(
                child
                for child in children.get(head.id, [])
                if child.deprel in {"aux", "cop"} and str(child.lemma or "").lower() == "do"
            )
            info = _predicate_info(source, pro_verb, words, children, {pro_verb.id})
            info["type"] = "省略替代谓语"
        elif _independent_clause_head(source, head, children) and (head_copulas := [
            child for child in children.get(head.id, []) if child.deprel == "cop"
        ]):
            copula_ids = {child.id for child in head_copulas}
            copula_ids.update(
                child.id
                for child in children.get(head.id, [])
                if child.deprel == "advmod" and str(child.lemma or "").lower() in {"not", "never"}
            )
            info = _predicate_info(source, head_copulas[0], words, children, copula_ids)
        elif head in shared_predicate_heads:
            shared_ids = _predicate_ids(head, words, children, include_shared_conj=False)
            info = _predicate_info(source, head, words, children, shared_ids)
        else:
            info = _predicate_info(source, head, words, children)
        key = tuple(info["_word_ids"])
        if key not in seen_predicate_ids:
            predicates.append(info)
            seen_predicate_ids.add(key)

    clauses: list[dict[str, Any]] = []
    if outer_copular_clause and outer_complement_ids:
        clauses.append({
            "text": _span_text(source, words_by_id, outer_complement_ids),
            "type": "表语从句",
            "function": "表语/主语补足语",
            "marker": clause_marker.text if clause_marker else "",
            "connector": "",
        })
    for head in words:
        if head.id == root.id:
            continue
        reduced_adverbial = _reduced_adverbial_clause(head, children)
        subordinate = (head.deprel in CLAUSE_RELATIONS and _finite_head(head, children)) or reduced_adverbial
        independent = _independent_clause_head(source, head, children)
        if not subordinate and not independent:
            continue
        ids = _descendant_ids(head.id, children)
        marker = next((word for word in words if word.id in ids and (word.deprel == "mark" or word.lemma in {"that", "who", "which", "whom", "whose", "where", "when", "why"})), None)
        marker_text = marker.text if marker else ""
        coordinator = next((child for child in children.get(head.id, []) if child.deprel == "cc"), None)
        connector_text = coordinator.text if coordinator else ""
        result_connector = next(
            (
                child
                for child in children.get(head.id, [])
                if child.deprel in {"mark", "cc", "advmod"}
                and str(child.lemma or child.text).lower() == "so"
            ),
            None,
        )
        if _coordinated_result_clause(source, head, children) and result_connector:
            connector_text = result_connector.text
        if independent:
            why_ellipsis = any(
                child.lemma == "why" and child.deprel == "advmod"
                for child in children.get(head.id, [])
            )
            if _coordinated_result_clause(source, head, children):
                clause_type = "并列结果分句"
                function = "so 连接第二套完整主谓，表示前句带来的结果"
            elif _do_so_ellipsis(head, children):
                clause_type = "并列省略分句"
                function = "第二套主谓；does 代替前一分句的谓语内容"
            elif why_ellipsis:
                clause_type = "独立省略问句"
                function = "冒号或并列后的独立表达"
            elif head.deprel == "conj":
                clause_type = "并列主句"
                function = "与前一主句并列"
            else:
                clause_type = "独立分句"
                function = "补充或插入表达"
        elif head.deprel == "advcl":
            clause_type = ADVERBIAL_TYPES.get((marker.lemma if marker else ""), "状语从句")
            if reduced_adverbial:
                clause_type = f"{clause_type}（省略）"
            function = "状语"
        elif head.deprel == "acl:relcl":
            clause_type = "定语从句"
            antecedent = words_by_id.get(head.head)
            function = f"修饰先行词 {antecedent.text}" if antecedent else "定语"
        elif head.deprel.startswith("csubj"):
            clause_type = "主语从句"
            function = "主语"
        else:
            clause_type = "名词性从句"
            function = "宾语/补充内容"
        clauses.append({
            "text": _span_text(source, words_by_id, ids),
            "type": clause_type,
            "function": function,
            "marker": marker_text,
            "connector": connector_text,
        })

    predicate_word_ids = {word_id for item in predicates for word_id in item["_word_ids"]}
    non_finite: list[dict[str, Any]] = []
    nonfinite_candidates = [
        word
        for word in words
        if word.id not in predicate_word_ids
        and word not in trailing_ing_series
        and word.upos in {"VERB", "AUX"}
        and any(flag in str(word.feats or "") for flag in {"VerbForm=Inf", "VerbForm=Ger", "VerbForm=Part"})
    ]
    nonfinite_candidate_ids = {word.id for word in nonfinite_candidates}
    for word in nonfinite_candidates:
        feats = word.feats or ""
        ancestor = words_by_id.get(word.head)
        nested_under_nonfinite = False
        while ancestor:
            if ancestor.id in nonfinite_candidate_ids:
                nested_under_nonfinite = True
                break
            ancestor = words_by_id.get(ancestor.head)
        if nested_under_nonfinite:
            continue
        marker = next((child for child in children.get(word.id, []) if child.deprel == "mark" and child.lemma == "to"), None)
        ids = _descendant_ids(word.id, children)
        for clause_head in words:
            if clause_head.id != word.id and clause_head.id in ids and clause_head.deprel in CLAUSE_RELATIONS and _finite_head(clause_head, children):
                ids -= _descendant_ids(clause_head.id, children)
        if _reduced_adverbial_clause(word, children):
            ids.difference_update(
                child.id
                for child in children.get(word.id, [])
                if child.deprel in {"mark", "advmod"}
                and str(child.lemma or "").lower() in ADVERBIAL_TYPES
            )
        if marker:
            ids.add(marker.id)
        surface = str(word.text).lower()
        form = "to do" if marker else ("doing" if surface.endswith("ing") or "VerbForm=Ger" in feats else "done/分词")
        if word.deprel == "xcomp" and (objects or iobjects):
            function = "宾语补足语"
        elif _reduced_adverbial_clause(word, children):
            function = "省略状语从句的非谓语核心"
        elif word in detached_nonfinite:
            function = "伴随或结果状语"
        elif word in choice_basis_heads:
            function = "依据/标准状语"
        elif word.deprel == "advcl":
            function = "分词状语"
        elif word.deprel in {"acl", "amod"}:
            function = "分词定语"
        else:
            function = "非谓语修饰或补充成分"
        logical_subject_head = (objects or iobjects)[0] if (objects or iobjects) else None
        if function == "宾语补足语" and logical_subject_head:
            logical_subject = _span_text(source, words_by_id, _descendant_ids(logical_subject_head.id, children))
        elif function in {"省略状语从句的非谓语核心", "伴随或结果状语", "依据/标准状语", "分词状语"} and subject:
            logical_subject = _span_text(source, words_by_id, _nominal_core_ids(subject, children, include_coordination=True))
        else:
            logical_subject = ""
        non_finite.append({
            "text": _span_text(source, words_by_id, ids),
            "form": form,
            "function": function,
            "logical_subject": logical_subject,
        })

    if trailing_ing_series:
        lexical_words = [word for word in words if word.upos != "PUNCT"]
        series_text = source[trailing_ing_series[0].start_char:max(word.end_char for word in lexical_words)].strip(" \t\r\n,;:.!?")
        non_finite.append({
            "text": series_text,
            "form": "doing 并列",
            "function": "共享逻辑主语的伴随/方式非谓语",
            "logical_subject": _span_text(
                source,
                words_by_id,
                _nominal_core_ids(subject, children, include_coordination=True),
            ) if subject else "",
        })

    word_classes, raw_word_classes, parallel_structures = _teaching_word_classes(source, sentence, words, children)
    if shared_predicate_heads:
        predicate_members: list[str] = []
        all_member_ids: set[int] = set()
        for head in [root, *shared_predicate_heads]:
            member_ids = _predicate_ids(head, words, children, include_shared_conj=False)
            for child in children.get(head.id, []):
                if child.deprel in {"obj", "iobj", "xcomp", "obl", "obl:agent"} or (
                    child.deprel == "advmod"
                    and str(child.lemma or "").lower() not in {"not", "never"}
                ):
                    member_ids.update(_descendant_ids(child.id, children))
            all_member_ids.update(member_ids)
            predicate_members.append(_span_text(source, words_by_id, member_ids))
        coordinators = [
            child.text
            for head in shared_predicate_heads
            for child in children.get(head.id, [])
            if child.deprel == "cc"
        ]
        parallel_structures.append({
            "text": _span_text(source, words_by_id, all_member_ids),
            "connector": " / ".join(dict.fromkeys(coordinators)) or "并列",
            "category": "并列谓语",
            "members": predicate_members,
            "explanation": "多个谓语共享同一个主语，每个谓语保留自己的宾语或补语，不拆成多个主句。",
        })

    warnings: list[str] = []
    if nominal_fragment:
        fragment_ids = {word.id for word in words if word.upos != "PUNCT"}
        for clause in words:
            if clause.deprel in CLAUSE_RELATIONS and _finite_head(clause, children):
                fragment_ids -= _descendant_ids(clause.id, children)
        fragment_ids.add(root.id)
        fragment_text = _span_text(source, words_by_id, fragment_ids)
        components = [_component(
            fragment_text, "C", fragment_ids,
            "该内容没有限定谓语，是标题、列表项或名词短语。",
            "名词性片段",
        )]
        predicates = []
        pattern = "句子片段（名词短语）"
        skeleton = fragment_text
        semantic_skeleton = fragment_text
        warnings.append("该内容没有限定谓语，不按完整的 SV/SVO 句型硬拆。")
    else:
        roles = [component["role"] for component in components]
        if copulas:
            base_pattern = "SVC"
        elif "IO" in roles and "DO" in roles:
            base_pattern = "SVOO"
        elif "O" in roles and "OC" in roles:
            base_pattern = "SVOC"
        elif "O" in roles:
            base_pattern = "SVO"
        else:
            base_pattern = "SV"
        pattern = f"复合句（主句 {base_pattern}）" if clauses else base_pattern
        skeleton = " + ".join(component["text"] for component in components if component["role"] not in {"Adv", "Atr", "App", "Conj"})
        semantic_skeleton = _semantic_skeleton(root, subject, words, children, outer_copular_clause, copulas)
        for clause_head in words:
            if clause_head.id == root.id or not _independent_clause_head(source, clause_head, children) or _do_so_ellipsis(clause_head, children):
                continue
            clause_subject = next(
                (child for child in children.get(clause_head.id, []) if child.deprel in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}),
                None,
            )
            clause_copulas = [child for child in children.get(clause_head.id, []) if child.deprel == "cop"]
            clause_core = _semantic_skeleton(clause_head, clause_subject, words, children, False, clause_copulas)
            if clause_core and clause_core not in semantic_skeleton:
                semantic_skeleton = f"{semantic_skeleton}; {clause_core}"

    cleaned_components = [{key: value for key, value in component.items() if not key.startswith("_")} for component in components]
    cleaned_predicates = [{key: value for key, value in predicate.items() if not key.startswith("_")} for predicate in predicates]
    dependencies = [
        {"id": word.id, "text": word.text, "lemma": word.lemma, "pos": word.upos, "head": word.head, "relation": word.deprel}
        for word in words
    ]
    return {
        "sentence": sentence.text,
        "analysis_method": "Stanford Stanza",
        "pattern": pattern,
        "skeleton": skeleton,
        "semantic_skeleton": semantic_skeleton,
        "components": cleaned_components,
        "predicates": cleaned_predicates,
        "clauses": clauses,
        "parallel_structures": parallel_structures,
        "non_finite": non_finite,
        "word_classes": word_classes,
        "raw_word_classes": raw_word_classes,
        "explanations": [
            "Stanza 先生成依存树和成分树，再映射为主谓宾补定状同。",
            "判断顺序：有限谓语 → 连接词与标点 → 主句主干 → 从句和修饰成分。",
        ],
        "warnings": warnings,
        "confidence": 0.92 if nominal_fragment else (0.9 if not clauses else 0.87),
        "constituency_tree": str(sentence.constituency),
        "dependencies": dependencies,
    }


def analyze_document(pipeline: Any, source: str, prompt_version: str) -> dict[str, Any]:
    document = pipeline(source)
    analyses = [analyze_sentence(source, sentence) for sentence in document.sentences]
    if not analyses:
        raise ValueError("Stanza 没有识别到可分析的英文句子")
    for analysis in analyses:
        analysis["prompt_version"] = prompt_version
    if len(analyses) == 1:
        return analyses[0]
    return {
        "sentence": source,
        "analysis_method": "Stanford Stanza",
        "pattern": f"{len(analyses)} 句文本",
        "skeleton": " ｜ ".join(item["skeleton"] for item in analyses),
        "semantic_skeleton": " ｜ ".join(item["semantic_skeleton"] for item in analyses),
        "components": [],
        "predicates": [],
        "clauses": [],
        "parallel_structures": [],
        "non_finite": [],
        "word_classes": [],
        "explanations": ["Stanza 已先自动分句，再分别分析每句话。"],
        "warnings": [],
        "confidence": round(mean(float(item["confidence"]) for item in analyses), 2),
        "sentence_analyses": analyses,
        "prompt_version": prompt_version,
    }
