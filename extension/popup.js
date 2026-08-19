const DEFAULTS = { enabled: true, autoAnalyze: false };

document.addEventListener("DOMContentLoaded", async () => {
  const settings = await chrome.storage.local.get(DEFAULTS);
  const enabled = document.getElementById("enabled");
  const autoAnalyze = document.getElementById("autoAnalyze");
  const health = document.getElementById("health");
  const status = document.getElementById("status");

  enabled.checked = settings.enabled;
  autoAnalyze.checked = settings.autoAnalyze;

  enabled.addEventListener("change", () => chrome.storage.local.set({ enabled: enabled.checked }));
  autoAnalyze.addEventListener("change", () =>
    chrome.storage.local.set({ autoAnalyze: autoAnalyze.checked }),
  );

  health.addEventListener("click", async () => {
    status.textContent = "正在检查……";
    const response = await chrome.runtime.sendMessage({ type: "SBP_HEALTH" });
    status.textContent = response?.ok
      ? `服务正常：${response.data.analysis_method || response.data.provider || "已连接"}`
      : `增强服务未连接；内置基础分析可用。${response?.error || ""}`;
  });
});
