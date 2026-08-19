(() => {
  "use strict";

  // 沉浸式翻译 1.32.1 中观察到的稳定 DOM 标记。集中放置，方便版本升级时维护。
  const IMT_BLOCK_SELECTOR = ".immersive-translate-target-translation-block-wrapper";
  const IMT_TARGET_SELECTOR = ".immersive-translate-target-wrapper";
  const SOURCE_ATTRIBUTE = "data-immersive-translate-source-text";
  const ROW_CLASS = "sbp-third-line";

  const DEFAULT_SETTINGS = {
    enabled: true,
    autoAnalyze: false,
    maxSentenceLength: 1600,
    showWordClasses: true,
    showExplanations: true,
  };

  const ROLE_LABELS = {
    S: "主语",
    V: "谓语",
    O: "宾语",
    IO: "间接宾语",
    DO: "直接宾语",
    SC: "表语/主补",
    OC: "宾语补足语",
    C: "补语",
    Atr: "定语",
    Adv: "状语",
    App: "同位语",
    Conj: "连接成分",
  };

  let settings = { ...DEFAULT_SETTINGS };
  let observer = null;
  let scanTimer = null;
  let themeTimer = null;

  init().catch((error) => console.warn("[句子蓝图] 初始化失败", error));

  async function init() {
    settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== "local") return;
      for (const [key, value] of Object.entries(changes)) {
        settings[key] = value.newValue;
      }
      if (settings.enabled) scheduleScan(document);
      else removeAllRows();
    });

    chrome.runtime.onMessage.addListener((message) => {
      if (message?.type === "SBP_ANALYZE_SELECTION") {
        showSelectionInline(message.sentence);
      }
      if (message?.type === "SBP_ANALYZE_CURRENT_SELECTION") {
        const selected = window.getSelection()?.toString().trim();
        if (selected) showSelectionInline(selected);
      }
    });

    if (!settings.enabled) return;
    scan(document);
    observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "attributes") {
          if (mutation.target instanceof Element && !mutation.target.closest(`.${ROW_CLASS}`)) {
            scheduleThemeRefresh();
          }
          continue;
        }
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) scheduleScan(node);
        }
      }
    });
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "style", "data-theme", "data-color-mode"],
    });
    window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener?.("change", scheduleThemeRefresh);
  }

  function scheduleScan(root) {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(() => scan(root?.isConnected ? root : document), 120);
  }

  function scheduleThemeRefresh() {
    clearTimeout(themeTimer);
    themeTimer = setTimeout(() => {
      document.querySelectorAll(`.${ROW_CLASS}`).forEach((row) => {
        const anchor = row.__sbpThemeAnchor;
        if (anchor?.isConnected) applyHostTheme(row, anchor);
      });
    }, 160);
  }

  function scan(root) {
    if (!settings.enabled || !root) return;
    const candidates = new Set();

    if (root.matches?.(IMT_BLOCK_SELECTOR) || root.matches?.(IMT_TARGET_SELECTOR)) {
      candidates.add(root);
    }
    root.querySelectorAll?.(`${IMT_BLOCK_SELECTOR}, ${IMT_TARGET_SELECTOR}`).forEach((node) =>
      candidates.add(node),
    );

    for (const node of candidates) {
      const anchor = node.closest(IMT_BLOCK_SELECTOR) || node;
      if (!anchor.matches(IMT_BLOCK_SELECTOR) && anchor.closest(IMT_BLOCK_SELECTOR)) continue;
      mountThirdLine(anchor);
    }
  }

  function mountThirdLine(anchor) {
    if (!(anchor instanceof Element) || anchor.dataset.sbpMounted === "1") return;
    if (anchor.closest(`.${ROW_CLASS}`)) return;

    const sourceText = extractSourceText(anchor);
    if (!isLikelyEnglish(sourceText)) return;
    if (sourceText.length > Number(settings.maxSentenceLength || 1600)) return;

    anchor.dataset.sbpMounted = "1";
    const row = document.createElement("span");
    row.className = ROW_CLASS;
    row.dataset.sbpSource = sourceText;

    const bar = document.createElement("span");
    bar.className = "sbp-bar";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "sbp-trigger";
    button.textContent = "拆";
    button.title = "按谓语、连词、主干、从句、非谓语拆解";

    const title = document.createElement("span");
    title.className = "sbp-title";
    title.textContent = "句子拆解";

    const preview = document.createElement("span");
    preview.className = "sbp-preview";
    preview.textContent = "点击生成第三行结构分析";

    const details = document.createElement("span");
    details.className = "sbp-details";
    details.hidden = true;

    bar.append(button, title, preview);
    row.append(bar, details);
    applyHostTheme(row, anchor);
    anchor.insertAdjacentElement("afterend", row);

    bar.addEventListener("click", () => {
      if (row.dataset.sbpLoaded === "1") {
        details.hidden = !details.hidden;
        row.classList.toggle("sbp-expanded", !details.hidden);
        return;
      }
      runAnalysis(row, sourceText);
    });

    if (settings.autoAnalyze) runAnalysis(row, sourceText, { keepCollapsed: true });
  }

  function extractSourceText(anchor) {
    let current = anchor;
    for (let depth = 0; current && depth < 7; depth += 1, current = current.parentElement) {
      const source = current.getAttribute?.(SOURCE_ATTRIBUTE);
      if (source?.trim()) return cleanSentence(source);
    }

    const container = anchor.parentElement;
    if (!container) return "";
    const clone = container.cloneNode(true);
    clone.querySelectorAll(`${IMT_TARGET_SELECTOR}, .${ROW_CLASS}`).forEach((node) => node.remove());
    return cleanSentence(clone.textContent || "");
  }

  function cleanSentence(value) {
    return String(value || "")
      .replace(/[\u200B-\u200D\uFEFF]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function isLikelyEnglish(value) {
    if (!value || value.length < 3) return false;
    const letters = value.match(/[A-Za-z]/g)?.length || 0;
    const words = value.match(/[A-Za-z]+(?:['’-][A-Za-z]+)*/g)?.length || 0;
    return words >= 2 && letters / Math.max(value.length, 1) >= 0.35;
  }

  async function runAnalysis(row, sentence, options = {}) {
    const details = row.querySelector(".sbp-details");
    const preview = row.querySelector(".sbp-preview");
    if (!details || !preview || row.dataset.sbpLoading === "1") return;

    row.dataset.sbpLoading = "1";
    preview.textContent = "正在先找谓语……";
    details.hidden = Boolean(options.keepCollapsed);
    row.classList.toggle("sbp-expanded", !details.hidden);
    renderLoading(details);

    try {
      const response = await chrome.runtime.sendMessage({
        type: "SBP_ANALYZE",
        sentence,
      });
      if (!response?.ok) throw new Error(response?.error || "分析失败");

      renderAnalysis(details, response.data);
      row.dataset.sbpLoaded = "1";
      const skeleton = response.data.skeleton || response.data.pattern || "分析完成";
      preview.textContent = skeleton.length > 90 ? `${skeleton.slice(0, 90)}…` : skeleton;
    } catch (error) {
      renderError(details, error.message);
      preview.textContent = "分析服务未连接，点击查看启动方法";
      details.hidden = false;
      row.classList.add("sbp-expanded");
    } finally {
      delete row.dataset.sbpLoading;
    }
  }

  function renderLoading(container) {
    container.replaceChildren();
    const loading = el("span", "sbp-loading", "正在拆骨架：谓语 → 连词 → 主干 → 修饰……");
    container.append(loading);
  }

  function renderError(container, message) {
    container.replaceChildren();
    const box = el("span", "sbp-error");
    box.append(
      el("strong", "", "暂时无法分析"),
      el("span", "", message || "请检查本地服务"),
      el("code", "", ".\\start_service.ps1"),
    );
    container.append(box);
  }

  function renderAnalysis(container, data) {
    container.replaceChildren();

    if (Array.isArray(data.sentence_analyses) && data.sentence_analyses.length > 1) {
      const summary = el("span", "sbp-meta");
      summary.append(
        badge(data.pattern || `${data.sentence_analyses.length} 句文本`, "sbp-pattern"),
        badge(data.analysis_method || "Stanford Stanza", "sbp-method"),
        badge(`置信度 ${Math.round(Number(data.confidence || 0) * 100)}%`, "sbp-confidence"),
      );
      container.append(summary);
      data.sentence_analyses.forEach((sentenceAnalysis, index) => {
        const block = el("span", "sbp-sentence-analysis");
        const heading = el("span", "sbp-sentence-heading");
        const coloredSentence = el("span", "sbp-colored-sentence");
        renderPosColoredSentence(
          coloredSentence,
          sentenceAnalysis.sentence || "",
          sentenceAnalysis.word_classes || [],
        );
        heading.append(
          el("strong", "", `第 ${index + 1} 句`),
          coloredSentence,
        );
        const body = el("span", "sbp-sentence-body");
        block.append(heading, body);
        container.append(block);
        renderAnalysis(body, sentenceAnalysis);
      });
      renderListSection(container, "提醒", data.warnings, (item) => String(item), "sbp-warning-list");
      return;
    }

    const meta = el("span", "sbp-meta");
    meta.append(
      badge(data.pattern || "待判断", "sbp-pattern"),
      badge(data.analysis_method || "分析", "sbp-method"),
      badge(`置信度 ${Math.round(Number(data.confidence || 0) * 100)}%`, "sbp-confidence"),
    );
    container.append(meta);

    if (data.skeleton) {
      const skeleton = section("主干");
      skeleton.body.append(el("span", "sbp-skeleton", data.skeleton));
      container.append(skeleton.root);
    }

    if (Array.isArray(data.components) && data.components.length) {
      const parts = section("七大成分");
      const line = el("span", "sbp-components");
      for (const component of data.components) {
        const role = normalizeRole(component.role);
        const item = el("span", `sbp-component sbp-role-${role}`);
        item.append(
          el("span", "sbp-component-text", component.text || ""),
          el("span", "sbp-component-label", component.label || ROLE_LABELS[role] || role),
        );
        if (component.explanation) item.title = component.explanation;
        line.append(item);
      }
      parts.body.append(line);
      container.append(parts.root);
    }

    renderListSection(container, "谓语", data.predicates, (item) => {
      const text = item.text || String(item);
      const detail = [item.tense, item.voice, item.type].filter(Boolean).join(" · ");
      return detail ? `${text}｜${detail}` : text;
    });

    renderListSection(container, "从句与连接", data.clauses, (item) => {
      const label = [item.type, item.function].filter(Boolean).join(" / ");
      return `${item.text || ""}${label ? `｜${label}` : ""}`;
    });

    renderListSection(container, "非谓语", data.non_finite, (item) => {
      const detail = [item.form, item.function, item.logical_subject && `逻辑主语：${item.logical_subject}`]
        .filter(Boolean)
        .join(" · ");
      return `${item.text || ""}${detail ? `｜${detail}` : ""}`;
    });

    if (settings.showWordClasses) {
      const visibleWordClasses = Array.isArray(data.word_classes)
        ? data.word_classes.filter(
            (item) => item?.pos !== "标点" && /[A-Za-z0-9]/.test(String(item?.text || "")),
          )
        : [];
      renderWordClassSection(container, visibleWordClasses);
    }

    if (settings.showExplanations) {
      renderListSection(container, "为什么", data.explanations, (item) => String(item));
    }
    renderListSection(container, "提醒", data.warnings, (item) => String(item), "sbp-warning-list");
  }

  function renderListSection(container, title, values, formatter, extraClass = "") {
    if (!Array.isArray(values) || !values.length) return;
    const block = section(title);
    const list = el("span", `sbp-list ${extraClass}`.trim());
    for (const value of values) list.append(el("span", "sbp-list-item", formatter(value)));
    block.body.append(list);
    container.append(block.root);
  }

  function renderWordClassSection(container, values) {
    if (!Array.isArray(values) || !values.length) return;
    const block = section("词性层");
    const list = el("span", "sbp-list sbp-word-grid");
    for (const item of values) {
      const pos = item?.pos || "待判断";
      const chip = el("span", `sbp-list-item sbp-pos-chip ${posClassName(pos)}`);
      chip.title = pos;
      chip.append(
        el("span", "sbp-pos-word", item?.text || ""),
        el("span", "sbp-pos-label", pos),
      );
      list.append(chip);
    }
    block.body.append(list);
    container.append(block.root);
  }

  function section(title) {
    const root = el("span", "sbp-section");
    const heading = el("span", "sbp-section-title", title);
    const body = el("span", "sbp-section-body");
    root.append(heading, body);
    return { root, body };
  }

  function normalizeRole(role) {
    const raw = String(role || "").trim();
    const aliases = {
      subject: "S",
      predicate: "V",
      object: "O",
      indirect_object: "IO",
      direct_object: "DO",
      subject_complement: "SC",
      object_complement: "OC",
      complement: "C",
      attribute: "Atr",
      adverbial: "Adv",
      appositive: "App",
      conjunction: "Conj",
    };
    return aliases[raw] || raw || "O";
  }

  function badge(text, className) {
    return el("span", `sbp-badge ${className}`, text);
  }

  function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function removeAllRows() {
    document.querySelectorAll(`.${ROW_CLASS}`).forEach((node) => node.remove());
    document.querySelectorAll("[data-sbp-mounted]").forEach((node) => delete node.dataset.sbpMounted);
  }

  function showSelectionInline(rawSentence) {
    const sentence = cleanSentence(rawSentence);
    if (!isLikelyEnglish(sentence)) return;

    const anchor = findSelectionAnchor(sentence);
    const previous = anchor?.nextElementSibling;
    if (previous?.classList.contains("sbp-selection-inline")) previous.remove();

    const row = el("span", `${ROW_CLASS} sbp-selection-inline`);
    row.dataset.sbpSource = sentence;
    const header = el("span", "sbp-selection-header");
    const title = el("strong", "", "句子蓝图 · 当前内容下方");
    const annotationTabs = el("span", "sbp-annotation-tabs");
    annotationTabs.setAttribute("role", "tablist");
    annotationTabs.setAttribute("aria-label", "原句标注方式");
    const posTab = el("button", "sbp-annotation-tab is-active", "词性视图");
    const structureTab = el("button", "sbp-annotation-tab", "句子结构");
    const tabs = { pos: posTab, structure: structureTab };
    for (const [mode, tab] of Object.entries(tabs)) {
      tab.type = "button";
      tab.disabled = true;
      tab.dataset.mode = mode;
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-selected", mode === "pos" ? "true" : "false");
    }
    annotationTabs.append(posTab, structureTab);
    const sourceLine = el("span", "sbp-selection-source", sentence);
    const structureLegend = el("span", "sbp-structure-legend");
    structureLegend.hidden = true;
    header.append(title, annotationTabs, sourceLine, structureLegend);
    const close = el("button", "sbp-selection-close", "×");
    close.type = "button";
    close.title = "关闭本条分析";
    close.addEventListener("click", () => row.remove());
    header.append(close);

    const details = el("span", "sbp-details");
    row.append(header, details);
    applyHostTheme(row, anchor);
    insertAfterAnchor(anchor, row);
    renderLoading(details);

    let analysisData = null;
    let annotationMode = "pos";
    const renderSourceAnnotation = () => {
      for (const [mode, tab] of Object.entries(tabs)) {
        const active = mode === annotationMode;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      }
      sourceLine.dataset.annotationMode = annotationMode;
      if (!analysisData) return;
      if (annotationMode === "structure") {
        renderStructureColoredSentence(sourceLine, sentence, analysisData, structureLegend);
      } else {
        structureLegend.hidden = true;
        structureLegend.replaceChildren();
        renderPosColoredSentence(sourceLine, sentence, collectWordClasses(analysisData));
      }
    };
    for (const [mode, tab] of Object.entries(tabs)) {
      tab.addEventListener("click", () => {
        annotationMode = mode;
        renderSourceAnnotation();
      });
    }

    chrome.runtime
      .sendMessage({ type: "SBP_ANALYZE", sentence })
      .then((response) => {
        if (!response?.ok) throw new Error(response?.error || "分析失败");
        analysisData = response.data;
        Object.values(tabs).forEach((tab) => {
          tab.disabled = false;
        });
        renderAnalysis(details, analysisData);
        renderSourceAnnotation();
      })
      .catch((error) => renderError(details, error.message));
  }

  function findSelectionAnchor(sentence) {
    const selection = window.getSelection();
    if (selection?.rangeCount) {
      const range = selection.getRangeAt(0);
      const common = range.commonAncestorContainer;
      const element = common.nodeType === Node.ELEMENT_NODE ? common : common.parentElement;
      const anchor = closestReadableBlock(element);
      if (anchor) return anchor;
    }

    // 某些网页在右键菜单打开后会清掉 Range；此时用所选文本反查最深层内容块。
    const needle = sentence.slice(0, 100).toLowerCase();
    if (needle && document.body) {
      const candidates = document.body.querySelectorAll("p, li, blockquote, td, th, figcaption, article, section, div");
      for (const candidate of candidates) {
        if (candidate.closest(`.${ROW_CLASS}`)) continue;
        const text = cleanSentence(candidate.textContent).toLowerCase();
        if (text.includes(needle)) {
          const deeper = Array.from(candidate.querySelectorAll("p, li, blockquote, td, th, figcaption"))
            .find((node) => cleanSentence(node.textContent).toLowerCase().includes(needle));
          return deeper || candidate;
        }
      }
    }
    return document.body;
  }

  function closestReadableBlock(element) {
    if (!(element instanceof Element)) return null;
    return (
      element.closest(IMT_BLOCK_SELECTOR) ||
      element.closest("p, li, blockquote, td, th, figcaption, h1, h2, h3, h4, h5, h6") ||
      element.closest("article, section, div") ||
      element
    );
  }

  function insertAfterAnchor(anchor, row) {
    if (anchor && ![document.documentElement, document.body].includes(anchor) && anchor.parentElement) {
      anchor.insertAdjacentElement("afterend", row);
      return;
    }
    (document.body || document.documentElement).append(row);
  }

  function applyHostTheme(row, anchor) {
    const context = anchor instanceof Element ? anchor : document.body || document.documentElement;
    row.__sbpThemeAnchor = context;
    const computed = getComputedStyle(context);
    const background = findEffectiveBackground(context);
    let foreground = parseCssColor(computed.color) || { r: 31, g: 41, b: 55, a: 1 };
    const dark = relativeLuminance(background) < 0.42;

    if (contrastRatio(foreground, background) < 3) {
      foreground = dark ? { r: 226, g: 232, b: 240, a: 1 } : { r: 31, g: 41, b: 55, a: 1 };
    }

    const accent = findHostAccent(context, background, dark);
    const surface = dark ? mixColors(background, { r: 255, g: 255, b: 255 }, 0.045) : mixColors(background, { r: 255, g: 255, b: 255 }, 0.4);
    const surfaceSoft = dark ? mixColors(background, { r: 255, g: 255, b: 255 }, 0.085) : mixColors(background, accent, 0.045);
    const border = mixColors(background, foreground, dark ? 0.2 : 0.16);
    const muted = mixColors(foreground, background, dark ? 0.34 : 0.38);
    const accentSoft = mixColors(background, accent, dark ? 0.24 : 0.12);
    const accentBorder = mixColors(background, accent, dark ? 0.48 : 0.34);
    const onAccent = contrastRatio({ r: 255, g: 255, b: 255, a: 1 }, accent) >= 4.2
      ? { r: 255, g: 255, b: 255 }
      : { r: 15, g: 23, b: 42 };

    const hostFontSize = Number.parseFloat(computed.fontSize) || 14;
    const fontSize = Math.max(12.5, Math.min(hostFontSize, 15.5));
    const hostLineHeight = Number.parseFloat(computed.lineHeight);
    const lineHeight = Number.isFinite(hostLineHeight)
      ? Math.max(1.35, Math.min(hostLineHeight / Math.max(hostFontSize, 1), 1.8))
      : 1.55;
    const hostRadius = Number.parseFloat(computed.borderRadius);
    const radius = Number.isFinite(hostRadius) && hostRadius > 0 ? Math.min(hostRadius, 14) : 8;

    row.classList.toggle("sbp-theme-dark", dark);
    row.classList.toggle("sbp-theme-light", !dark);
    row.style.setProperty("--sbp-surface", colorToCss(surface));
    row.style.setProperty("--sbp-surface-soft", colorToCss(surfaceSoft));
    row.style.setProperty("--sbp-text", colorToCss(foreground));
    row.style.setProperty("--sbp-muted", colorToCss(muted));
    row.style.setProperty("--sbp-border", colorToCss(border));
    row.style.setProperty("--sbp-accent", colorToCss(accent));
    row.style.setProperty("--sbp-accent-soft", colorToCss(accentSoft));
    row.style.setProperty("--sbp-accent-border", colorToCss(accentBorder));
    row.style.setProperty("--sbp-on-accent", colorToCss(onAccent));
    row.style.setProperty("--sbp-shadow", `rgba(${foreground.r}, ${foreground.g}, ${foreground.b}, ${dark ? 0.2 : 0.09})`);
    row.style.setProperty("--sbp-font-family", computed.fontFamily || "system-ui, sans-serif");
    row.style.setProperty("--sbp-font-size", `${fontSize}px`);
    row.style.setProperty("--sbp-line-height", String(lineHeight));
    row.style.setProperty("--sbp-radius", `${radius}px`);
  }

  function findEffectiveBackground(element) {
    const layers = [];
    let current = element;
    while (current instanceof Element) {
      const color = parseCssColor(getComputedStyle(current).backgroundColor);
      if (color && color.a > 0.01) layers.push(color);
      current = current.parentElement;
    }
    let result = layers.findLast?.((color) => color.a >= 0.98) || null;
    if (!result) {
      result = getComputedStyle(document.documentElement).colorScheme.includes("dark")
        ? { r: 15, g: 23, b: 42, a: 1 }
        : { r: 255, g: 255, b: 255, a: 1 };
    }
    for (let index = layers.length - 1; index >= 0; index -= 1) {
      result = compositeColor(layers[index], result);
    }
    return { ...result, a: 1 };
  }

  function findHostAccent(context, background, dark) {
    const variableNames = [
      "--color-primary", "--primary-color", "--ifm-color-primary", "--md-primary-fg-color",
      "--theme-primary", "--accent-color", "--link-color",
    ];
    const elements = [context, document.body, document.documentElement].filter(Boolean);
    for (const element of elements) {
      const style = getComputedStyle(element);
      for (const name of variableNames) {
        const color = parseCssColor(style.getPropertyValue(name));
        if (color && color.a > 0.5 && contrastRatio(color, background) >= 2.2) return color;
      }
    }

    const nearbyLink = context.closest("a") || context.parentElement?.querySelector("a[href]") || document.querySelector("a[href]");
    if (nearbyLink) {
      const color = parseCssColor(getComputedStyle(nearbyLink).color);
      if (color && color.a > 0.5 && colorSaturation(color) > 0.18 && contrastRatio(color, background) >= 2.2) {
        return color;
      }
    }
    return dark ? { r: 96, g: 165, b: 250, a: 1 } : { r: 37, g: 99, b: 235, a: 1 };
  }

  function parseCssColor(value) {
    const match = String(value || "").trim().match(/^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+))?\s*\)$/i);
    if (!match) return null;
    return {
      r: Math.max(0, Math.min(255, Number(match[1]))),
      g: Math.max(0, Math.min(255, Number(match[2]))),
      b: Math.max(0, Math.min(255, Number(match[3]))),
      a: match[4] === undefined ? 1 : Math.max(0, Math.min(1, Number(match[4]))),
    };
  }

  function compositeColor(top, bottom) {
    const alpha = top.a + bottom.a * (1 - top.a);
    if (alpha <= 0) return { r: 255, g: 255, b: 255, a: 1 };
    return {
      r: (top.r * top.a + bottom.r * bottom.a * (1 - top.a)) / alpha,
      g: (top.g * top.a + bottom.g * bottom.a * (1 - top.a)) / alpha,
      b: (top.b * top.a + bottom.b * bottom.a * (1 - top.a)) / alpha,
      a: alpha,
    };
  }

  function mixColors(first, second, amount) {
    const weight = Math.max(0, Math.min(1, amount));
    return {
      r: first.r + (second.r - first.r) * weight,
      g: first.g + (second.g - first.g) * weight,
      b: first.b + (second.b - first.b) * weight,
      a: 1,
    };
  }

  function relativeLuminance(color) {
    const channel = (value) => {
      const normalized = value / 255;
      return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
  }

  function contrastRatio(first, second) {
    const lighter = Math.max(relativeLuminance(first), relativeLuminance(second));
    const darker = Math.min(relativeLuminance(first), relativeLuminance(second));
    return (lighter + 0.05) / (darker + 0.05);
  }

  function colorSaturation(color) {
    const max = Math.max(color.r, color.g, color.b);
    const min = Math.min(color.r, color.g, color.b);
    return max === 0 ? 0 : (max - min) / max;
  }

  function colorToCss(color) {
    return `rgb(${Math.round(color.r)}, ${Math.round(color.g)}, ${Math.round(color.b)})`;
  }

  function collectWordClasses(data) {
    if (Array.isArray(data?.sentence_analyses) && data.sentence_analyses.length) {
      return data.sentence_analyses.flatMap((item) => item.word_classes || []);
    }
    return Array.isArray(data?.word_classes) ? data.word_classes : [];
  }

  function findSourceRange(source, rawText) {
    const text = String(rawText || "").trim();
    if (!text) return null;
    const haystack = source.toLocaleLowerCase();
    const needle = text.toLocaleLowerCase();
    let cursor = 0;
    while (cursor < source.length) {
      const start = haystack.indexOf(needle, cursor);
      if (start < 0) return null;
      const end = start + text.length;
      const firstIsWord = /[A-Za-z0-9]/.test(text[0] || "");
      const lastIsWord = /[A-Za-z0-9]/.test(text.at(-1) || "");
      const beforeIsWord = start > 0 && /[A-Za-z0-9]/.test(source[start - 1]);
      const afterIsWord = end < source.length && /[A-Za-z0-9]/.test(source[end]);
      if ((!firstIsWord || !beforeIsWord) && (!lastIsWord || !afterIsWord)) return { start, end };
      cursor = start + 1;
    }
    return null;
  }

  function clauseStructureClassName(rawType) {
    const type = String(rawType || "");
    if (type.includes("并列主句") || type.includes("独立分句") || type.includes("独立省略")) {
      return "sbp-structure-independent-clause";
    }
    if (type.includes("状语从句")) return "sbp-structure-adverbial-clause";
    if (type.includes("定语从句")) return "sbp-structure-relative-clause";
    if (
      type.includes("主语从句") ||
      type.includes("宾语从句") ||
      type.includes("表语从句") ||
      type.includes("同位语从句") ||
      type.includes("名词性从句")
    ) {
      return "sbp-structure-nominal-clause";
    }
    return "sbp-structure-other-clause";
  }

  function componentStructureClassName(rawRole) {
    const role = normalizeRole(rawRole);
    if (role === "S") return "sbp-structure-subject";
    if (role === "V") return "sbp-structure-predicate";
    if (["O", "IO", "DO"].includes(role)) return "sbp-structure-object";
    if (["C", "SC", "OC"].includes(role)) return "sbp-structure-complement";
    if (["Atr", "Adv", "App"].includes(role)) return "sbp-structure-modifier";
    return "sbp-structure-connector";
  }

  function renderStructureLegend(container, items) {
    container.replaceChildren();
    const unique = new Map();
    for (const item of items) {
      if (item?.label && !unique.has(item.label)) unique.set(item.label, item.className);
    }
    for (const [label, className] of unique.entries()) {
      const legendItem = el("span", `sbp-structure-legend-item ${className}`);
      legendItem.append(el("span", "sbp-structure-swatch"), el("span", "", label));
      container.append(legendItem);
    }
    container.hidden = unique.size === 0;
  }

  function buildStructureAnnotations(source, data) {
    const clauses = Array.isArray(data?.clauses) ? data.clauses : [];
    let annotations = clauses
      .map((item) => {
        const range = findSourceRange(source, item?.text);
        if (!range) return null;
        const label = item?.type || "从句";
        return { ...range, label, className: clauseStructureClassName(label) };
      })
      .filter(Boolean);
    const clauseMode = annotations.length > 0;
    const defaultAnnotation = clauseMode
      ? { label: "主句", className: "sbp-structure-main-clause" }
      : null;
    const components = Array.isArray(data?.components) ? data.components : [];

    const componentItems = clauseMode
      ? components.filter((item) => {
          const role = normalizeRole(item?.role);
          return role === "Adv" && item?.label && item.label !== ROLE_LABELS.Adv;
        })
      : components;
    annotations.push(
      ...componentItems
        .map((item) => {
          const range = findSourceRange(source, item?.text);
          if (!range) return null;
          const role = normalizeRole(item?.role);
          return {
            ...range,
            label: item?.label || ROLE_LABELS[role] || role,
            className: componentStructureClassName(role),
          };
        })
        .filter(Boolean),
    );
    return { annotations, defaultAnnotation };
  }

  function renderOneStructureSentence(container, source, data) {
    const { annotations, defaultAnnotation } = buildStructureAnnotations(source, data);

    const boundaries = new Set([0, source.length]);
    for (const item of annotations) {
      boundaries.add(item.start);
      boundaries.add(item.end);
    }
    const orderedBoundaries = [...boundaries].sort((left, right) => left - right);
    const usedLegendItems = [];
    if (defaultAnnotation) usedLegendItems.push(defaultAnnotation);

    for (let index = 0; index < orderedBoundaries.length - 1; index += 1) {
      const start = orderedBoundaries[index];
      const end = orderedBoundaries[index + 1];
      const text = source.slice(start, end);
      if (!text) continue;
      const matching = annotations
        .filter((item) => item.start <= start && item.end >= end)
        .sort((first, second) => (first.end - first.start) - (second.end - second.start));
      const annotation = matching[0] || defaultAnnotation;
      if (!annotation || !/[A-Za-z0-9]/.test(text)) {
        container.append(document.createTextNode(text));
        continue;
      }
      const span = el("span", `sbp-structure-token ${annotation.className}`, text);
      span.title = annotation.label;
      container.append(span);
      usedLegendItems.push(annotation);
    }
    if (!container.childNodes.length) container.textContent = source;
    return usedLegendItems;
  }

  function renderStructureColoredSentence(container, sentence, data, legend) {
    container.replaceChildren();
    const usedLegendItems = [];
    const analyses = Array.isArray(data?.sentence_analyses) ? data.sentence_analyses : [];
    if (analyses.length > 1) {
      analyses.forEach((analysis, index) => {
        const block = el("span", "sbp-structure-sentence");
        block.dataset.sentenceLabel = `第${index + 1}句`;
        const sentenceText = el("span", "sbp-structure-sentence-text");
        usedLegendItems.push(
          ...renderOneStructureSentence(sentenceText, String(analysis?.sentence || ""), analysis),
        );
        block.append(sentenceText);
        container.append(block);
        if (index < analyses.length - 1) container.append(document.createTextNode(" "));
      });
    } else {
      usedLegendItems.push(...renderOneStructureSentence(container, String(sentence || ""), data));
    }
    renderStructureLegend(legend, usedLegendItems);
  }

  function renderPosColoredSentence(container, sentence, wordClasses) {
    container.replaceChildren();
    const source = String(sentence || "");
    let cursor = 0;
    for (const item of wordClasses || []) {
      const token = String(item?.text || "");
      if (!token) continue;
      let index = source.indexOf(token, cursor);
      if (index < 0) index = source.toLocaleLowerCase().indexOf(token.toLocaleLowerCase(), cursor);
      if (index < 0) continue;
      if (index > cursor) container.append(document.createTextNode(source.slice(cursor, index)));
      const matchedText = source.slice(index, index + token.length);
      const span = el("span", `sbp-pos-token ${posClassName(item?.pos)}`, matchedText);
      span.title = item?.pos || "词性待判断";
      container.append(span);
      cursor = index + token.length;
    }
    if (cursor < source.length) container.append(document.createTextNode(source.slice(cursor)));
    if (!container.childNodes.length) container.textContent = source;
  }

  function posClassName(rawPos) {
    const pos = String(rawPos || "");
    if (pos.includes("专有名词") || pos === "名词" || pos.includes("名词/")) return "sbp-pos-noun";
    if (pos.includes("动词")) return "sbp-pos-verb";
    if (pos.includes("形容词")) return "sbp-pos-adjective";
    if (pos.includes("副词")) return "sbp-pos-adverb";
    if (pos.includes("代词")) return "sbp-pos-pronoun";
    if (pos.includes("介词")) return "sbp-pos-preposition";
    if (pos.includes("连词") || pos.includes("连接词")) return "sbp-pos-conjunction";
    if (pos.includes("限定词")) return "sbp-pos-determiner";
    if (pos.includes("数词")) return "sbp-pos-number";
    return "sbp-pos-other";
  }
})();
