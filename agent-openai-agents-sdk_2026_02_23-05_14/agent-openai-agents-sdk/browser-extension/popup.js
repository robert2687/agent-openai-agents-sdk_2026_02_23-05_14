const extensionApi = globalThis.browser ?? globalThis.chrome;

const DEFAULTS = {
  baseUrl: "http://localhost:8000",
  timeoutMs: 30000,
  history: [],
};

async function getSettings() {
  const result = await extensionApi.storage.sync.get(DEFAULTS);
  return {
    baseUrl: String(result.baseUrl || DEFAULTS.baseUrl).replace(/\/$/, ""),
    timeoutMs: Number(result.timeoutMs || DEFAULTS.timeoutMs),
    history: Array.isArray(result.history) ? result.history : [],
  };
}

async function setHistory(history) {
  await extensionApi.storage.sync.set({ history: history.slice(-20) });
}

function appendMessage(role, text) {
  const messages = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = `${role.toUpperCase()}: ${text}`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

async function renderHistory() {
  const settings = await getSettings();
  const messages = document.getElementById("messages");
  messages.innerHTML = "";
  for (const msg of settings.history) {
    appendMessage(msg.role, msg.text);
  }
}

async function updateStatus(text) {
  document.getElementById("status").textContent = text;
}

async function checkHealth() {
  const settings = await getSettings();
  updateStatus("Checking...");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), settings.timeoutMs);

  try {
    const response = await fetch(`${settings.baseUrl}/health`, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const health = await response.json();
    updateStatus(`${health.status || "ok"} (${health.model || "unknown model"})`);
  } catch (error) {
    updateStatus(`offline: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    clearTimeout(timer);
  }
}

async function sendPrompt() {
  const settings = await getSettings();
  const prompt = document.getElementById("prompt");
  const text = prompt.value.trim();
  if (!text) {
    return;
  }

  prompt.value = "";
  appendMessage("user", text);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), settings.timeoutMs);

  try {
    const response = await fetch(`${settings.baseUrl}/invocations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input: [{ role: "user", content: text }],
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`HTTP ${response.status}: ${body}`);
    }

    const data = await response.json();
    const payload = JSON.stringify(data, null, 2);
    appendMessage("assistant", payload);

    const newHistory = [
      ...settings.history,
      { role: "user", text },
      { role: "assistant", text: payload },
    ];
    await setHistory(newHistory);
  } catch (error) {
    const message = `Error: ${error instanceof Error ? error.message : String(error)}`;
    appendMessage("assistant", message);

    const newHistory = [...settings.history, { role: "user", text }, { role: "assistant", text: message }];
    await setHistory(newHistory);
  } finally {
    clearTimeout(timer);
  }
}

function bindEvents() {
  document.getElementById("send").addEventListener("click", sendPrompt);
  document.getElementById("health").addEventListener("click", checkHealth);
  document.getElementById("openOptions").addEventListener("click", () => {
    extensionApi.runtime.openOptionsPage();
  });
  document.getElementById("prompt").addEventListener("keydown", async (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      await sendPrompt();
    }
  });
}

async function init() {
  bindEvents();
  await renderHistory();
  await checkHealth();
}

init();
