from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
CACHE_PATH = BASE_DIR / "sentence_blueprint_cache.sqlite3"
PROMPT_VERSION = "2026-08-19-stanza-v4-discourse-and-independent-clauses"

DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "stanza",
    "api_url": "",
    "model": "",
    "api_key_env": "SBP_API_KEY",
    "timeout_seconds": 90,
    "host": "127.0.0.1",
    "port": 8765,
    "stanza_model_dir": r"D:\sentence-blueprint-runtime\stanza_resources",
    "stanza_processors": "tokenize,pos,lemma,depparse,constituency",
    "stanza_use_gpu": False,
}

STANZA_PIPELINE: Any | None = None
STANZA_PIPELINE_KEY = ""
STANZA_LOCK = threading.RLock()

TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:\.\d+)?|[^\w\s]", re.UNICODE)

DETERMINERS = {
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "his",
    "her", "its", "our", "their", "some", "any", "each", "every", "either",
    "neither", "much", "many", "few", "little", "several", "all", "both", "no",
}
PRONOUNS = {
    "i", "me", "you", "he", "him", "she", "her", "it", "we", "us", "they", "them",
    "who", "whom", "whose", "which", "what", "someone", "somebody", "something",
    "everyone", "everybody", "everything", "nobody", "nothing", "one", "ones",
}
POSSESSIVE_PRONOUNS = {"mine", "yours", "his", "hers", "ours", "theirs"}
MODALS = {
    "can", "could", "may", "might", "must", "shall", "should", "will", "would",
    "ought", "need", "dare",
}
BE_FORMS = {"am", "is", "are", "was", "were", "be", "been", "being"}
HAVE_FORMS = {"have", "has", "had"}
DO_FORMS = {"do", "does", "did"}
AUXILIARIES = MODALS | BE_FORMS | HAVE_FORMS | DO_FORMS

COORDINATORS = {"and", "but", "or", "nor", "yet", "so"}
ADVERBIAL_MARKERS = {
    "because": "原因状语从句",
    "although": "让步状语从句",
    "though": "让步状语从句",
    "unless": "条件状语从句",
    "while": "时间/对比状语从句",
    "when": "时间状语从句",
    "whenever": "时间状语从句",
    "before": "时间状语从句",
    "after": "时间状语从句",
    "until": "时间状语从句",
    "since": "时间/原因状语从句",
    "if": "条件状语从句",
    "once": "时间状语从句",
    "wherever": "地点状语从句",
    "where": "地点状语从句",
    "as": "方式/时间/原因状语从句",
}
RELATIVE_MARKERS = {"who", "whom", "whose", "which", "that", "where", "when", "why"}
NOUN_CLAUSE_MARKERS = {"that", "whether", "if", "what", "who", "whom", "which", "whose", "how", "why", "where", "when"}
PREPOSITIONS = {
    "about", "above", "across", "after", "against", "along", "among", "around", "at",
    "before", "behind", "below", "beside", "between", "beyond", "by", "despite", "during",
    "for", "from", "in", "inside", "into", "like", "near", "of", "off", "on", "onto",
    "out", "outside", "over", "past", "since", "through", "throughout", "to", "toward",
    "under", "until", "up", "upon", "with", "within", "without",
}

COMMON_VERBS = {
    "accept", "achieve", "agree", "allow", "answer", "appear", "ask", "become", "begin",
    "believe", "borrow", "bring", "build", "buy", "call", "cause", "change", "choose",
    "come", "consider", "continue", "create", "cut", "decide", "develop", "discover",
    "discuss", "do", "elect", "enable", "encourage", "enjoy", "expect", "explain", "fail",
    "feel", "find", "finish", "follow", "forget", "get", "give", "go", "grow", "happen",
    "have", "hear", "help", "hold", "hope", "improve", "invite", "keep", "know", "learn",
    "leave", "lend", "let", "like", "listen", "live", "look", "love", "make", "mean",
    "meet", "move", "need", "offer", "open", "order", "pass", "play", "prefer", "prevent",
    "promise", "protect", "prove", "read", "realize", "recommend", "remain", "remember",
    "reply", "require", "review", "run", "say", "see", "seem", "send", "show", "sing",
    "smell", "sound", "speak", "spend", "stand", "start", "stay", "stop", "study", "suggest",
    "take", "taste", "teach", "tell", "think", "travel", "try", "turn", "understand", "use",
    "visit", "wait", "walk", "want", "watch", "work", "write",
}

IRREGULAR_LEMMAS = {
    "bought": "buy", "brought": "bring", "built": "build", "came": "come", "cut": "cut",
    "did": "do", "done": "do", "felt": "feel", "forgot": "forget", "forgotten": "forget",
    "found": "find", "gave": "give", "given": "give", "gone": "go", "grew": "grow",
    "had": "have", "heard": "hear", "held": "hold", "kept": "keep", "knew": "know",
    "known": "know", "left": "leave", "lent": "lend", "made": "make", "met": "meet",
    "read": "read", "ran": "run", "said": "say", "saw": "see", "seen": "see",
    "sent": "send", "spoke": "speak", "spoken": "speak", "stood": "stand", "taught": "teach",
    "thought": "think", "told": "tell", "took": "take", "taken": "take", "went": "go",
    "wrote": "write", "written": "write",
}

LINKING_VERBS = {
    "be", "become", "seem", "appear", "feel", "look", "sound", "taste", "smell", "remain",
    "stay", "grow", "turn", "prove", "get",
}
OBJECT_CONTROL_VERBS = {
    "ask", "tell", "want", "expect", "allow", "enable", "encourage", "invite", "force",
    "teach", "remind", "advise", "persuade", "help", "order", "require", "cause",
}
DITRANSITIVE_VERBS = {
    "give", "tell", "show", "send", "offer", "lend", "teach", "buy", "bring", "write",
    "promise", "pass", "hand", "cost", "save", "make",
}
OBJECT_COMPLEMENT_VERBS = {"make", "keep", "find", "consider", "elect", "call", "name", "paint", "leave", "have"}
INTRANSITIVE_VERBS = {"arrive", "come", "cry", "die", "fall", "go", "happen", "laugh", "rise", "run", "smile", "wait"}

KNOWN_ADVERBS = {
    "aloud", "already", "always", "carefully", "early", "fast", "hard", "here", "never",
    "not", "now", "often", "quickly", "quietly", "really", "slowly", "soon", "still",
    "there", "together", "usually", "very", "well", "yesterday", "today", "tomorrow",
}
KNOWN_ADJECTIVES = {
    "able", "afraid", "beautiful", "beneficial", "careful", "clear", "difficult", "easy",
    "excited", "famous", "free", "good", "happy", "hard", "important", "kind", "late",
    "necessary", "new", "open", "possible", "quiet", "ready", "sad", "successful", "sure",
    "useful", "young",
}
TIME_WORDS = {
    "morning", "afternoon", "evening", "night", "day", "week", "month", "year", "minute",
    "minutes", "hour", "hours", "test", "exam", "examination", "deadline", "today", "tomorrow",
    "yesterday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}

POS_ZH = {
    "NOUN": "名词", "PROPN": "专有名词", "PRON": "代词", "VERB": "动词",
    "AUX": "助动词/情态动词", "ADJ": "形容词", "ADV": "副词", "ADP": "介词",
    "DET": "限定词", "CCONJ": "并列连词", "SCONJ": "从属连接词", "NUM": "数词",
    "PUNCT": "标点", "PART": "小品词",
}


@dataclass(frozen=True)
class Token:
    text: str
    lower: str
    start: int
    end: int
    index: int


def load_config() -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            config.update(loaded)

    config["provider"] = os.getenv("SBP_PROVIDER", str(config["provider"]))
    config["api_url"] = os.getenv("SBP_API_URL", str(config["api_url"]))
    config["model"] = os.getenv("SBP_MODEL", str(config["model"]))
    config["stanza_model_dir"] = os.getenv("SBP_STANZA_MODEL_DIR", str(config["stanza_model_dir"]))
    return config


def init_cache() -> None:
    with sqlite3.connect(CACHE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                cache_key TEXT PRIMARY KEY,
                sentence TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )


def cache_key(sentence: str, config: dict[str, Any]) -> str:
    source = "|".join(
        [
            PROMPT_VERSION,
            str(config.get("provider", "heuristic")),
            str(config.get("model", "")),
            str(config.get("stanza_model_dir", "")),
            str(config.get("stanza_processors", "")),
            sentence,
        ]
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def get_cached(key: str) -> dict[str, Any] | None:
    with sqlite3.connect(CACHE_PATH) as connection:
        row = connection.execute(
            "SELECT result_json FROM analyses WHERE cache_key = ?", (key,)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def put_cached(key: str, sentence: str, config: dict[str, Any], result: dict[str, Any]) -> None:
    with sqlite3.connect(CACHE_PATH) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO analyses
              (cache_key, sentence, provider, model, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                sentence,
                str(config.get("provider", "heuristic")),
                str(config.get("model", "")),
                json.dumps(result, ensure_ascii=False),
                int(time.time()),
            ),
        )


def tokenize(sentence: str) -> list[Token]:
    return [
        Token(match.group(0), match.group(0).lower(), match.start(), match.end(), index)
        for index, match in enumerate(TOKEN_RE.finditer(sentence))
    ]


def lemma_candidates(word: str) -> set[str]:
    lower = word.lower()
    values = {lower}
    if lower in IRREGULAR_LEMMAS:
        values.add(IRREGULAR_LEMMAS[lower])
    if lower.endswith("ies") and len(lower) > 4:
        values.add(lower[:-3] + "y")
    if lower.endswith("ied") and len(lower) > 4:
        values.add(lower[:-3] + "y")
    if lower.endswith("ing") and len(lower) > 5:
        stem = lower[:-3]
        values.add(stem)
        values.add(stem + "e")
        if len(stem) > 2 and stem[-1] == stem[-2]:
            values.add(stem[:-1])
    if lower.endswith("ed") and len(lower) > 4:
        stem = lower[:-2]
        values.add(stem)
        values.add(stem + "e")
        if len(stem) > 2 and stem[-1] == stem[-2]:
            values.add(stem[:-1])
    if lower.endswith("es") and len(lower) > 3:
        values.add(lower[:-2])
        values.add(lower[:-1])
    if lower.endswith("s") and len(lower) > 3:
        values.add(lower[:-1])
    return values


def lemma_of(word: str) -> str:
    candidates = lemma_candidates(word)
    for candidate in candidates:
        if candidate in COMMON_VERBS or candidate in LINKING_VERBS:
            return candidate
    return IRREGULAR_LEMMAS.get(word.lower(), word.lower())


def looks_like_verb(token: Token) -> bool:
    if token.lower in AUXILIARIES:
        return True
    if lemma_candidates(token.lower) & COMMON_VERBS:
        return True
    return token.lower.endswith(("ing", "ed", "en")) and len(token.lower) > 4


def marker_starts_clause(tokens: list[Token], index: int) -> bool:
    """A subordinating word starts a clause only when a finite predicate follows it."""
    for cursor in range(index + 1, min(len(tokens), index + 14)):
        if tokens[cursor].text in {",", ";", ".", "?", "!"}:
            break
        if is_finite_start(tokens, cursor):
            return True
    return False


def guess_pos(tokens: list[Token], index: int) -> str:
    token = tokens[index]
    lower = token.lower
    previous = tokens[index - 1].lower if index else ""

    if not re.search(r"[A-Za-z0-9]", token.text):
        return "PUNCT"
    if token.text.isdigit() or re.fullmatch(r"\d+(?:\.\d+)?", token.text):
        return "NUM"
    if lower in DETERMINERS:
        return "DET"
    if lower in PRONOUNS or lower in POSSESSIVE_PRONOUNS:
        return "PRON"
    if lower in COORDINATORS:
        return "CCONJ"
    if lower in PREPOSITIONS and lower in ADVERBIAL_MARKERS and not marker_starts_clause(tokens, index):
        return "ADP"
    if lower in ADVERBIAL_MARKERS or lower in {"whether", "though", "although", "unless"}:
        return "SCONJ"
    if lower in PREPOSITIONS:
        return "PART" if lower == "to" and index + 1 < len(tokens) and looks_like_verb(tokens[index + 1]) else "ADP"
    if lower in AUXILIARIES:
        return "AUX"
    if previous == "to" or looks_like_verb(token):
        return "VERB"
    if lower in KNOWN_ADVERBS or (lower.endswith("ly") and lower not in {"friendly", "lovely"}):
        return "ADV"
    if lower in KNOWN_ADJECTIVES or lower.endswith(("ous", "ful", "less", "able", "ible", "ive", "al", "ic")):
        return "ADJ"
    if token.text[:1].isupper() and index > 0:
        return "PROPN"
    return "NOUN"


def is_finite_start(tokens: list[Token], index: int) -> bool:
    token = tokens[index]
    if index and tokens[index - 1].lower == "to":
        return False
    if token.lower.endswith("ing"):
        return False
    if token.lower in AUXILIARIES:
        return True
    return bool(lemma_candidates(token.lower) & COMMON_VERBS)


def find_predicates(tokens: list[Token]) -> list[dict[str, Any]]:
    predicates: list[dict[str, Any]] = []
    used: set[int] = set()
    index = 0

    while index < len(tokens):
        if index in used or not is_finite_start(tokens, index):
            index += 1
            continue

        start = index
        end = index
        if tokens[index].lower in AUXILIARIES:
            cursor = index + 1
            found_lexical = False
            while cursor < len(tokens):
                current = tokens[cursor]
                if current.lower in {"not", "never", "already", "still", "just"}:
                    end = cursor
                    cursor += 1
                    continue
                if current.lower in AUXILIARIES or looks_like_verb(current):
                    end = cursor
                    found_lexical = current.lower not in AUXILIARIES
                    cursor += 1
                    continue
                break
            if not found_lexical and tokens[start].lower not in BE_FORMS:
                end = start

        for used_index in range(start, end + 1):
            used.add(used_index)

        words = [tokens[i].lower for i in range(start, end + 1)]
        text = " ".join(tokens[i].text for i in range(start, end + 1))
        lexical_word = next(
            (tokens[i].text for i in range(end, start - 1, -1) if tokens[i].lower not in AUXILIARIES and tokens[i].lower not in {"not", "never"}),
            tokens[end].text,
        )
        lemma = lemma_of(lexical_word)
        tense = "一般现在时"
        voice = "主动"
        kind = "实义动词谓语"

        if any(word in MODALS for word in words):
            tense = "情态动词结构"
        elif any(word in {"was", "were", "had", "did"} for word in words) or tokens[start].lower in IRREGULAR_LEMMAS or tokens[start].lower.endswith("ed"):
            tense = "过去时间结构"
        if any(word in HAVE_FORMS for word in words) and len(words) > 1:
            tense = f"{tense} · 完成结构"
        if any(word in BE_FORMS for word in words) and any(word.endswith("ing") for word in words):
            tense = f"{tense} · 进行结构"
        if any(word in BE_FORMS for word in words) and any(word.endswith(("ed", "en")) or word in IRREGULAR_LEMMAS for word in words[1:]):
            voice = "被动"
        if lemma in LINKING_VERBS and len(words) == 1:
            kind = "系动词谓语"

        predicates.append(
            {
                "text": text,
                "start": start,
                "end": end,
                "lemma": lemma,
                "tense": tense,
                "voice": voice,
                "type": kind,
            }
        )
        index = end + 1

    return predicates


def token_text(tokens: list[Token], start: int, end: int) -> str:
    if start > end or start < 0 or end >= len(tokens):
        return ""
    pieces: list[str] = []
    for index in range(start, end + 1):
        text = tokens[index].text
        if pieces and re.fullmatch(r"[,.;:!?)]", text):
            pieces[-1] += text
        elif text == "(" or not pieces:
            pieces.append(text)
        else:
            pieces.append(" " + text)
    return "".join(pieces).strip()


def trim_punctuation(tokens: list[Token], start: int, end: int) -> tuple[int, int]:
    while start <= end and guess_pos(tokens, start) == "PUNCT":
        start += 1
    while end >= start and guess_pos(tokens, end) == "PUNCT":
        end -= 1
    return start, end


def find_main_start_and_predicate(tokens: list[Token], predicates: list[dict[str, Any]]) -> tuple[int, dict[str, Any] | None]:
    if not predicates:
        return 0, None
    comma_index = next((token.index for token in tokens if token.text in {",", ";"}), None)
    leading_is_modifier = bool(tokens) and (
        tokens[0].lower in ADVERBIAL_MARKERS
        or tokens[0].lower == "to"
        or tokens[0].lower.endswith("ing")
        or tokens[0].lower.endswith("ed")
    )
    if comma_index is not None and leading_is_modifier:
        main = next((item for item in predicates if item["start"] > comma_index), predicates[-1])
        return comma_index + 1, main
    return 0, predicates[0]


def find_trailing_adverbial(tokens: list[Token], start: int, end: int) -> int | None:
    for index in range(start, end + 1):
        lower = tokens[index].lower
        next_lower = tokens[index + 1].lower if index < end else ""
        if lower in {"because", "although", "though", "unless", "while", "whenever", "wherever"}:
            return index
        if lower in {"before", "after", "during", "until", "throughout", "despite"}:
            return index
        if lower in {"today", "tomorrow", "yesterday", "every"}:
            return index
        if lower in {"at", "on", "in", "for", "by"} and next_lower in TIME_WORDS:
            return index
    return None


def split_first_noun_phrase(tokens: list[Token], start: int, end: int) -> int | None:
    if start > end:
        return None
    if guess_pos(tokens, start) == "PRON":
        return start + 1 if start + 1 <= end else None
    for index in range(start + 1, end + 1):
        if tokens[index].lower in DETERMINERS:
            return index
    return None


def component(tokens: list[Token], start: int, end: int, role: str, explanation: str) -> dict[str, Any] | None:
    start, end = trim_punctuation(tokens, start, end)
    if start > end:
        return None
    return {
        "text": token_text(tokens, start, end),
        "role": role,
        "label": role,
        "explanation": explanation,
        "token_start": start,
        "token_end": end,
    }


def build_components(tokens: list[Token], predicates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, list[str], float]:
    components: list[dict[str, Any]] = []
    warnings: list[str] = []
    confidence = 0.78
    main_start, main_predicate = find_main_start_and_predicate(tokens, predicates)

    if main_predicate is None:
        warnings.append("内置规则没有可靠找到有限谓语，建议开启 AI 复核。")
        return components, "待判断", warnings, 0.35

    if main_start > 0:
        leading = component(tokens, 0, main_start - 1, "Adv", "句首修饰部分，先暂时拿掉再找主句主干。")
        if leading:
            components.append(leading)

    subject = component(
        tokens,
        main_start,
        main_predicate["start"] - 1,
        "S",
        "位于主句谓语之前，是动作发出者或状态主体。",
    )
    if subject:
        components.append(subject)

    predicate_component = component(
        tokens,
        main_predicate["start"],
        main_predicate["end"],
        "V",
        "这是带时态、语态并与主语呼应的完整谓语组。",
    )
    if predicate_component:
        components.append(predicate_component)

    sentence_end = len(tokens) - 1
    while sentence_end >= 0 and guess_pos(tokens, sentence_end) == "PUNCT":
        sentence_end -= 1
    rest_start = main_predicate["end"] + 1
    if rest_start > sentence_end:
        return components, "SV", warnings, confidence

    adverbial_start = find_trailing_adverbial(tokens, rest_start, sentence_end)
    core_end = adverbial_start - 1 if adverbial_start is not None else sentence_end
    lemma = main_predicate["lemma"]
    pattern = "SVO"

    if lemma in OBJECT_CONTROL_VERBS:
        to_index = next(
            (index for index in range(rest_start, core_end + 1) if tokens[index].lower == "to" and index + 1 <= core_end and looks_like_verb(tokens[index + 1])),
            None,
        )
        if to_index is not None and to_index > rest_start:
            obj = component(tokens, rest_start, to_index - 1, "O", "谓语动作直接涉及的对象。")
            oc = component(
                tokens,
                to_index,
                core_end,
                "OC",
                "不定式补充说明宾语所执行的动作；前面的宾语是该动作的逻辑主语。",
            )
            if obj:
                components.append(obj)
            if oc:
                components.append(oc)
            pattern = "SVOC"
        else:
            obj = component(tokens, rest_start, core_end, "O", "谓语动作涉及的对象。")
            if obj:
                components.append(obj)

    elif lemma in LINKING_VERBS:
        comp = component(tokens, rest_start, core_end, "SC", "位于系动词后，说明主语的身份、性质或状态。")
        if comp:
            components.append(comp)
        pattern = "SVC"

    elif lemma in OBJECT_COMPLEMENT_VERBS:
        split = split_first_noun_phrase(tokens, rest_start, core_end)
        if split is not None:
            second_pos = guess_pos(tokens, split)
            is_clear_object_complement = lemma in {"elect", "call", "name", "consider", "keep", "find", "paint", "leave", "have"} or second_pos in {"ADJ", "VERB"}
            if is_clear_object_complement:
                obj = component(tokens, rest_start, split - 1, "O", "谓语动作直接涉及的对象。")
                oc = component(tokens, split, core_end, "OC", "补充说明前面宾语的状态、身份或动作。")
                if obj:
                    components.append(obj)
                if oc:
                    components.append(oc)
                pattern = "SVOC"
            else:
                io = component(tokens, rest_start, split - 1, "IO", "动作的接受者，常可改写为 to/for + 人。")
                do = component(tokens, split, core_end, "DO", "动作直接涉及的事物。")
                if io:
                    components.append(io)
                if do:
                    components.append(do)
                pattern = "SVOO"
                if lemma == "make":
                    warnings.append("make + 人 + 名词可能是双宾语，也可能是宾补；内置规则按当前词形给出初判。")
                    confidence -= 0.08
        else:
            obj = component(tokens, rest_start, core_end, "O", "谓语动作涉及的对象。")
            if obj:
                components.append(obj)

    elif lemma in DITRANSITIVE_VERBS:
        split = split_first_noun_phrase(tokens, rest_start, core_end)
        if split is not None:
            io = component(tokens, rest_start, split - 1, "IO", "动作的接受者，常可改写为 to/for + 人。")
            do = component(tokens, split, core_end, "DO", "动作直接涉及的事物。")
            if io:
                components.append(io)
            if do:
                components.append(do)
            pattern = "SVOO"
        else:
            obj = component(tokens, rest_start, core_end, "O", "谓语动作涉及的对象。")
            if obj:
                components.append(obj)

    elif lemma in INTRANSITIVE_VERBS or core_end < rest_start:
        if core_end >= rest_start:
            adv = component(tokens, rest_start, core_end, "Adv", "修饰谓语动作的方式、时间、地点或程度。")
            if adv:
                components.append(adv)
        pattern = "SV"

    else:
        first_pos = guess_pos(tokens, rest_start)
        if first_pos == "ADV":
            adv = component(tokens, rest_start, core_end, "Adv", "修饰谓语动作的方式、时间或程度。")
            if adv:
                components.append(adv)
            pattern = "SV"
        else:
            obj = component(tokens, rest_start, core_end, "O", "谓语动作涉及的对象。")
            if obj:
                components.append(obj)
            pattern = "SVO"

    if adverbial_start is not None:
        adv = component(tokens, adverbial_start, sentence_end, "Adv", "修饰动作或整句，表示时间、原因、条件等背景。")
        if adv:
            components.append(adv)

    if len(predicates) > 1:
        confidence -= 0.1
        warnings.append("检测到多套谓语；内置规则已先保留主句主干，复杂从句建议使用 AI 复核。")

    return components, pattern, warnings, max(0.35, min(confidence, 0.9))


def detect_clauses(tokens: list[Token]) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        lower = token.lower
        if lower in COORDINATORS:
            clauses.append(
                {
                    "text": token.text,
                    "type": "并列连接",
                    "function": "连接并列词、短语或分句",
                    "marker": token.text,
                }
            )
            continue
        if lower not in ADVERBIAL_MARKERS and lower not in NOUN_CLAUSE_MARKERS:
            continue
        if lower in PREPOSITIONS and not marker_starts_clause(tokens, index):
            continue

        end = len(tokens) - 1
        for cursor in range(index + 1, len(tokens)):
            if tokens[cursor].text in {";", ".", "?", "!"}:
                end = cursor - 1
                break
        text = token_text(tokens, index, end)

        preceding_has_noun = any(guess_pos(tokens, cursor) in {"NOUN", "PROPN", "PRON"} for cursor in range(max(0, index - 3), index))
        if lower in RELATIVE_MARKERS and preceding_has_noun:
            clause_type = "定语从句"
            function = "修饰前面的先行词"
        elif lower in ADVERBIAL_MARKERS:
            clause_type = ADVERBIAL_MARKERS[lower]
            function = "状语"
        else:
            clause_type = "名词性从句"
            function = "在主句中承担名词性成分"
        clauses.append({"text": text, "type": clause_type, "function": function, "marker": token.text})
    return clauses


def detect_non_finite(tokens: list[Token], predicates: list[dict[str, Any]], components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    predicate_indices = {
        index
        for item in predicates
        for index in range(int(item["start"]), int(item["end"]) + 1)
    }
    results: list[dict[str, Any]] = []

    def component_for(index: int) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in components
                if int(item.get("token_start", -1)) <= index <= int(item.get("token_end", -1))
            ),
            None,
        )

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.lower == "to" and index + 1 < len(tokens) and looks_like_verb(tokens[index + 1]):
            owner = component_for(index)
            logical_subject = ""
            if owner and owner.get("role") == "OC":
                object_component = next((item for item in components if item.get("role") == "O"), None)
                logical_subject = object_component.get("text", "") if object_component else ""
            results.append(
                {
                    "text": f"to {tokens[index + 1].text}",
                    "form": "不定式 to do",
                    "function": ROLE_FUNCTIONS.get(owner.get("role"), "非谓语成分") if owner else "非谓语成分",
                    "logical_subject": logical_subject,
                }
            )
            index += 2
            continue

        if index not in predicate_indices and token.lower.endswith("ing") and looks_like_verb(token):
            owner = component_for(index)
            form = "动名词/现在分词 doing"
            results.append(
                {
                    "text": token.text,
                    "form": form,
                    "function": ROLE_FUNCTIONS.get(owner.get("role"), "待结合位置判断") if owner else "待结合位置判断",
                    "logical_subject": "",
                }
            )
        elif index not in predicate_indices and token.lower.endswith(("ed", "en")) and looks_like_verb(token):
            owner = component_for(index)
            results.append(
                {
                    "text": token.text,
                    "form": "过去分词 done",
                    "function": ROLE_FUNCTIONS.get(owner.get("role"), "待结合位置判断") if owner else "待结合位置判断",
                    "logical_subject": "",
                }
            )
        index += 1
    return results


ROLE_FUNCTIONS = {
    "S": "作主语",
    "O": "作宾语",
    "IO": "作间接宾语",
    "DO": "作直接宾语",
    "SC": "作表语/主语补足语",
    "OC": "作宾语补足语",
    "Atr": "作定语",
    "Adv": "作状语",
    "App": "作同位语",
}


def build_word_classes(
    tokens: list[Token], predicates: list[dict[str, Any]], components: list[dict[str, Any]]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    predicate_indices = {
        index
        for item in predicates
        for index in range(int(item["start"]), int(item["end"]) + 1)
    }
    for index, token in enumerate(tokens):
        pos = guess_pos(tokens, index)
        if pos == "PUNCT":
            continue
        owner = next(
            (
                item
                for item in components
                if int(item.get("token_start", -1)) <= index <= int(item.get("token_end", -1))
            ),
            None,
        )
        form = ""
        if index in predicate_indices:
            form = "有限谓语/谓语组的一部分"
        elif token.lower == "to" and index + 1 < len(tokens) and looks_like_verb(tokens[index + 1]):
            form = "不定式标记"
        elif token.lower.endswith("ing") and pos == "VERB":
            form = "doing"
        elif token.lower.endswith(("ed", "en")) and pos == "VERB":
            form = "done/过去式待结合谓语判断"
        rows.append(
            {
                "text": token.text,
                "pos": POS_ZH.get(pos, pos),
                "form": form,
                "function": ROLE_FUNCTIONS.get(owner.get("role"), owner.get("role", "")) if owner else "",
            }
        )
    return rows


def analyze_heuristic(sentence: str) -> dict[str, Any]:
    tokens = tokenize(sentence)
    predicates = find_predicates(tokens)
    components, pattern, warnings, confidence = build_components(tokens, predicates)
    clauses = detect_clauses(tokens)
    non_finite = detect_non_finite(tokens, predicates, components)
    word_classes = build_word_classes(tokens, predicates, components)

    main_components = [item for item in components if item["role"] not in {"Adv", "Atr", "App", "Conj"}]
    skeleton = " + ".join(item["text"] for item in main_components)
    predicate_text = "、".join(item["text"] for item in predicates) or "未可靠识别"
    explanations = [
        f"先圈出有限谓语：{predicate_text}。",
        "再用连词和标点分割主从句，暂时拿掉定语、状语、同位语。",
        f"保留下来的主干为：{skeleton or '待判断'}。",
    ]
    if pattern == "SVOC":
        explanations.append("宾语与宾补之间存在逻辑主谓关系：宾语是后面状态或动作的主体。")
    if pattern == "SVOO":
        explanations.append("两个宾语彼此不构成主谓关系，前者通常是接受者，后者是事物。")
    if confidence < 0.7 and not any("AI" in warning for warning in warnings):
        warnings.append("该句存在歧义，建议在 config.json 中启用 AI 复核。")

    return {
        "sentence": sentence,
        "analysis_method": "内置规则",
        "pattern": pattern,
        "skeleton": skeleton,
        "components": [{key: value for key, value in item.items() if not key.startswith("token_")} for item in components],
        "predicates": [{key: value for key, value in item.items() if key not in {"start", "end", "lemma"}} for item in predicates],
        "clauses": clauses,
        "non_finite": non_finite,
        "word_classes": word_classes,
        "explanations": explanations,
        "warnings": warnings,
        "confidence": round(confidence, 2),
        "prompt_version": PROMPT_VERSION,
    }


def system_prompt() -> str:
    return """
你是英语句子结构分析器。只输出一个合法 JSON 对象，不要输出 Markdown。

固定分析顺序：
1. 圈出全部有限谓语组，助动词、情态动词、否定词和实义动词要合并，如 must have forgotten、did not reply。
2. 找并列连词、从属连词、关系词和标点，切分各套主谓。
3. 保留主句主干，再放回从句、非谓语、定语、状语和同位语。
4. 不要混淆词性、动词形态和句子成分。非谓语不是一种词性。
5. 双宾语与宾补：宾语与宾补能形成逻辑主谓关系；两个宾语之间不能。
6. 翻译按逻辑组，不逐词硬译。本插件已有上方译文，translation 可为空。

role 只能使用：S, V, O, IO, DO, SC, OC, Atr, Adv, App, Conj。
components 中的 text 必须原样摘自输入，按原句顺序排列。谓语组必须完整。

返回结构：
{
  "pattern": "SV/SVO/SVC/SVOO/SVOC/复合句",
  "skeleton": "主句最小主干",
  "components": [{"text":"", "role":"S", "label":"主语", "explanation":""}],
  "predicates": [{"text":"", "tense":"", "voice":"", "type":""}],
  "clauses": [{"text":"", "type":"", "function":"", "marker":""}],
  "non_finite": [{"text":"", "form":"", "function":"", "logical_subject":""}],
  "word_classes": [{"text":"", "pos":"", "form":"", "function":""}],
  "explanations": [""],
  "warnings": [""],
  "confidence": 0.0
}
""".strip()


def strip_json_fence(content: str) -> str:
    value = content.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    first = value.find("{")
    last = value.rfind("}")
    return value[first:last + 1] if first >= 0 and last > first else value


def normalize_ai_result(sentence: str, result: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "sentence": sentence,
        "analysis_method": "AI 复核",
        "pattern": str(result.get("pattern") or "待判断"),
        "skeleton": str(result.get("skeleton") or ""),
        "components": result.get("components") if isinstance(result.get("components"), list) else [],
        "predicates": result.get("predicates") if isinstance(result.get("predicates"), list) else [],
        "clauses": result.get("clauses") if isinstance(result.get("clauses"), list) else [],
        "non_finite": result.get("non_finite") if isinstance(result.get("non_finite"), list) else [],
        "word_classes": result.get("word_classes") if isinstance(result.get("word_classes"), list) else [],
        "explanations": result.get("explanations") if isinstance(result.get("explanations"), list) else [],
        "warnings": result.get("warnings") if isinstance(result.get("warnings"), list) else [],
        "confidence": max(0.0, min(float(result.get("confidence", 0.75)), 1.0)),
        "prompt_version": PROMPT_VERSION,
    }
    return normalized


def analyze_with_ai(sentence: str, config: dict[str, Any]) -> dict[str, Any]:
    api_url = str(config.get("api_url") or "").strip()
    model = str(config.get("model") or "").strip()
    if not api_url or not model:
        raise RuntimeError("AI 复核已启用，但 api_url 或 model 尚未配置")

    key_env = str(config.get("api_key_env") or "SBP_API_KEY")
    api_key = os.getenv(key_env, "").strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": sentence},
        ],
        "temperature": 0.1,
    }
    request = urllib.request.Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    timeout = float(config.get("timeout_seconds", 90))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"AI 接口返回 HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"无法连接 AI 接口：{error.reason}") from error

    try:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(strip_json_fence(content))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("AI 接口没有返回符合约定的 JSON") from error
    if not isinstance(parsed, dict):
        raise RuntimeError("AI 分析结果不是 JSON 对象")
    return normalize_ai_result(sentence, parsed)


def get_stanza_pipeline(config: dict[str, Any]) -> Any:
    global STANZA_PIPELINE, STANZA_PIPELINE_KEY
    model_dir = Path(str(config.get("stanza_model_dir") or "")).expanduser().resolve()
    processors = str(config.get("stanza_processors") or "tokenize,pos,lemma,depparse,constituency")
    use_gpu = bool(config.get("stanza_use_gpu", False))
    pipeline_key = f"{model_dir}|{processors}|{use_gpu}"

    with STANZA_LOCK:
        if STANZA_PIPELINE is not None and STANZA_PIPELINE_KEY == pipeline_key:
            return STANZA_PIPELINE
        if not model_dir.exists():
            raise RuntimeError(f"Stanza 模型目录不存在：{model_dir}")
        try:
            import stanza
        except ImportError as error:
            raise RuntimeError("当前 Python 环境未安装 stanza，请使用 D 盘专用运行环境启动") from error

        STANZA_PIPELINE = stanza.Pipeline(
            "en",
            dir=str(model_dir),
            processors=processors,
            download_method=None,
            use_gpu=use_gpu,
            verbose=False,
        )
        STANZA_PIPELINE_KEY = pipeline_key
        return STANZA_PIPELINE


def analyze_with_stanza(sentence: str, config: dict[str, Any]) -> dict[str, Any]:
    from stanza_analyzer import analyze_document

    pipeline = get_stanza_pipeline(config)
    with STANZA_LOCK:
        return analyze_document(pipeline, sentence, PROMPT_VERSION)


def analyze(sentence: str, force_refresh: bool = False) -> dict[str, Any]:
    config = load_config()
    key = cache_key(sentence, config)
    if not force_refresh:
        cached = get_cached(key)
        if cached:
            cached = dict(cached)
            cached["cached"] = True
            return cached

    provider = str(config.get("provider", "heuristic")).lower()
    if provider == "openai_compatible":
        try:
            result = analyze_with_ai(sentence, config)
        except Exception as error:  # 失败时保留可用的基础分析，不让网页第三行空白。
            result = analyze_heuristic(sentence)
            result["warnings"].append(f"AI 复核失败，已回退到内置规则：{error}")
            result["confidence"] = min(float(result["confidence"]), 0.62)
    elif provider == "stanza":
        try:
            result = analyze_with_stanza(sentence, config)
        except Exception as error:
            result = analyze_heuristic(sentence)
            result["warnings"].append(f"Stanza 分析失败，已回退到内置规则：{error}")
            result["confidence"] = min(float(result["confidence"]), 0.58)
    else:
        result = analyze_heuristic(sentence)

    result["cached"] = False
    put_cached(key, sentence, config, result)
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "SentenceBlueprint/0.2"

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format_string % args}")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/health":
            config = load_config()
            self.send_json(
                200,
                {
                    "status": "ok",
                    "provider": config.get("provider", "heuristic"),
                    "analysis_method": {
                        "openai_compatible": "AI 复核",
                        "stanza": "Stanford Stanza",
                    }.get(str(config.get("provider")), "内置规则"),
                    "stanza_model_dir": config.get("stanza_model_dir") if config.get("provider") == "stanza" else None,
                    "prompt_version": PROMPT_VERSION,
                },
            )
            return
        self.send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/analyze":
            self.send_json(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("请求正文为空或过大")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            sentence = re.sub(r"\s+", " ", str(payload.get("sentence", ""))).strip()
            if not sentence:
                raise ValueError("sentence 不能为空")
            if len(sentence) > 10_000:
                raise ValueError("句子过长")
            result = analyze(sentence, bool(payload.get("force_refresh")))
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except Exception as error:
            self.send_json(500, {"error": f"分析失败：{error}"})


def main() -> None:
    init_cache()
    config = load_config()
    if str(config.get("provider", "")).lower() == "stanza":
        print("正在加载 Stanford Stanza 英文语法模型……", flush=True)
        try:
            get_stanza_pipeline(config)
            print("Stanford Stanza 模型加载完成", flush=True)
        except Exception as error:
            print(f"Stanza 预加载失败；请求时将回退到内置规则：{error}", flush=True)
    host = str(config.get("host", "127.0.0.1"))
    port = int(config.get("port", 8765))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"句子蓝图分析服务已启动：http://{host}:{port}", flush=True)
    print(f"当前模式：{config.get('provider', 'heuristic')}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
