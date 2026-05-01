import * as vscode from "vscode";

type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type InvocationResponse = {
  output?: unknown;
  status?: string;
};

export class BackendClient {
  constructor(private readonly config: vscode.WorkspaceConfiguration) {}

  private getBaseUrl(): string {
    const raw = this.config.get<string>("baseUrl", "http://localhost:8000");
    return raw.replace(/\/$/, "");
  }

  private getTimeoutMs(): number {
    return this.config.get<number>("requestTimeoutMs", 30000);
  }

  async health(): Promise<Record<string, unknown>> {
    const url = `${this.getBaseUrl()}/health`;
    return this.requestJson(url, { method: "GET" });
  }

  async invoke(input: ChatMessage[]): Promise<InvocationResponse> {
    const url = `${this.getBaseUrl()}/invocations`;
    return this.requestJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input }),
    });
  }

  private async requestJson(url: string, init: RequestInit): Promise<any> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.getTimeoutMs());

    try {
      const response = await fetch(url, { ...init, signal: controller.signal });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status}: ${text}`);
      }
      return await response.json();
    } finally {
      clearTimeout(timeout);
    }
  }
}
