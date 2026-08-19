import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require(
  "C:/Users/极客/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
);

const thisDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(thisDir, "..");
const demoPath = path.join(projectDir, "demo", "index.html");
const contentScriptPath = path.join(projectDir, "extension", "content.js");
const contentStylePath = path.join(projectDir, "extension", "content.css");
const fallbackAnalyzerPath = path.join(projectDir, "extension", "fallback-analyzer.js");
const artifactDir = path.join(projectDir, "artifacts");
const chromeCandidates = [
  chromium.executablePath(),
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  path.join(process.env.LOCALAPPDATA || "", "Google/Chrome/Application/chrome.exe"),
];
const executablePath = chromeCandidates.find((candidate) => candidate && fs.existsSync(candidate));
if (!executablePath) throw new Error("没有找到 Google Chrome 可执行文件");

const html = fs.readFileSync(demoPath);
const server = http.createServer((request, response) => {
  if (request.url === "/" || request.url === "/index.html") {
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    response.end(html);
    return;
  }
  response.writeHead(404);
  response.end("Not found");
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const address = server.address();

let browser;
try {
  browser = await chromium.launch({
    executablePath,
    headless: true,
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: "dark" });
  const page = await context.newPage();
  await page.addInitScript(() => {
    const storageListeners = [];
    const runtimeListeners = [];
    globalThis.chrome = {
      storage: {
        local: {
          get: async (defaults) => ({ ...defaults }),
        },
        onChanged: {
          addListener: (listener) => storageListeners.push(listener),
        },
      },
      runtime: {
        onMessage: { addListener: (listener) => runtimeListeners.push(listener) },
        sendMessage: async (message) => {
          if (message?.type !== "SBP_ANALYZE") return { ok: false, error: "Unsupported" };
          if (message.sentence === "Apache Doris is a high-performance, real-time analytical database.") {
            return {
              ok: true,
              data: {
                sentence: message.sentence,
                analysis_method: "Stanford Stanza",
                pattern: "SVC",
                skeleton: "Apache Doris + is + a high-performance, real-time analytical database",
                components: [
                  { text: "Apache Doris", role: "S", label: "主语", explanation: "主语" },
                  { text: "is", role: "V", label: "谓语", explanation: "系动词" },
                  { text: "a high-performance, real-time analytical database", role: "SC", label: "表语/主补", explanation: "表语" },
                ],
                predicates: [{ text: "is", tense: "一般现在时", voice: "主动", type: "系动词谓语" }],
                clauses: [],
                non_finite: [],
                word_classes: [
                  { text: "Apache", pos: "专有名词" },
                  { text: "Doris", pos: "专有名词" },
                  { text: "is", pos: "助动词/系动词" },
                  { text: "a", pos: "限定词" },
                  { text: "high-performance", pos: "复合形容词（作定语）" },
                  { text: "real-time", pos: "复合形容词（作定语）" },
                  { text: "analytical", pos: "形容词" },
                  { text: "database", pos: "名词" },
                ],
                explanations: [],
                warnings: [],
                confidence: 0.9,
              },
            };
          }
          if (message.sentence === "Because Docker controls the virtualization layer, it can be monitored in ways that aren't possible.") {
            return {
              ok: true,
              data: {
                sentence: message.sentence,
                analysis_method: "Stanford Stanza",
                pattern: "复合句（主句 SV）",
                skeleton: "it + can be monitored",
                components: [
                  { text: "it", role: "S", label: "主语", explanation: "主句主语" },
                  { text: "can be monitored", role: "V", label: "谓语", explanation: "主句谓语" },
                ],
                predicates: [{ text: "can be monitored", tense: "情态动词结构", voice: "被动", type: "动词谓语" }],
                clauses: [
                  { text: "Because Docker controls the virtualization layer", type: "原因状语从句", function: "状语" },
                  { text: "that aren't possible", type: "定语从句", function: "修饰先行词 ways" },
                ],
                non_finite: [],
                word_classes: [
                  { text: "Because", pos: "从属连接词" },
                  { text: "Docker", pos: "专有名词" },
                  { text: "controls", pos: "动词" },
                  { text: "the", pos: "限定词" },
                  { text: "virtualization", pos: "名词" },
                  { text: "layer", pos: "名词" },
                  { text: "it", pos: "代词" },
                  { text: "can", pos: "助动词/系动词" },
                  { text: "be", pos: "助动词/系动词" },
                  { text: "monitored", pos: "动词" },
                  { text: "in", pos: "介词" },
                  { text: "ways", pos: "名词" },
                  { text: "that", pos: "从属连接词" },
                  { text: "aren't", pos: "助动词/系动词" },
                  { text: "possible", pos: "形容词" },
                ],
                explanations: [],
                warnings: [],
                confidence: 0.9,
              },
            };
          }
          if (message.sentence === "Personally, I had it in mind that OpenAI's infra was better, and more: why not warn us when we change reasoning? Again, I apologize and I was wrong here.") {
            return {
              ok: true,
              data: {
                sentence: message.sentence,
                analysis_method: "Stanford Stanza",
                pattern: "2 句文本",
                skeleton: "I + had ｜ I + apologize",
                components: [],
                predicates: [],
                clauses: [],
                non_finite: [],
                word_classes: [],
                explanations: [],
                warnings: [],
                confidence: 0.88,
                sentence_analyses: [
                  {
                    sentence: "Personally, I had it in mind that OpenAI's infra was better, and more: why not warn us when we change reasoning?",
                    analysis_method: "Stanford Stanza",
                    pattern: "复合句（主句 SV）",
                    skeleton: "I + had",
                    components: [
                      { text: "Personally", role: "Adv", label: "评注性状语", explanation: "说话人的个人视角" },
                      { text: "I", role: "S", label: "主语", explanation: "主句主语" },
                      { text: "had", role: "V", label: "谓语", explanation: "主句谓语" },
                    ],
                    predicates: [{ text: "had", tense: "过去时间结构", voice: "主动", type: "动词谓语" }],
                    clauses: [
                      { text: "that OpenAI's infra was better", type: "名词性从句", function: "宾语/补充内容" },
                      { text: "and more: why not warn us when we change reasoning", type: "独立省略问句", function: "冒号或并列后的独立表达" },
                      { text: "when we change reasoning", type: "时间状语从句", function: "状语" },
                    ],
                    non_finite: [],
                    word_classes: [{ text: "Personally", pos: "副词" }, { text: "I", pos: "代词" }, { text: "had", pos: "动词" }],
                    explanations: [],
                    warnings: [],
                    confidence: 0.88,
                  },
                  {
                    sentence: "Again, I apologize and I was wrong here.",
                    analysis_method: "Stanford Stanza",
                    pattern: "复合句（主句 SV）",
                    skeleton: "I + apologize",
                    components: [
                      { text: "Again", role: "Adv", label: "评注性状语", explanation: "承接前文" },
                      { text: "I", role: "S", label: "主语", explanation: "主句主语" },
                      { text: "apologize", role: "V", label: "谓语", explanation: "主句谓语" },
                    ],
                    predicates: [{ text: "apologize", tense: "一般现在时", voice: "主动", type: "动词谓语" }],
                    clauses: [{ text: "and I was wrong here", type: "并列主句", function: "与前一主句并列" }],
                    non_finite: [],
                    word_classes: [{ text: "Again", pos: "副词" }, { text: "I", pos: "代词" }, { text: "apologize", pos: "动词" }],
                    explanations: [],
                    warnings: [],
                    confidence: 0.88,
                  },
                ],
              },
            };
          }
          return { ok: true, data: globalThis.SentenceBlueprintFallback.analyze(message.sentence) };
        },
      },
    };
    globalThis.__sbpDispatch = (message) => runtimeListeners.forEach((listener) => listener(message));
    globalThis.__sbpSampleRolePalette = (host) => {
      const parseColor = (value) => {
        const channels = String(value).match(/[\d.]+/g)?.slice(0, 3).map(Number) || [0, 0, 0];
        return { r: channels[0], g: channels[1], b: channels[2] };
      };
      const luminance = (value) => {
        const color = parseColor(value);
        const channel = (number) => {
          const normalized = number / 255;
          return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
        };
        return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
      };
      const result = {};
      for (const role of ["S", "V", "O", "C", "Atr", "Adv", "App", "Conj"]) {
        const sample = document.createElement("span");
        sample.className = `sbp-component sbp-role-${role}`;
        sample.textContent = role;
        host.append(sample);
        const style = getComputedStyle(sample);
        const foreground = style.color;
        const background = style.backgroundColor;
        const foregroundLuminance = luminance(foreground);
        const backgroundLuminance = luminance(background);
        result[role] = {
          foreground,
          background,
          backgroundLuminance,
          contrast: (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
            (Math.min(foregroundLuminance, backgroundLuminance) + 0.05),
        };
        sample.remove();
      }
      return result;
    };
  });
  await page.goto(`http://127.0.0.1:${address.port}/`, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ path: contentStylePath });
  await page.addScriptTag({ path: fallbackAnalyzerPath });
  await page.addScriptTag({ path: contentScriptPath });
  await page.locator(".sbp-third-line").first().waitFor({ timeout: 15_000 });
  const rowCount = await page.locator(".sbp-third-line").count();
  if (rowCount !== 3) throw new Error(`预期 3 条第三行，实际 ${rowCount} 条`);

  await page.locator(".sbp-bar").first().click();
  await page.locator(".sbp-component").first().waitFor({ timeout: 15_000 });
  const summary = await page.locator(".sbp-details").first().innerText();
  if (!summary.includes("SVOC") || !summary.includes("宾语补足语")) {
    throw new Error(`拆解结果不符合预期：${summary}`);
  }

  await page.evaluate(() => {
    const paragraph = document.querySelector("article p:nth-of-type(2)");
    const range = document.createRange();
    range.selectNodeContents(paragraph.firstChild);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    globalThis.__sbpDispatch({
      type: "SBP_ANALYZE_SELECTION",
      sentence: "My father bought me a new phone.",
    });
  });
  const inline = page.locator(".sbp-selection-inline").first();
  await inline.locator(".sbp-component").first().waitFor({ timeout: 15_000 });
  const posColors = await inline.evaluate((node) => {
    const source = node.querySelector(".sbp-selection-source");
    const noun = source?.querySelector(".sbp-pos-noun");
    const verb = source?.querySelector(".sbp-pos-verb");
    return {
      sourceText: source?.textContent || "",
      tokenCount: source?.querySelectorAll(".sbp-pos-token").length || 0,
      chipCount: node.querySelectorAll(".sbp-pos-chip").length,
      nounColor: noun ? getComputedStyle(noun).color : "",
      verbColor: verb ? getComputedStyle(verb).color : "",
    };
  });
  if (
    posColors.sourceText !== "My father bought me a new phone." ||
    posColors.tokenCount < 6 ||
    posColors.chipCount < 6 ||
    !posColors.nounColor ||
    posColors.nounColor === posColors.verbColor
  ) {
    throw new Error(`原句词性着色不符合预期：${JSON.stringify(posColors)}`);
  }
  const placement = await inline.evaluate((node) => ({
    previousTag: node.previousElementSibling?.tagName,
    previousText: node.previousElementSibling?.textContent || "",
    position: getComputedStyle(node).position,
  }));
  if (placement.previousTag !== "P" || !placement.previousText.includes("My father bought")) {
    throw new Error(`选中分析未插入原段落下方：${JSON.stringify(placement)}`);
  }
  if (placement.position === "fixed") throw new Error("选中分析仍然是 fixed 浮窗");

  await page.evaluate(() => {
    const paragraph = document.createElement("p");
    paragraph.id = "hyphenated-compound-example";
    paragraph.textContent = "Apache Doris is a high-performance, real-time analytical database.";
    document.querySelector("article").append(paragraph);
    const range = document.createRange();
    range.selectNodeContents(paragraph);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    globalThis.__sbpDispatch({
      type: "SBP_ANALYZE_SELECTION",
      sentence: paragraph.textContent,
    });
  });
  const compoundInline = page.locator("#hyphenated-compound-example + .sbp-selection-inline");
  await compoundInline.locator(".sbp-component").first().waitFor({ timeout: 15_000 });
  const compounds = await compoundInline.evaluate((node) => {
    const source = node.querySelector(".sbp-selection-source");
    const sourceTokens = [...(source?.querySelectorAll(".sbp-pos-token") || [])].map((item) => ({
      text: item.textContent,
      title: item.title,
      adjective: item.classList.contains("sbp-pos-adjective"),
    }));
    const chips = [...node.querySelectorAll(".sbp-pos-chip")].map((item) => item.textContent);
    return { sourceTokens, chips };
  });
  for (const phrase of ["high-performance", "real-time"]) {
    const token = compounds.sourceTokens.find((item) => item.text === phrase);
    if (!token?.adjective || token.title !== "复合形容词（作定语）" || !compounds.chips.some((item) => item.includes(phrase))) {
      throw new Error(`连字符复合形容词被错误拆开：${JSON.stringify(compounds)}`);
    }
  }
  if (compounds.chips.some((item) => item === "high 形容词" || item === "performance 名词")) {
    throw new Error(`词性层仍显示连字符复合词的内部碎片：${JSON.stringify(compounds)}`);
  }
  await compoundInline.locator('[data-mode="structure"]').click();
  const simpleStructureLabels = await compoundInline
    .locator(".sbp-structure-token")
    .evaluateAll((items) => [...new Set(items.map((item) => item.title))]);
  if (!simpleStructureLabels.includes("主语") || !simpleStructureLabels.includes("谓语") || !simpleStructureLabels.includes("表语/主补")) {
    throw new Error(`简单句成分视图不符合预期：${JSON.stringify(simpleStructureLabels)}`);
  }
  await compoundInline.locator('[data-mode="pos"]').click();

  await page.evaluate(() => {
    const paragraph = document.createElement("p");
    paragraph.id = "clause-structure-example";
    paragraph.textContent = "Because Docker controls the virtualization layer, it can be monitored in ways that aren't possible.";
    document.querySelector("article").append(paragraph);
    const range = document.createRange();
    range.selectNodeContents(paragraph);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    globalThis.__sbpDispatch({
      type: "SBP_ANALYZE_SELECTION",
      sentence: paragraph.textContent,
    });
  });
  const structureInline = page.locator("#clause-structure-example + .sbp-selection-inline");
  await structureInline.locator(".sbp-component").first().waitFor({ timeout: 15_000 });
  await structureInline.locator('[data-mode="structure"]').click();
  const structureView = await structureInline.evaluate((node) => ({
    sourceText: node.querySelector(".sbp-selection-source")?.textContent || "",
    activeMode: node.querySelector(".sbp-annotation-tab.is-active")?.dataset.mode || "",
    segments: [...node.querySelectorAll(".sbp-structure-token")].map((item) => ({
      text: item.textContent,
      label: item.title,
    })),
    legend: [...node.querySelectorAll(".sbp-structure-legend-item")].map((item) => item.textContent),
  }));
  const structureLabels = new Set(structureView.segments.map((item) => item.label));
  if (
    structureView.sourceText !== "Because Docker controls the virtualization layer, it can be monitored in ways that aren't possible." ||
    structureView.activeMode !== "structure" ||
    !structureLabels.has("主句") ||
    !structureLabels.has("原因状语从句") ||
    !structureLabels.has("定语从句") ||
    structureView.legend.length !== 3
  ) {
    throw new Error(`句子结构视图不符合预期：${JSON.stringify(structureView)}`);
  }
  await structureInline.locator('[data-mode="pos"]').click();
  const returnedToPos = await structureInline.evaluate((node) => ({
    activeMode: node.querySelector(".sbp-annotation-tab.is-active")?.dataset.mode || "",
    posTokens: node.querySelectorAll(".sbp-pos-token").length,
    structureTokens: node.querySelectorAll(".sbp-structure-token").length,
    legendHidden: node.querySelector(".sbp-structure-legend")?.hidden,
  }));
  if (returnedToPos.activeMode !== "pos" || returnedToPos.posTokens < 10 || returnedToPos.structureTokens !== 0 || !returnedToPos.legendHidden) {
    throw new Error(`词性/结构标签页切换失败：${JSON.stringify(returnedToPos)}`);
  }

  const discourseSource = "Personally, I had it in mind that OpenAI's infra was better, and more: why not warn us when we change reasoning? Again, I apologize and I was wrong here.";
  await page.evaluate((source) => {
    const paragraph = document.createElement("p");
    paragraph.id = "discourse-structure-example";
    paragraph.textContent = source;
    document.querySelector("article").append(paragraph);
    const range = document.createRange();
    range.selectNodeContents(paragraph);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    globalThis.__sbpDispatch({ type: "SBP_ANALYZE_SELECTION", sentence: source });
  }, discourseSource);
  const discourseInline = page.locator("#discourse-structure-example + .sbp-selection-inline");
  await discourseInline.locator(".sbp-sentence-analysis").nth(1).waitFor({ timeout: 15_000 });
  await discourseInline.locator('[data-mode="structure"]').click();
  const discourseView = await discourseInline.evaluate((node) => ({
    sourceText: node.querySelector(".sbp-selection-source")?.textContent || "",
    sentenceLabels: [...node.querySelectorAll(".sbp-structure-sentence")].map((item) => item.dataset.sentenceLabel),
    sentenceTexts: [...node.querySelectorAll(".sbp-structure-sentence-text")].map((item) => item.textContent),
    tokens: [...node.querySelectorAll(".sbp-structure-token")].map((item) => ({ text: item.textContent, label: item.title })),
  }));
  const discourseLabels = new Set(discourseView.tokens.map((item) => item.label));
  if (
    discourseView.sourceText !== discourseSource ||
    JSON.stringify(discourseView.sentenceLabels) !== JSON.stringify(["第1句", "第2句"]) ||
    discourseView.sentenceTexts.length !== 2 ||
    !discourseView.tokens.some((item) => item.text === "Personally" && item.label === "评注性状语") ||
    !discourseView.tokens.some((item) => item.text === "Again" && item.label === "评注性状语") ||
    !discourseLabels.has("主句") ||
    !discourseLabels.has("名词性从句") ||
    !discourseLabels.has("时间状语从句") ||
    !discourseLabels.has("独立省略问句") ||
    !discourseLabels.has("并列主句")
  ) {
    throw new Error(`多句分层与评注性状语视图不符合预期：${JSON.stringify(discourseView)}`);
  }
  const lightTheme = await inline.evaluate((node) => ({
    isLight: node.classList.contains("sbp-theme-light"),
    background: getComputedStyle(node.querySelector(".sbp-details")).backgroundColor,
    rolePalette: globalThis.__sbpSampleRolePalette(node),
  }));
  const expectedLightRoleBackgrounds = {
    S: "rgb(219, 234, 254)",
    V: "rgb(255, 228, 230)",
    O: "rgb(204, 251, 241)",
    C: "rgb(243, 232, 255)",
    Atr: "rgb(224, 242, 254)",
    Adv: "rgb(254, 243, 199)",
    App: "rgb(224, 231, 255)",
    Conj: "rgb(243, 244, 246)",
  };
  const lightPaletteValid = Object.entries(expectedLightRoleBackgrounds).every(
    ([role, background]) => lightTheme.rolePalette[role]?.background === background && lightTheme.rolePalette[role]?.contrast >= 4.5,
  );
  if (!lightTheme.isLight || !lightTheme.background.includes("255, 255, 255") || !lightPaletteValid) {
    throw new Error(`系统为深色偏好时未跟随白色网页：${JSON.stringify(lightTheme)}`);
  }

  await page.evaluate(() => {
    const section = document.createElement("section");
    section.id = "dark-host-section";
    section.style.cssText = "margin-top:24px;padding:18px;border-radius:12px;background:rgb(17,24,39);color:rgb(229,231,235);font:18px/1.7 Georgia,serif";
    const paragraph = document.createElement("p");
    paragraph.textContent = "Docker VMM provides a stable alternative.";
    section.append(paragraph);
    document.body.append(section);
    const range = document.createRange();
    range.selectNodeContents(paragraph);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    globalThis.__sbpDispatch({
      type: "SBP_ANALYZE_SELECTION",
      sentence: paragraph.textContent,
    });
  });
  const darkInline = page.locator("#dark-host-section .sbp-selection-inline");
  await darkInline.locator(".sbp-component").first().waitFor({ timeout: 15_000 });
  const darkTheme = await darkInline.evaluate((node) => ({
    isDark: node.classList.contains("sbp-theme-dark"),
    fontFamily: getComputedStyle(node).fontFamily,
    background: getComputedStyle(node.querySelector(".sbp-details")).backgroundColor,
    componentLabelBackground: getComputedStyle(node.querySelector(".sbp-component-label")).backgroundColor,
    rolePalette: globalThis.__sbpSampleRolePalette(node),
  }));
  const darkPaletteValid = Object.entries(expectedLightRoleBackgrounds).every(
    ([role, background]) => darkTheme.rolePalette[role]?.background === background && darkTheme.rolePalette[role]?.contrast >= 4.5,
  );
  if (
    !darkTheme.isDark ||
    !darkTheme.fontFamily.includes("Georgia") ||
    darkTheme.componentLabelBackground !== "rgba(255, 255, 255, 0.65)" ||
    !darkPaletteValid
  ) {
    throw new Error(`深色局部区域未继承页面主题：${JSON.stringify(darkTheme)}`);
  }
  await page.locator("#dark-host-section").evaluate((node) => {
    node.style.background = "rgb(255, 255, 255)";
    node.style.color = "rgb(31, 41, 55)";
    node.style.fontFamily = "Arial, sans-serif";
  });
  await page.waitForTimeout(260);
  const switchedTheme = await darkInline.evaluate((node) => ({
    isLight: node.classList.contains("sbp-theme-light"),
    fontFamily: getComputedStyle(node).fontFamily,
    subjectBackground: globalThis.__sbpSampleRolePalette(node).S.background,
  }));
  if (
    !switchedTheme.isLight ||
    !switchedTheme.fontFamily.includes("Arial") ||
    switchedTheme.subjectBackground !== expectedLightRoleBackgrounds.S
  ) {
    throw new Error(`网页运行时切换主题后未自动刷新：${JSON.stringify(switchedTheme)}`);
  }
  await page.locator("#dark-host-section").evaluate((node) => {
    node.style.background = "rgb(17, 24, 39)";
    node.style.color = "rgb(229, 231, 235)";
    node.style.fontFamily = "Georgia, serif";
  });
  await page.waitForTimeout(260);

  fs.mkdirSync(artifactDir, { recursive: true });
  await structureInline.locator('[data-mode="structure"]').click();
  await structureInline.screenshot({ path: path.join(artifactDir, "structure-view-demo.png") });
  await discourseInline.screenshot({ path: path.join(artifactDir, "multi-sentence-structure-demo.png") });
  await page.screenshot({ path: path.join(artifactDir, "third-line-demo.png"), fullPage: true });

  process.stdout.write(`E2E OK：多句分层、评注性状语、独立句、双视图与主题切换均通过。\n`);
} finally {
  if (browser) await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
