"""PERFECT-AGENT runner.

Provides:
- ``chat_with_agent(user_message)`` — single-turn helper used by tests / scripts.
- ``run_interactive()`` — blocking REPL for terminal use.
- ``main()`` — CLI entry point (interactive by default; --message for scripting).

Tool-calling loop supports up to ``config.MAX_TOOL_ROUNDS`` rounds so the agent
can chain multiple tool calls before returning its final answer.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure the package root is on sys.path so absolute imports work when run directly.
_pkg_root = Path(__file__).resolve().parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from dotenv import load_dotenv

# Load .env from the repo root (two levels up from this file) or current dir.
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
load_dotenv(override=False)

from agent import config  # noqa: E402 — after dotenv
from agent.fallback_client import check_api_keys, fallback_chat  # noqa: E402
from agent.tools.file import append_file, delete_file, list_dir, read_file, write_file  # noqa: E402
from agent.tools.http import http_get, http_post  # noqa: E402
from agent.tools.shell import run as run_shell  # noqa: E402
from agent.skills.search_code import search_code  # noqa: E402
from agent.skills.git_ops import git_ops  # noqa: E402
from agent.skills.run_tests import run_tests  # noqa: E402
from agent.skills.web_search import web_search  # noqa: E402
from agent.skills.code_review import code_review  # noqa: E402
from agent.skills.todo_scan import todo_scan  # noqa: E402
from agent.skills.list_symbols import list_symbols  # noqa: E402
from agent.skills.dependency_check import dependency_check  # noqa: E402
from agent.skills.code_generator import code_generator  # noqa: E402
from agent.skills.app_creator import app_creator  # noqa: E402
from agent.skills.generate_tests import generate_tests  # noqa: E402
from agent.skills.format_code import format_code  # noqa: E402
from agent.skills.refactor_rename import refactor_rename  # noqa: E402
from agent.skills.create_class import create_class  # noqa: E402
from agent.skills.create_api_endpoint import create_api_endpoint  # noqa: E402

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
LOGGER = logging.getLogger("perfect-agent")

SYSTEM_PROMPT: str = (Path(__file__).with_name("system_prompt.txt")).read_text(encoding="utf-8")

# ── Tool registry ─────────────────────────────────────────────────────────────

_TOOL_MAP: dict = {
    "read_file": read_file,
    "write_file": write_file,
    "append_file": append_file,
    "delete_file": delete_file,
    "list_dir": list_dir,
    "http_get": http_get,
    "http_post": http_post,
    "run_shell": run_shell,
    # skills
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
    "generate_tests": generate_tests,
    "format_code": format_code,
    "refactor_rename": refactor_rename,
    "create_class": create_class,
    "create_api_endpoint": create_api_endpoint,
}

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full text content of a file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Absolute or relative file path."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write (overwrite) a file with the given content, creating parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string", "description": "Text content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Append text to a file (creates it if missing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and subdirectories inside a directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path (default '.')"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Perform an HTTP GET request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "headers": {"type": "object", "additionalProperties": {"type": "string"}},
                    "params": {"type": "object", "additionalProperties": {"type": "string"}},
                    "timeout": {"type": "integer", "default": config.HTTP_TIMEOUT},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_post",
            "description": "Perform an HTTP POST request with a JSON body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "json_body": {"type": "object"},
                    "headers": {"type": "object", "additionalProperties": {"type": "string"}},
                    "timeout": {"type": "integer", "default": config.HTTP_TIMEOUT},
                },
                "required": ["url", "json_body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command and return stdout, stderr, and exit code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "Shell command string (e.g. 'ls -la' or 'python script.py').",
                    },
                    "timeout": {"type": "integer", "default": config.SHELL_TIMEOUT},
                    "working_dir": {"type": "string", "description": "Optional working directory."},
                },
                "required": ["cmd"],
            },
        },
    },
    # ── Skills ────────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": (
                "Recursively search for a pattern (literal or regex) across source files in a directory. "
                "Returns matching lines with file paths and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (literal or regex)."},
                    "root": {"type": "string", "description": "Directory to search (default '.')."},
                    "is_regex": {"type": "boolean", "default": False},
                    "case_sensitive": {"type": "boolean", "default": False},
                    "include_extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Only search files with these extensions, e.g. [\".py\", \".ts\"].",
                    },
                    "max_results": {"type": "integer", "default": 50},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_ops",
            "description": (
                "Perform a Git operation on a repository. "
                "Actions: status, diff, log, add, commit, push, pull, branch, stash."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "diff", "log", "add", "commit", "push", "pull", "branch", "stash"],
                    },
                    "path": {"type": "string", "description": "Repository root (default '.')."},
                    "message": {"type": "string", "description": "Commit message (required for 'commit')."},
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to stage for 'add' (default all).",
                    },
                    "remote": {"type": "string", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name for push/pull/branch."},
                    "n": {"type": "integer", "default": 10, "description": "Number of log entries."},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": (
                "Discover and run the project test suite (pytest preferred, fallback to unittest). "
                "Returns pass/fail counts and failure snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string", "description": "Project root directory (default '.')."},
                    "pattern": {"type": "string", "default": "test_*.py"},
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Extra pytest arguments, e.g. [\"-k\", \"auth\"].",
                    },
                    "timeout": {"type": "integer", "default": 120},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web using DuckDuckGo (no API key required). "
                "Returns titles, URLs, and text snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 8},
                    "timeout": {"type": "integer", "default": 15},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_review",
            "description": (
                "Perform static heuristic analysis on a source file. "
                "Detects TODOs, hardcoded secrets, bare excepts, overly long functions, "
                "and other common code smells. Returns findings with line numbers and severity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the source file."},
                    "max_function_lines": {"type": "integer", "default": 60},
                    "max_line_length": {"type": "integer", "default": 120},
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
                    "root": {"type": "string", "description": "Root directory to scan (default '.')."},
                    "max_results": {"type": "integer", "default": 100},
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
                    "path": {"type": "string", "description": "Path to a source file."},
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
                    "root": {"type": "string", "description": "Project root directory (default '.')."},
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
                    "language": {"type": "string", "enum": ["python", "typescript"], "default": "python"},
                    "name": {"type": "string", "default": "example"},
                    "include_tests": {"type": "boolean", "default": True},
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
                    "root": {"type": "string", "default": "."},
                },
                "required": ["app_type", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_tests",
            "description": "Generate pytest test stubs for all public functions and classes in a Python file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the source Python file."},
                    "output_path": {"type": "string", "description": "Optional path to write the generated stubs."},
                    "framework": {"type": "string", "enum": ["pytest"], "default": "pytest"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "format_code",
            "description": "Format a source file using black (Python), autopep8, or prettier (JS/TS/JSON).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to format."},
                    "formatter": {"type": "string", "enum": ["auto", "black", "autopep8", "prettier"], "default": "auto"},
                    "dry_run": {"type": "boolean", "default": False, "description": "Preview changes without writing."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refactor_rename",
            "description": "Safely rename an identifier across all source files in a directory (with dry-run preview).",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_name": {"type": "string", "description": "Identifier to rename."},
                    "new_name": {"type": "string", "description": "Replacement identifier."},
                    "root": {"type": "string", "default": ".", "description": "Root directory to search."},
                    "whole_word": {"type": "boolean", "default": True},
                    "dry_run": {"type": "boolean", "default": True, "description": "Preview without writing (default True)."},
                    "include_extensions": {"type": "array", "items": {"type": "string"}},
                    "max_files": {"type": "integer", "default": 200},
                },
                "required": ["old_name", "new_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_class",
            "description": "Generate a boilerplate class definition file for Python, TypeScript, or Java.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Class name (PascalCase)."},
                    "language": {"type": "string", "enum": ["python", "typescript", "java"], "default": "python"},
                    "fields": {"type": "array", "items": {"type": "string"}, "description": "Field names."},
                    "methods": {"type": "array", "items": {"type": "string"}, "description": "Additional method names to stub."},
                    "base_class": {"type": "string", "description": "Optional parent class to extend."},
                    "output_path": {"type": "string", "description": "Optional file path to write to."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_api_endpoint",
            "description": "Generate a REST endpoint stub for FastAPI, Flask, Express, or Django.",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "description": "URL route path, e.g. '/users/{user_id}'."},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
                    "handler_name": {"type": "string", "description": "Function/handler name (auto-derived if empty)."},
                    "framework": {"type": "string", "enum": ["fastapi", "flask", "express", "django"], "default": "fastapi"},
                    "output_path": {"type": "string", "description": "Optional file path to write to."},
                    "include_schema": {"type": "boolean", "default": True},
                },
                "required": ["route"],
            },
        },
    },
]


# ── Core agent loop ───────────────────────────────────────────────────────────

def _dispatch_tool(name: str, args: dict) -> str:
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(**args)
    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc)}
    return json.dumps(result) if not isinstance(result, str) else result


def chat_with_agent(user_message: str) -> str:
    """Run a single user message through the agent and return the final reply.

    Supports multi-step tool-calling up to ``config.MAX_TOOL_ROUNDS`` rounds.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for round_idx in range(config.MAX_TOOL_ROUNDS):
        response = fallback_chat(messages, tools=TOOL_SCHEMAS)
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        # Append the assistant's tool-calling turn.
        # Use model_dump() for Pydantic objects (SDK v1+); fall back to raw __dict__.
        def _tc_to_dict(tc) -> dict:
            if hasattr(tc, "model_dump"):
                return tc.model_dump()
            return {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }

        messages.append(
            {
                "role": "assistant",
                "tool_calls": [_tc_to_dict(tc) for tc in msg.tool_calls],
                "content": msg.content or "",
            }
        )

        # Execute all requested tool calls.
        for call in msg.tool_calls:
            tool_name = call.function.name
            try:
                raw_args = call.function.arguments or "{}"
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}

            LOGGER.info("Tool call: %s(%s)", tool_name, list(args.keys()))
            result_content = _dispatch_tool(tool_name, args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": tool_name,
                    "content": result_content,
                }
            )

        LOGGER.debug("Completed tool round %d/%d", round_idx + 1, config.MAX_TOOL_ROUNDS)

    # Max rounds reached — get a final answer without tools.
    LOGGER.warning("Max tool rounds (%d) reached; requesting final answer.", config.MAX_TOOL_ROUNDS)
    final = fallback_chat(messages)
    return final.choices[0].message.content or ""


# ── Interactive REPL ──────────────────────────────────────────────────────────

def run_interactive() -> None:
    """Blocking REPL: read from stdin, print agent responses to stdout."""
    check_api_keys()
    # Ensure UTF-8 output to avoid UnicodeEncodeError on Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(
        "PERFECT-AGENT  (Nemotron -> Qwen -> GPT-4.1 fallback)  |  Ctrl+C or 'exit' to quit\n"
        f"Models: {config.NEMOTRON_MODEL} / {config.QWEN_MODEL} / {config.OPENAI_MODEL}\n"
        "────────────────────────────────────────────────────────────────────────────────"
    )
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            print("Bye.")
            break

        try:
            reply = chat_with_agent(user_input)
        except Exception as exc:  # noqa: BLE001
            print(f"\n[ERROR] {exc}", file=sys.stderr)
            continue

        print(f"\nAgent:\n\n{reply}")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="perfect-agent",
        description="PERFECT-AGENT — deterministic, tool-using assistant.",
    )
    parser.add_argument(
        "--message", "-m",
        metavar="TEXT",
        help="Run a single message non-interactively and print the reply.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging to stderr.",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate API keys early so the error is clear.
    check_api_keys()

    if args.message:
        try:
            print(chat_with_agent(args.message))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        run_interactive()


if __name__ == "__main__":
    main()