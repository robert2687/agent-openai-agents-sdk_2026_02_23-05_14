"""Shell execution tool for PERFECT-AGENT."""

from __future__ import annotations

import os
import shlex
import subprocess
from typing import Any, Dict, List, Optional, Union

from agent import config


def run(
    cmd: Union[str, List[str]],
    timeout: int = config.SHELL_TIMEOUT,
    check: bool = False,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run *cmd* in a subprocess and return stdout, stderr, and return code.

    Parameters
    ----------
    cmd:         Command string or argument list.
    timeout:     Seconds before the process is killed (default from config).
    check:       If True, raise on non-zero exit.
    working_dir: Working directory for the subprocess (defaults to cwd).
    """
    cwd = working_dir or os.getcwd()
    try:
        args = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
        result = subprocess.run(
            args,
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
