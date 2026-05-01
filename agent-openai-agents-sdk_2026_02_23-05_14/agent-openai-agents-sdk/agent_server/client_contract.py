from __future__ import annotations


def build_client_contract() -> dict:
    """Shared product contract for IDE + Web clients.

    Keep this endpoint stable so clients can render capabilities and policies
    from backend configuration instead of hard-coded UI assumptions.
    """
    return {
        "platform_strategy": {
            "backend": "single deployable backend",
            "clients": ["vscode-extension", "web-ui"],
            "note": "Both clients share the same REST and streaming transport endpoints.",
        },
        "layers": {
            "core_agent_runtime": [
                "reasoning",
                "tool orchestration",
                "memory",
                "retry policy",
                "model fallback",
            ],
            "transport_api": [
                "GET /health",
                "GET /client-capabilities",
                "POST /invocations",
                "POST /v1/chat/completions",
            ],
            "clients": [
                "VS Code extension UI",
                "Web chat UI",
            ],
        },
        "ide_actions_mvp": [
            {
                "id": "open_chat",
                "label": "Open Chat",
                "safe": True,
                "mode": "read-only",
            },
            {
                "id": "explain_current_file",
                "label": "Explain Current File",
                "safe": True,
                "mode": "read-only",
            },
            {
                "id": "summarize_selection",
                "label": "Summarize Selection",
                "safe": True,
                "mode": "read-only",
            },
            {
                "id": "check_backend_health",
                "label": "Check Backend Health",
                "safe": True,
                "mode": "read-only",
            },
            {
                "id": "propose_patch",
                "label": "Propose Patch",
                "safe": True,
                "mode": "write-proposal-with-confirmation",
            },
        ],
        "web_actions_mvp": [
            {
                "id": "qa_chat",
                "label": "Q&A Chat",
                "safe": True,
                "mode": "read-only",
            },
            {
                "id": "repo_analysis",
                "label": "Repository Analysis",
                "safe": True,
                "mode": "read-only",
            },
            {
                "id": "api_call_assist",
                "label": "API Call Assistant",
                "safe": True,
                "mode": "read-only",
            },
            {
                "id": "tool_run",
                "label": "Run Tool (Policy Controlled)",
                "safe": True,
                "mode": "guarded",
            },
            {
                "id": "export_result",
                "label": "Export Result",
                "safe": True,
                "mode": "read-only",
            },
        ],
        "production_basics": {
            "auth": ["jwt", "oauth2"],
            "tenant_isolation": "required",
            "rate_limit_scope": "per-user",
            "audit_logs": "required",
            "tool_permission_policy": "allowlist + confirmation for writes",
        },
    }
