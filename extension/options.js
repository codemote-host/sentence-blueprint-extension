const DEFAULTS = {
  enabled: true,
  autoAnalyze: false,
  analyzerUrl: "http://127.0.0.1:8765/analyze",
  maxSentenceLength: 1600,
  showWordClasses: true,
  showExplanations: true,
};

document.addEventListener("DOMContentLoaded", async () => {
  const settings = await chrome.storage.local.get(DEFAULTS);
  for (const [key, value] of Object.entries(settings)) {
    const input = document.getElementById(key);
    if (!input) continue;
    if (input.type === "checkbox") input.checked = Boolean(value);
    else input.value = value;
  }

  document.getElementById("save").addEventListener("click", save);
  document.getElementById("health").addEventListener("click", checkHealth);
  document.getElementById("clearLogs").addEventListener("click", clearLogs);
  await renderLogs();
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes.diagnosticLogs) renderLogs();
  });
});

async function save() {
  const next = {
    enabled: document.getElementById("enabled").checked,
    autoAnalyze: document.getElementById("autoAnalyze").checked,
    analyzerUrl: document.getElementById("analyzerUrl").value.trim(),
    maxSentenceLength: Number(document.getElementById("maxSentenceLength").value || 1600),
    showWordClasses: document.getElementById("showWordClasses").checked,
    showExplanations: document.getElementById("showExplanations").checked,
  };
  await chrome.storage.local.set(next);
  document.getElementById("status").textContent = "设置已保存，请刷新已打开的网页。";
}

async function checkHealth() {
  await save();
  const status = document.getElementById("status");
  status.textContent = "正在检查……";
  const response = await chrome.runtime.sendMessage({ type: "SBP_HEALTH" });
  status.textContent = response?.ok
    ? `服务正常：${JSON.stringify(response.data)}`
    : `本地服务未连接：${response?.error || "未知错误"}`;
}

async function renderLogs() {
  const output = document.getElementById("diagnosticLogs");
  const { diagnosticLogs = [] } = await chrome.storage.local.get({ diagnosticLogs: [] });
  if (!Array.isArray(diagnosticLogs) || diagnosticLogs.length === 0) {
    output.textContent = "暂无错误日志。";
    return;
  }
  output.textContent = diagnosticLogs
    .map((item) => {
      const time = item.time ? new Date(item.time).toLocaleString("zh-CN", { hour12: false }) : "未知时间";
      const target = item.analyzerUrl || item.healthUrl || "";
      return [`[${time}] ${item.stage || "unknown"}`, item.message || "未知错误", target].filter(Boolean).join("\n");
    })
    .join("\n\n");
}

async function clearLogs() {
  await chrome.storage.local.set({ diagnosticLogs: [] });
  await renderLogs();
  document.getElementById("status").textContent = "诊断日志已清空。";
}
