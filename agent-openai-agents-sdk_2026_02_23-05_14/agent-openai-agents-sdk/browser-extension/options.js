const extensionApi = globalThis.browser ?? globalThis.chrome;

const DEFAULTS = {
  baseUrl: "http://localhost:8000",
  timeoutMs: 30000,
  history: [],
};

async function load() {
  const data = await extensionApi.storage.sync.get(DEFAULTS);
  document.getElementById("baseUrl").value = data.baseUrl || DEFAULTS.baseUrl;
  document.getElementById("timeoutMs").value = String(data.timeoutMs || DEFAULTS.timeoutMs);
}

async function save() {
  const baseUrl = document.getElementById("baseUrl").value.trim().replace(/\/$/, "");
  const timeoutMsRaw = Number(document.getElementById("timeoutMs").value);
  const timeoutMs = Number.isFinite(timeoutMsRaw) && timeoutMsRaw >= 1000 ? timeoutMsRaw : DEFAULTS.timeoutMs;

  await extensionApi.storage.sync.set({ baseUrl, timeoutMs });
  document.getElementById("status").textContent = "Saved.";
}

async function clearHistory() {
  await extensionApi.storage.sync.set({ history: [] });
  document.getElementById("status").textContent = "Chat history cleared.";
}

function bind() {
  document.getElementById("save").addEventListener("click", save);
  document.getElementById("clearHistory").addEventListener("click", clearHistory);
}

bind();
load();
