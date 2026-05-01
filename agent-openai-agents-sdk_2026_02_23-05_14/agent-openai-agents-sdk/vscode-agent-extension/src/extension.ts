import * as vscode from "vscode";
import { BackendClient } from "./backendClient";
import { ChatPanel } from "./chatPanel";

function getClient(): BackendClient {
  const config = vscode.workspace.getConfiguration("perfectAgent");
  return new BackendClient(config);
}

async function invokeWithPrompt(prompt: string): Promise<void> {
  const client = getClient();
  const response = await client.invoke([{ role: "user", content: prompt }]);
  const output = JSON.stringify(response, null, 2);
  const doc = await vscode.workspace.openTextDocument({ content: output, language: "json" });
  await vscode.window.showTextDocument(doc, { preview: false });
}

function selectionOrAll(editor: vscode.TextEditor): string {
  const selection = editor.selection;
  if (!selection.isEmpty) {
    return editor.document.getText(selection);
  }
  return editor.document.getText();
}

export function activate(context: vscode.ExtensionContext): void {
  const openChat = vscode.commands.registerCommand("perfectAgent.openChat", () => {
    ChatPanel.show(context, getClient());
  });

  const explainCurrentFile = vscode.commands.registerCommand("perfectAgent.explainCurrentFile", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage("Open a file first.");
      return;
    }

    const fileName = editor.document.fileName;
    const content = editor.document.getText();
    await invokeWithPrompt(`Explain this file: ${fileName}\n\n${content}`);
  });

  const summarizeSelection = vscode.commands.registerCommand("perfectAgent.summarizeSelection", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage("Open a file first.");
      return;
    }

    const selected = selectionOrAll(editor);
    await invokeWithPrompt(`Summarize this code and list potential issues:\n\n${selected}`);
  });

  const checkBackendHealth = vscode.commands.registerCommand("perfectAgent.checkBackendHealth", async () => {
    try {
      const health = await getClient().health();
      vscode.window.showInformationMessage(`Backend online: ${JSON.stringify(health)}`);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      vscode.window.showErrorMessage(`Backend health check failed: ${text}`);
    }
  });

  const proposePatch = vscode.commands.registerCommand("perfectAgent.proposePatch", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage("Open a file first.");
      return;
    }

    const confirm = await vscode.window.showWarningMessage(
      "This action will ask the backend to propose a patch but will not auto-apply it. Continue?",
      { modal: true },
      "Continue"
    );

    if (confirm !== "Continue") {
      return;
    }

    const snippet = selectionOrAll(editor);
    await invokeWithPrompt(
      `Propose a minimal patch for this code. Return only a unified diff and a short rationale:\n\n${snippet}`
    );
  });

  context.subscriptions.push(openChat, explainCurrentFile, summarizeSelection, checkBackendHealth, proposePatch);
}

export function deactivate(): void {
  // no-op
}
