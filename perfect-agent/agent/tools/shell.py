"""Shell execution tool for PERFECT-AGENT."""

from __future__ import annotations

import os
import platform
import shlex
import subprocess
from typing import Any, Dict, List, Optional, Union

from agent import config


def _is_windows() -> bool:
    """Return True when running on Windows (including Cygwin/MSYS2)."""
    return platform.system() == "Windows"


def run(
    cmd: Union[str, List[str]],
    timeout: int = config.SHELL_TIMEOUT,
    check: bool = False,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run *cmd* in a subprocess and return stdout, stderr, and return code.

    On Windows, string commands are executed via ``shell=True`` (so that
    ``.bat``/``.cmd`` files and native Windows CLI syntax work correctly).
    On POSIX (macOS / Linux), string commands are split via ``shlex`` and
    executed without a shell for predictable quoting.

    Parameters
    ----------
    cmd:         Command string or argument list.
    timeout:     Seconds before the process is killed (default from config).
    check:       If True, raise on non-zero exit.
    working_dir: Working directory for the subprocess (defaults to cwd).
    """
    cwd = working_dir or os.getcwd()
    try:
        if isinstance(cmd, str):
            if _is_windows():
                # Windows: use shell=True so .bat/.cmd files and cmd.exe
                # built-ins (dir, copy, …) work natively.
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=check,
                    cwd=cwd,
                    shell=True,
                )
            else:
                # POSIX: split the string into a list to avoid shell
                # metacharacter surprises.
                result = subprocess.run(
                    shlex.split(cmd),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=check,
                    cwd=cwd,
                )
        else:
            # Already a list — pass as-is on every platform.
            result = subprocess.run(
                list(cmd),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
                cwd=cwd,
            )

        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "cmd": cmd if isinstance(cmd, str) else " ".join(cmd),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": "timeout",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "cmd": cmd if isinstance(cmd, str) else " ".join(cmd),
        }
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "error": "non-zero exit",
            "returncode": exc.returncode,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "cmd": cmd if isinstance(cmd, str) else " ".join(cmd),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "cmd": cmd if isinstance(cmd, str) else " ".join(cmd)}
