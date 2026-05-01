"""File-system tools for PERFECT-AGENT."""

from __future__ import annotations

import os
from typing import Any, Dict


def read_file(path: str) -> str:
    """Return the full text content of *path*, or an error string."""
    if not os.path.exists(path):
        return f"ERROR: File not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        return f"ERROR: Cannot read {path}: {exc}"


def write_file(path: str, content: str) -> str:
    """Write *content* to *path* (creating parent directories as needed)."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return f"File written: {path}"
    except OSError as exc:
        return f"ERROR: Cannot write {path}: {exc}"


def append_file(path: str, content: str) -> str:
    """Append *content* to *path*. Creates the file if it does not exist."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(content)
        return f"Appended to: {path}"
    except OSError as exc:
        return f"ERROR: Cannot append to {path}: {exc}"


def delete_file(path: str) -> str:
    """Delete *path* if it exists."""
    if not os.path.exists(path):
        return f"ERROR: File not found: {path}"
    try:
        os.remove(path)
        return f"Deleted: {path}"
    except OSError as exc:
        return f"ERROR: Cannot delete {path}: {exc}"


def list_dir(path: str = ".") -> Dict[str, Any]:
    """List files and directories inside *path*.

    Returns a dict with ``files`` and ``dirs`` lists, or an ``error`` key.
    """
    if not os.path.exists(path):
        return {"error": f"Path not found: {path}"}
    if not os.path.isdir(path):
        return {"error": f"Not a directory: {path}"}
    try:
        entries = os.listdir(path)
        files = sorted(e for e in entries if os.path.isfile(os.path.join(path, e)))
        dirs = sorted(e for e in entries if os.path.isdir(os.path.join(path, e)))
        return {"path": os.path.abspath(path), "files": files, "dirs": dirs}
    except OSError as exc:
        return {"error": str(exc)}
