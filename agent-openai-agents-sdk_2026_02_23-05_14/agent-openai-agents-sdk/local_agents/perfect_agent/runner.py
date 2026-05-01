import json
import importlib
from pathlib import Path

from .fallback_client import fallback_chat
from .skills import (
    search_code,
    git_ops,
    run_tests,
    web_search,
    code_review,
    todo_scan,
    list_symbols,
    dependency_check,
    code_generator,
    app_creator,
)

SYSTEM_PROMPT = Path(__file__).with_name("system_prompt.txt").read_text()

TOOLS = {
    "read_file": "local_agents.perfect_agent.tools.file:read_file",
    "write_file": "local_agents.perfect_agent.tools.file:write_file",
    "http_get": "local_agents.perfect_agent.tools.http:http_get",
    "http_post": "local_agents.perfect_agent.tools.http:http_post",
    "run_shell": "local_agents.perfect_agent.tools.shell:run",
}

# Skills are callables loaded directly (not via importlib string paths)
_SKILL_MAP = {
    "search_code": search_code,
    "git_ops": git_ops,
    "run_tests": run_tests,
    "web_search": web_search,
    "code_review": code_review,
    "todo_scan": todo_scan,
    "list_symbols": list_symbols,
    "dependency_check": dependency_check,
    "code_generator": code_generator,
    "app_creator": app_creator,
}

_SKILL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for a pattern across source files. Returns file:line:snippet matches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "root": {"type": "string"},
                    "is_regex": {"type": "boolean"},
                    "case_sensitive": {"type": "boolean"},
                    "include_extensions": {"type": "array", "items": {"type": "string"}},
                    "max_results": {"type": "integer"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_ops",
            "description": "Git operations: status, diff, log, add, commit, push, pull, branch, stash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "diff", "log", "add", "commit", "push", "pull", "branch", "stash"]},
                    "path": {"type": "string"},
                    "message": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string"}},
                    "remote": {"type": "string"},
                    "branch": {"type": "string"},
                    "n": {"type": "integer"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the test suite (pytest/unittest) and return structured pass/fail results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                    "pattern": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                    "timeout": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web via DuckDuckGo (no API key). Returns title, url, snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "timeout": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_review",
            "description": "Static analysis of a source file: TODOs, hardcoded secrets, long functions, bare excepts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_function_lines": {"type": "integer"},
                    "max_line_length": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_scan",
            "description": "Scan a directory recursively for TODO/FIXME/HACK markers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_symbols",
            "description": "Extract symbols from a source file (Python, JS, TS).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dependency_check",
            "description": "Inspect requirements.txt, pyproject.toml, and package.json dependencies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_generator",
            "description": "Generate starter code files for common coding tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["function", "class", "script", "api_handler"]},
                    "language": {"type": "string", "enum": ["python", "typescript"]},
                    "name": {"type": "string"},
                    "include_tests": {"type": "boolean"},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "app_creator",
            "description": "Scaffold a starter app on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_type": {"type": "string", "enum": ["python_cli", "fastapi", "node_api", "static_web"]},
                    "name": {"type": "string"},
                    "root": {"type": "string"},
                },
                "required": ["app_type", "name"],
            },
        },
    },
]

def load_tool(name):
    if name in _SKILL_MAP:
        return _SKILL_MAP[name]
    module_path, func_name = TOOLS[name].split(":")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def call_tool(name, args):
    return load_tool(name)(**args)


def tool_schemas():
    base = [{"type": "function", "function": {"name": name}} for name in TOOLS]
    return base + _SKILL_SCHEMAS

def chat_with_agent(user_message):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    response = fallback_chat(messages, tools=tool_schemas())
    msg = response.choices[0].message

    if msg.tool_calls:
        tool_results = []
        for call in msg.tool_calls:
            tool_name = call.function.name
            args = json.loads(call.function.arguments or "{}")
            result = call_tool(tool_name, args)
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": tool_name,
                    "content": json.dumps(result),
                }
            )

        messages.append({"role": "assistant", "tool_calls": msg.tool_calls})
        messages.extend(tool_results)

        final = fallback_chat(messages)
        return final.choices[0].message.content

    return msg.content


def main():
    print("PERFECT-AGENT CLI (Nemotron → Qwen → GPT‑4.1 fallback). Ctrl+C to exit.")
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in {"exit", "quit"}:
                break
            print("\nAgent:\n")
            print(chat_with_agent(user_input))
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
