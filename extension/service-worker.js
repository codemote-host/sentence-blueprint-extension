importScripts("fallback-analyzer.js");

const DEFAULT_SETTINGS = Object.freeze({
  enabled: true,
  autoAnalyze: false,
  analyzerUrl: "http://127.0.0.1:8765/analyze",
  maxSentenceLength: 1600,
  showWordClasses: true,
  showExplanations: true,
});

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get(DEFAULT_SETTINGS);
  await chrome.storage.local.set({ ...DEFAULT_SETTINGS, ...current });

  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "sentence-blueprint-analyze",
      title: "用句子蓝图拆解",
      contexts: ["selection"],
    });
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "sentence-blueprint-analyze" || !tab?.id) return;
  const sentence = (info.selectionText || "").trim();
  if (!sentence) return;
  chrome.tabs.sendMessage(
    tab.id,
    { type: "SBP_ANALYZE_SELECTION", sentence },
    Number.isInteger(info.frameId) ? { frameId: info.frameId } : undefined,
  );
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "analyze-selection") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  chrome.tabs.sendMessage(tab.id, { type: "SBP_ANALYZE_CURRENT_SELECTION" });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "SBP_ANALYZE") {
    analyzeSentence(message.sentence, Boolean(message.forceRefresh))
      .then((data) => sendResponse({ ok: true, data }))
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error?.message || "分析服务不可用",
        }),
      );
    return true;
  }

  if (message?.type === "SBP_HEALTH") {
    checkHealth()
      .then((data) => sendResponse({ ok: true, data }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  return false;
});

async function getSettings() {
  return chrome.storage.local.get(DEFAULT_SETTINGS);
}

async function analyzeSentence(rawSentence, forceRefresh = false) {
  const settings = await getSettings();
  const sentence = String(rawSentence || "").replace(/\s+/g, " ").trim();

  if (!sentence) throw new Error("没有检测到英文句子");
  if (sentence.length > Number(settings.maxSentenceLength || 1600)) {
    throw new Error(`句子过长，请控制在 ${settings.maxSentenceLength} 个字符以内`);
  }

  try {
    const response = await fetch(settings.analyzerUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sentence, force_refresh: forceRefresh }),
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      throw new Error(`分析服务返回了无法识别的内容（HTTP ${response.status}）`);
    }

    if (!response.ok || payload?.error) {
      throw new Error(payload?.error || `分析请求失败（HTTP ${response.status}）`);
    }
    return payload;
  } catch (error) {
    await recordDiagnostic("analyze_fetch", error, { analyzerUrl: settings.analyzerUrl });
    const fallback = globalThis.SentenceBlueprintFallback?.analyze(sentence);
    if (!fallback) throw error;
    return fallback;
  }
}

async function checkHealth() {
  const settings = await getSettings();
  const healthUrl = new URL(settings.analyzerUrl);
  healthUrl.pathname = "/health";
  healthUrl.search = "";
  try {
    const response = await fetch(healthUrl.toString(), { method: "GET" });
    if (!response.ok) throw new Error(`服务状态异常（HTTP ${response.status}）`);
    return response.json();
  } catch (error) {
    await recordDiagnostic("health_fetch", error, { healthUrl: healthUrl.toString() });
    throw new Error(`${error?.message || "连接失败"}；内置基础分析仍可使用`);
  }
}

async function recordDiagnostic(stage, error, extra = {}) {
  try {
    const stored = await chrome.storage.local.get({ diagnosticLogs: [] });
    const logs = Array.isArray(stored.diagnosticLogs) ? stored.diagnosticLogs : [];
    logs.unshift({
      time: new Date().toISOString(),
      stage,
      message: error?.message || String(error || "未知错误"),
      ...extra,
    });
    await chrome.storage.local.set({ diagnosticLogs: logs.slice(0, 50) });
  } catch (_storageError) {
    // 诊断日志不应阻断分析降级。
  }
}
