import * as vscode from "vscode";
import { BackendClient } from "./backendClient";

export class ChatPanel {
  private static currentPanel: ChatPanel | undefined;
  private readonly panel: vscode.WebviewPanel;

  private constructor(panel: vscode.WebviewPanel, private readonly client: BackendClient) {
    this.panel = panel;
    this.panel.webview.html = this.getHtml();

    this.panel.webview.onDidReceiveMessage(async (message) => {
      if (message?.type !== "chat") {
        return;
      }

      try {
        const payload = await this.client.invoke([{ role: "user", content: String(message.text ?? "") }]);
        this.panel.webview.postMessage({ type: "assistant", payload: JSON.stringify(payload, null, 2) });
      } catch (error) {
        const text = error instanceof Error ? error.message : String(error);
        this.panel.webview.postMessage({ type: "assistant", payload: `Error: ${text}` });
      }
    });

    this.panel.onDidDispose(() => {
      ChatPanel.currentPanel = undefined;
    });
  }

  static show(context: vscode.ExtensionContext, client: BackendClient): void {
    const column = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.One;

    if (ChatPanel.currentPanel) {
      ChatPanel.currentPanel.panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel("perfectAgentChat", "PERFECT Agent Chat", column, {
      enableScripts: true,
      retainContextWhenHidden: true,
    });

    ChatPanel.currentPanel = new ChatPanel(panel, client);
    context.subscriptions.push(panel);
  }

  private getHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PERFECT Agent Chat</title>
  <style>
    body { font-family: "Segoe UI", sans-serif; margin: 0; padding: 12px; color: #e6edf3; background: #0d1117; }
    #log { border: 1px solid #30363d; border-radius: 8px; padding: 10px; height: 58vh; overflow: auto; background: #161b22; }
    .row { margin-bottom: 8px; white-space: pre-wrap; }
    .user { color: #79c0ff; }
    .assistant { color: #d2a8ff; }
    .input { margin-top: 10px; display: flex; gap: 8px; }
    textarea { flex: 1; min-height: 70px; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: #e6edf3; padding: 10px; }
    button { border-radius: 8px; border: 1px solid #30363d; background: #21262d; color: #e6edf3; padding: 10px 14px; cursor: pointer; }
  </style>
</head>
<body>
  <h3>PERFECT Agent</h3>
  <div id="log"></div>
  <div class="input">
    <textarea id="prompt" placeholder="Ask the agent..."></textarea>
    <button id="send">Send</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    const log = document.getElementById("log");
    const prompt = document.getElementById("prompt");
    const send = document.getElementById("send");

    const append = (role, text) => {
      const row = document.createElement("div");
      row.className = "row " + role;
      row.textContent = role.toUpperCase() + ": " + text;
      log.appendChild(row);
      log.scrollTop = log.scrollHeight;
    };

    send.addEventListener("click", () => {
      const text = prompt.value.trim();
      if (!text) return;
      append("user", text);
      vscode.postMessage({ type: "chat", text });
      prompt.value = "";
    });

    window.addEventListener("message", (event) => {
      const data = event.data;
      if (data?.type === "assistant") {
        append("assistant", data.payload || "(no response)");
      }
    });
  </script>
</body>
</html>`;
  }
}
