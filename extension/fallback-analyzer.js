(() => {
  "use strict";

  const BE = new Set(["am", "is", "are", "was", "were", "be", "been", "being"]);
  const AUX = new Set([
    ...BE,
    "have", "has", "had", "do", "does", "did", "can", "could", "may", "might",
    "must", "shall", "should", "will", "would", "need", "dare", "ought",
  ]);
  const COMMON_VERBS = new Set([
    "accept", "achieve", "add", "agree", "allow", "analyze", "appear", "ask", "become",
    "begin", "believe", "bring", "build", "buy", "call", "change", "choose", "come",
    "consider", "contain", "continue", "create", "cut", "decide", "develop", "discover",
    "discuss", "enable", "encourage", "enjoy", "expect", "explain", "fail", "feel", "find",
    "finish", "follow", "forget", "get", "give", "go", "grow", "happen", "hear", "help",
    "hold", "hope", "improve", "include", "invite", "keep", "know", "learn", "leave", "let",
    "like", "listen", "live", "look", "love", "make", "mean", "meet", "move", "need", "offer",
    "open", "order", "pass", "play", "prefer", "prevent", "promise", "protect", "prove", "read",
    "realize", "recommend", "remain", "remember", "replace", "reply", "require", "review", "run",
    "say", "see", "seem", "send", "show", "sing", "smell", "sound", "speak", "spend", "stand",
    "start", "stay", "stop", "study", "suggest", "support", "take", "taste", "teach", "tell",
    "think", "travel", "try", "turn", "understand", "use", "visit", "wait", "walk", "want",
    "watch", "work", "write",
  ]);
  const LINKING = new Set(["be", "become", "seem", "appear", "feel", "look", "sound", "taste", "smell", "remain", "stay", "grow", "turn", "prove"]);
  const OBJECT_CONTROL = new Set(["ask", "tell", "want", "expect", "allow", "enable", "encourage", "invite", "force", "teach", "remind", "help", "order", "require", "cause"]);
  const DITRANSITIVE = new Set(["give", "tell", "show", "send", "offer", "lend", "teach", "buy", "bring", "write", "promise", "pass", "make"]);
  const CONNECTORS = new Map([
    ["because", "原因状语从句"], ["although", "让步状语从句"], ["though", "让步状语从句"],
    ["if", "条件状语从句"], ["unless", "条件状语从句"], ["when", "时间状语从句"],
    ["while", "时间/对比状语从句"], ["before", "时间状语从句"], ["after", "时间状语从句"],
    ["since", "时间/原因状语从句"], ["that", "名词性从句/定语从句"], ["which", "定语从句"],
    ["who", "定语从句"], ["and", "并列连接"], ["but", "并列连接"], ["or", "并列连接"],
  ]);
  const IRREGULAR = new Map([
    ["bought", "buy"], ["brought", "bring"], ["built", "build"], ["came", "come"],
    ["did", "do"], ["done", "do"], ["felt", "feel"], ["forgot", "forget"],
    ["forgotten", "forget"], ["found", "find"], ["gave", "give"], ["given", "give"],
    ["gone", "go"], ["grew", "grow"], ["had", "have"], ["heard", "hear"],
    ["held", "hold"], ["kept", "keep"], ["knew", "know"], ["known", "know"],
    ["left", "leave"], ["made", "make"], ["met", "meet"], ["ran", "run"],
    ["said", "say"], ["saw", "see"], ["seen", "see"], ["sent", "send"],
    ["spoke", "speak"], ["spoken", "speak"], ["stood", "stand"], ["taught", "teach"],
    ["thought", "think"], ["told", "tell"], ["took", "take"], ["taken", "take"],
    ["went", "go"], ["wrote", "write"], ["written", "write"],
  ]);

  function words(text) {
    return text.match(/[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:\.\d+)?|[^\w\s]/g) || [];
  }

  function lemma(raw) {
    const word = raw.toLowerCase();
    if (IRREGULAR.has(word)) return IRREGULAR.get(word);
    if (COMMON_VERBS.has(word) || BE.has(word)) return word;
    const candidates = [];
    if (word.endsWith("ies")) candidates.push(`${word.slice(0, -3)}y`);
    if (word.endsWith("ied")) candidates.push(`${word.slice(0, -3)}y`);
    if (word.endsWith("ing")) candidates.push(word.slice(0, -3), `${word.slice(0, -3)}e`);
    if (word.endsWith("ed")) candidates.push(word.slice(0, -2), `${word.slice(0, -2)}e`);
    if (word.endsWith("es")) candidates.push(word.slice(0, -2), word.slice(0, -1));
    if (word.endsWith("s")) candidates.push(word.slice(0, -1));
    return candidates.find((item) => COMMON_VERBS.has(item) || BE.has(item)) || word;
  }

  function isVerb(token, index, tokens) {
    const lower = token.toLowerCase();
    if (index > 0 && tokens[index - 1].toLowerCase() === "to") return false;
    if (lower.endsWith("ing") && !BE.has(tokens[index - 1]?.toLowerCase())) return false;
    return AUX.has(lower) || COMMON_VERBS.has(lemma(lower)) || IRREGULAR.has(lower);
  }

  function textOf(tokens, start, end) {
    return tokens.slice(start, end + 1).join(" ").replace(/\s+([,.;:!?])/g, "$1").trim();
  }

  function firstSentence(source) {
    const matches = source.match(/[^.!?]+[.!?]?/g)?.map((item) => item.trim()).filter(Boolean) || [];
    return { focus: matches[0] || source, count: matches.length || 1 };
  }

  function guessPos(token) {
    const lower = token.toLowerCase();
    if (!/[A-Za-z0-9]/.test(token)) return "标点";
    if (AUX.has(lower)) return "助动词/系动词";
    if (CONNECTORS.has(lower)) return "连接词";
    if (["a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their"].includes(lower)) return "限定词";
    if (["i", "you", "he", "she", "it", "we", "they", "me", "him", "us", "them"].includes(lower)) return "代词";
    if (COMMON_VERBS.has(lemma(lower)) || IRREGULAR.has(lower)) return "动词";
    if (lower.endsWith("ly")) return "副词";
    if (lower.endsWith("ing") || lower.endsWith("ed")) return "非谓语/形容词形态";
    return "名词/修饰词（需结合语境）";
  }

  function analyze(rawSentence) {
    const source = String(rawSentence || "").replace(/\s+/g, " ").trim();
    const { focus, count } = firstSentence(source);
    const tokens = words(focus);
    const warnings = ["本地分析服务未运行，当前使用浏览器内置基础分析；复杂从句建议启动本地服务复核。"];
    if (count > 1) warnings.push(`本次选中了 ${count} 句，先展示第一句的结构；逐句选择可获得更清楚的结果。`);

    let predicateStart = tokens.findIndex((token, index) => isVerb(token, index, tokens));
    if (predicateStart < 0) {
      return {
        sentence: focus,
        pattern: "待判断",
        skeleton: focus,
        components: [{ text: focus, role: "S", label: "待判断", explanation: "未识别到明确的限定谓语。" }],
        predicates: [], clauses: [], non_finite: [],
        word_classes: tokens.filter((item) => /[A-Za-z]/.test(item)).map((item) => ({ text: item, pos: guessPos(item) })),
        explanations: ["先找能够体现时态、语态或情态的谓语，再切分主干。"], warnings,
        analysis_method: "浏览器内置基础分析", confidence: 0.35,
      };
    }

    let predicateEnd = predicateStart;
    if (AUX.has(tokens[predicateStart].toLowerCase())) {
      let cursor = predicateStart + 1;
      while (cursor < tokens.length && cursor <= predicateStart + 4) {
        const lower = tokens[cursor].toLowerCase();
        if (["not", "never", "already", "still", "just"].includes(lower) || AUX.has(lower) || COMMON_VERBS.has(lemma(lower)) || lower.endsWith("ing") || lower.endsWith("ed")) {
          predicateEnd = cursor;
          cursor += 1;
        } else break;
      }
    }

    const subjectText = textOf(tokens, 0, predicateStart - 1) || "（省略/待判断）";
    const predicateText = textOf(tokens, predicateStart, predicateEnd);
    const restEnd = tokens.length - (/[.!?]/.test(tokens.at(-1) || "") ? 2 : 1);
    const restText = restEnd >= predicateEnd + 1 ? textOf(tokens, predicateEnd + 1, restEnd) : "";
    const predicateLemma = lemma(tokens[predicateEnd]);
    const isLinking = BE.has(tokens[predicateStart].toLowerCase()) || LINKING.has(predicateLemma);
    const components = [
      { text: subjectText, role: "S", label: "主语", explanation: "谓语前承担陈述对象的部分。" },
      { text: predicateText, role: "V", label: "谓语", explanation: "体现时态、语态或情态的动词组。" },
    ];
    let pattern = "SV";
    const restStart = predicateEnd + 1;
    const toIndex = tokens.findIndex((token, index) => index >= restStart && token.toLowerCase() === "to");
    const firstRest = tokens[restStart]?.toLowerCase();
    const objectPronouns = new Set(["me", "you", "him", "her", "it", "us", "them"]);
    if (restText && OBJECT_CONTROL.has(predicateLemma) && toIndex > restStart) {
      components.push(
        { text: textOf(tokens, restStart, toIndex - 1), role: "O", label: "宾语", explanation: "动作直接涉及的人或事物。" },
        { text: textOf(tokens, toIndex, restEnd), role: "OC", label: "宾语补足语", explanation: "说明宾语要做什么；宾语与其后动作可形成逻辑主谓。" },
      );
      pattern = "SVOC";
    } else if (restText && DITRANSITIVE.has(predicateLemma) && objectPronouns.has(firstRest) && restEnd > restStart) {
      components.push(
        { text: tokens[restStart], role: "IO", label: "间接宾语", explanation: "通常表示动作的接受者。" },
        { text: textOf(tokens, restStart + 1, restEnd), role: "DO", label: "直接宾语", explanation: "通常表示被给予、告知或传递的事物。" },
      );
      pattern = "SVOO";
    } else if (restText) {
      components.push({
        text: restText,
        role: isLinking ? "SC" : "O",
        label: isLinking ? "表语/主补" : "宾语（基础判断）",
        explanation: isLinking ? "说明主语的身份、性质或状态。" : "位于实义动词后，基础模式中先按宾语处理。",
      });
      pattern = isLinking ? "SVC" : "SVO";
    }

    const clauses = [];
    tokens.forEach((token, index) => {
      const lower = token.toLowerCase();
      if (CONNECTORS.has(lower)) clauses.push({ text: textOf(tokens, index, tokens.length - 1), type: CONNECTORS.get(lower), function: "连接成分" });
    });
    const nonFinite = [];
    tokens.forEach((token, index) => {
      const lower = token.toLowerCase();
      if (lower === "to" && tokens[index + 1] && COMMON_VERBS.has(lemma(tokens[index + 1]))) {
        nonFinite.push({ text: `${token} ${tokens[index + 1]}`, form: "to do", function: "需结合语境判断目的、宾补或后置修饰" });
      } else if (lower.endsWith("ing") && index !== predicateEnd) {
        nonFinite.push({ text: token, form: "doing", function: "需结合语境判断状语、定语或补语" });
      }
    });

    return {
      sentence: focus,
      pattern,
      skeleton: components.map((item) => item.text).join(" + "),
      components,
      predicates: [{ text: predicateText, tense: "基础判断", voice: "待结合上下文", type: isLinking ? "系动词谓语" : "动词谓语" }],
      clauses,
      non_finite: nonFinite,
      word_classes: tokens.filter((item) => /[A-Za-z]/.test(item)).map((item) => ({ text: item, pos: guessPos(item) })),
      explanations: ["刘老师式顺序：先圈谓语，再看连接词，最后保留主干并处理修饰成分。"],
      warnings,
      analysis_method: "浏览器内置基础分析",
      confidence: count > 1 ? 0.48 : 0.62,
    };
  }

  globalThis.SentenceBlueprintFallback = Object.freeze({ analyze });
  if (typeof module !== "undefined" && module.exports) module.exports = { analyze };
})();
