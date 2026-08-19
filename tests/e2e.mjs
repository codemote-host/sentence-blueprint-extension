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
          return { ok: true, data: globalThis.SentenceBlueprintFallback.analyze(message.sentence) };
        },
      },
    };
    globalThis.__sbpDispatch = (message) => runtimeListeners.forEach((listener) => listener(message));
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
  const inline = page.locator(".sbp-selection-inline");
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
  const lightTheme = await inline.evaluate((node) => ({
    isLight: node.classList.contains("sbp-theme-light"),
    background: getComputedStyle(node.querySelector(".sbp-details")).backgroundColor,
  }));
  if (!lightTheme.isLight || !lightTheme.background.includes("255, 255, 255")) {
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
  }));
  if (!darkTheme.isDark || !darkTheme.fontFamily.includes("Georgia")) {
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
  }));
  if (!switchedTheme.isLight || !switchedTheme.fontFamily.includes("Arial")) {
    throw new Error(`网页运行时切换主题后未自动刷新：${JSON.stringify(switchedTheme)}`);
  }
  await page.locator("#dark-host-section").evaluate((node) => {
    node.style.background = "rgb(17, 24, 39)";
    node.style.color = "rgb(229, 231, 235)";
    node.style.fontFamily = "Georgia, serif";
  });
  await page.waitForTimeout(260);

  fs.mkdirSync(artifactDir, { recursive: true });
  await page.screenshot({ path: path.join(artifactDir, "third-line-demo.png"), fullPage: true });

  process.stdout.write(`E2E OK：页面主题自动适配；原句与词性标签已按词性着色。\n`);
} finally {
  if (browser) await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
