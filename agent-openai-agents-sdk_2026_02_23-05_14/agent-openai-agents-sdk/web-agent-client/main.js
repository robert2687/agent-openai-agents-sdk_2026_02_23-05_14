const state = {
  sessions: [],
  activeSessionId: null,
  workspace: "default-workspace",
  project: "default-project",
};

const STORAGE_KEY = "perfect-agent-web-mvp";

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      Object.assign(state, parsed);
    } catch {
      // ignore invalid local state
    }
  }

  if (!state.sessions.length) {
    createSession();
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function createSession() {
  const id = `${Date.now()}`;
  const session = {
    id,
    title: `Session ${state.sessions.length + 1}`,
    messages: [],
  };
  state.sessions.unshift(session);
  state.activeSessionId = id;
  saveState();
  render();
}

function getActiveSession() {
  return state.sessions.find((s) => s.id === state.activeSessionId);
}

function addMessage(role, content) {
  const session = getActiveSession();
  if (!session) {
    return;
  }
  session.messages.push({ role, content, at: new Date().toISOString() });
  saveState();
  renderMessages();
}

function apiUrl() {
  return document.getElementById("apiUrl").value.replace(/\/$/, "");
}

async function checkHealth() {
  const label = document.getElementById("healthLabel");
  label.textContent = "Checking...";
  try {
    const res = await fetch(`${apiUrl()}/health`);
    const data = await res.json();
    label.textContent = `${data.status || "ok"} (${data.model || "unknown model"})`;
  } catch (error) {
    label.textContent = `offline: ${error}`;
  }
}

async function sendPrompt() {
  const input = document.getElementById("prompt");
  const text = input.value.trim();
  if (!text) {
    return;
  }

  addMessage("user", text);
  input.value = "";

  const scopedPrompt = [
    `workspace: ${state.workspace}`,
    `project: ${state.project}`,
    text,
  ].join("\n");

  try {
    const res = await fetch(`${apiUrl()}/invocations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input: [{ role: "user", content: scopedPrompt }],
      }),
    });

    const data = await res.json();
    addMessage("assistant", JSON.stringify(data, null, 2));
  } catch (error) {
    addMessage("assistant", `Error: ${error}`);
  }
}

function renderSessions() {
  const list = document.getElementById("sessionList");
  list.innerHTML = "";

  for (const session of state.sessions) {
    const li = document.createElement("li");
    li.textContent = session.title;
    li.onclick = () => {
      state.activeSessionId = session.id;
      saveState();
      render();
    };
    list.appendChild(li);
  }
}

function renderMessages() {
  const box = document.getElementById("messages");
  box.innerHTML = "";

  const session = getActiveSession();
  if (!session) {
    return;
  }

  for (const msg of session.messages) {
    const div = document.createElement("div");
    div.className = `message ${msg.role}`;
    div.textContent = `${msg.role.toUpperCase()}: ${msg.content}`;
    box.appendChild(div);
  }

  box.scrollTop = box.scrollHeight;
}

function renderScope() {
  const workspaceSelect = document.getElementById("workspaceSelect");
  const projectSelect = document.getElementById("projectSelect");

  const workspaces = ["default-workspace", "frontend", "backend", "data"]; 
  const projects = ["default-project", "agent-core", "ide-extension", "web-client"];

  workspaceSelect.innerHTML = workspaces.map((w) => `<option value="${w}">${w}</option>`).join("");
  projectSelect.innerHTML = projects.map((p) => `<option value="${p}">${p}</option>`).join("");

  workspaceSelect.value = state.workspace;
  projectSelect.value = state.project;
}

function saveScope() {
  state.workspace = document.getElementById("workspaceSelect").value;
  state.project = document.getElementById("projectSelect").value;
  saveState();
}

function render() {
  renderSessions();
  renderMessages();
  renderScope();
}

function setupEvents() {
  document.getElementById("newSession").addEventListener("click", createSession);
  document.getElementById("send").addEventListener("click", sendPrompt);
  document.getElementById("checkHealth").addEventListener("click", checkHealth);
  document.getElementById("saveScope").addEventListener("click", saveScope);
}

loadState();
setupEvents();
render();
checkHealth();
