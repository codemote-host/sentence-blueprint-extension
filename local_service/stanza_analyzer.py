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
HYPHEN_CHARS = {"-", "‐", "‑", "‒", "–", "—"}
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
        "text": _span_text(source, words_by_id, predicate_ids),
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


def _independent_clause_head(word: Any, children: dict[int, list[Any]]) -> bool:
    if word.deprel not in INDEPENDENT_CLAUSE_RELATIONS or word.upos not in {"VERB", "ADJ"}:
        return False
    own_subject = any(
        child.deprel in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}
        for child in children.get(word.id, [])
    )
    why_ellipsis = any(child.lemma == "why" and child.deprel == "advmod" for child in children.get(word.id, []))
    return own_subject or why_ellipsis or (word.deprel == "parataxis" and _finite_head(word, children))


def _comment_adverb(word: Any, children: dict[int, list[Any]]) -> bool:
    return (
        word.deprel == "discourse"
        or str(word.lemma or "").lower() in COMMENT_ADVERBS
        or any(child.deprel == "punct" and child.text in {",", ":"} for child in children.get(word.id, []))
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


def _teaching_word_classes(source: str, sentence: Any, words: list[Any], children: dict[int, list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
            "start": token.start_char,
            "end": token.end_char,
        })

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
    return display, raw


def analyze_sentence(source: str, sentence: Any) -> dict[str, Any]:
    words = list(sentence.words)
    words_by_id = {word.id: word for word in words}
    children = _children(words)
    root = next(word for word in words if word.head == 0)
    components: list[dict[str, Any]] = []

    subject = next((word for word in children.get(root.id, []) if word.deprel in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}), None)
    direct_adv = [
        word
        for word in children.get(root.id, [])
        if word.deprel in {"advcl", "obl", "advmod", "discourse"}
        and str(word.lemma or "").lower() not in {"not", "never"}
    ]
    for adverbial in sorted((word for word in direct_adv if word.start_char < root.start_char), key=lambda item: item.start_char):
        ids = _descendant_ids(adverbial.id, children)
        is_comment = _comment_adverb(adverbial, children)
        components.append(_component(
            _span_text(source, words_by_id, ids), "Adv", ids,
            "位于句首，对整句话表达说话人的态度、视角或衔接关系。" if is_comment
            else "位于主句主干之前，说明原因、时间、地点、条件或背景。",
            "评注性状语" if is_comment else None,
        ))

    if subject:
        subject_ids = _descendant_ids(subject.id, children)
        components.append(_component(
            _span_text(source, words_by_id, subject_ids), "S", subject_ids,
            "由 Stanza 的主语依存关系识别。",
        ))

    copulas = [word for word in children.get(root.id, []) if word.deprel == "cop"]
    main_predicate_ids = _predicate_ids(root, words, children)
    if copulas:
        copula_ids = {word.id for word in copulas}
        copula_ids.update(word.id for word in children.get(root.id, []) if word.deprel == "advmod" and word.lemma in {"not", "never"})
        components.append(_component(
            _span_text(source, words_by_id, copula_ids), "V", copula_ids,
            "系动词及其否定成分构成谓语。",
        ))
        excluded = copula_ids | ({subject.id} if subject else set())
        complement_ids = _descendant_ids(root.id, children) - excluded
        for child in children.get(root.id, []):
            if child.deprel in CLAUSE_RELATIONS or child.deprel in {"obl", "punct"}:
                complement_ids -= _descendant_ids(child.id, children)
        complement_ids.discard(root.id) if root.upos == "PUNCT" else None
        complement_ids.add(root.id)
        components.append(_component(
            _span_text(source, words_by_id, complement_ids), "SC", complement_ids,
            "说明主语的身份、性质或状态。",
        ))
    else:
        components.append(_component(
            _span_text(source, words_by_id, main_predicate_ids), "V", main_predicate_ids,
            "包含限定助动词、被动标记以及共享助动词的并列谓语。",
        ))

    iobjects = [word for word in children.get(root.id, []) if word.deprel == "iobj"]
    objects = [word for word in children.get(root.id, []) if word.deprel == "obj"]
    xcomps = [word for word in children.get(root.id, []) if word.deprel == "xcomp"]
    for item in iobjects:
        ids = _descendant_ids(item.id, children)
        role = "O" if xcomps else "IO"
        explanation = "后面带有开放补语，当前成分是宾补结构中的宾语。" if role == "O" else "动作的接受者，依存关系为间接宾语。"
        components.append(_component(_span_text(source, words_by_id, ids), role, ids, explanation))
    for item in objects:
        ids = _descendant_ids(item.id, children)
        role = "DO" if iobjects and not xcomps else "O"
        components.append(_component(_span_text(source, words_by_id, ids), role, ids, "动作直接涉及的人或事物。"))
    for item in xcomps:
        ids = _descendant_ids(item.id, children)
        role = "OC" if objects or iobjects else "C"
        explanation = "说明宾语要做什么或处于什么状态，宾语与其构成逻辑主谓。" if role == "OC" else "补充谓语的内容。"
        components.append(_component(_span_text(source, words_by_id, ids), role, ids, explanation))

    occupied_ids = {word_id for component in components for word_id in component["_word_ids"]}
    for adverbial in sorted((word for word in direct_adv if word.start_char >= root.start_char), key=lambda item: item.start_char):
        ids = _descendant_ids(adverbial.id, children)
        if ids & occupied_ids:
            continue
        components.append(_component(
            _span_text(source, words_by_id, ids), "Adv", ids,
            "修饰主句谓语，说明方式、地点、范围或伴随信息。",
        ))

    components.sort(key=lambda item: min((words_by_id[word_id].start_char for word_id in item["_word_ids"]), default=10**9))

    predicates: list[dict[str, Any]] = []
    predicate_heads = [root]
    predicate_heads.extend(word for word in words if word.deprel in CLAUSE_RELATIONS and _finite_head(word, children))
    predicate_heads.extend(word for word in words if _independent_clause_head(word, children))
    seen_predicate_ids: set[tuple[int, ...]] = set()
    for head in predicate_heads:
        info = _predicate_info(source, head, words, children)
        key = tuple(info["_word_ids"])
        if key not in seen_predicate_ids:
            predicates.append(info)
            seen_predicate_ids.add(key)

    clauses: list[dict[str, Any]] = []
    for head in words:
        subordinate = head.deprel in CLAUSE_RELATIONS and _finite_head(head, children)
        independent = _independent_clause_head(head, children)
        if not subordinate and not independent:
            continue
        ids = _descendant_ids(head.id, children)
        marker = next((word for word in words if word.id in ids and (word.deprel == "mark" or word.lemma in {"that", "who", "which", "whom", "whose", "where", "when", "why"})), None)
        marker_text = marker.text if marker else ""
        if independent:
            why_ellipsis = any(
                child.lemma == "why" and child.deprel == "advmod"
                for child in children.get(head.id, [])
            )
            if why_ellipsis:
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
        })

    predicate_word_ids = {word_id for item in predicates for word_id in item["_word_ids"]}
    non_finite: list[dict[str, Any]] = []
    for word in words:
        feats = word.feats or ""
        if word.id in predicate_word_ids or word.upos not in {"VERB", "AUX"}:
            continue
        if not any(flag in feats for flag in {"VerbForm=Inf", "VerbForm=Ger", "VerbForm=Part"}):
            continue
        marker = next((child for child in children.get(word.id, []) if child.deprel == "mark" and child.lemma == "to"), None)
        ids = {word.id} | ({marker.id} if marker else set())
        form = "to do" if marker else ("doing" if "VerbForm=Ger" in feats else "done/分词")
        function = "宾语补足语" if word.deprel == "xcomp" and (objects or iobjects) else "非谓语修饰或补充成分"
        logical_subject_head = (objects or iobjects)[0] if (objects or iobjects) else None
        logical_subject = _span_text(source, words_by_id, _descendant_ids(logical_subject_head.id, children)) if function == "宾语补足语" and logical_subject_head else ""
        non_finite.append({
            "text": _span_text(source, words_by_id, ids),
            "form": form,
            "function": function,
            "logical_subject": logical_subject,
        })

    word_classes, raw_word_classes = _teaching_word_classes(source, sentence, words, children)

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
        "components": cleaned_components,
        "predicates": cleaned_predicates,
        "clauses": clauses,
        "non_finite": non_finite,
        "word_classes": word_classes,
        "raw_word_classes": raw_word_classes,
        "explanations": [
            "Stanza 先生成依存树和成分树，再映射为主谓宾补定状同。",
            "判断顺序：有限谓语 → 连接词与标点 → 主句主干 → 从句和修饰成分。",
        ],
        "warnings": [],
        "confidence": 0.9 if not clauses else 0.87,
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
        "components": [],
        "predicates": [],
        "clauses": [],
        "non_finite": [],
        "word_classes": [],
        "explanations": ["Stanza 已先自动分句，再分别分析每句话。"],
        "warnings": [],
        "confidence": round(mean(float(item["confidence"]) for item in analyses), 2),
        "sentence_analyses": analyses,
        "prompt_version": prompt_version,
    }
