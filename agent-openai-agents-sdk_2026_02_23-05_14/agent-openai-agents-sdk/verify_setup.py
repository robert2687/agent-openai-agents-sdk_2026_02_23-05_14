#!/usr/bin/env python3
"""Setup verification for local/OpenAI and optional Databricks modes."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def detect_backend(env_vars: dict[str, str]) -> str:
    backend = (env_vars.get("AGENT_BACKEND", "") or os.getenv("AGENT_BACKEND", "")).strip().lower()
    if backend in {"openai", "databricks"}:
        return backend
    return "openai" if (env_vars.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")) else "databricks"


def parse_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def check_command(cmd: str, name: str) -> bool:
    """Check if a command exists"""
    if shutil.which(cmd):
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.strip() or result.stderr.strip()
            print(f"✓ {name} is installed: {version.split()[0] if version else 'version unknown'}")
            return True
        except Exception:
            print(f"✓ {name} is installed")
            return True
    else:
        print(f"✗ {name} is NOT installed")
        return False


def check_env_file() -> tuple[bool, str]:
    """Check if .env file exists and has required variables for configured backend mode."""
    env_path = Path(".env")
    if not env_path.exists():
        print("✗ .env file not found")
        return False, "unknown"

    print("✓ .env file exists")
    env_vars = parse_env_file(env_path)
    backend = detect_backend(env_vars)

    print(f"✓ Backend mode: {backend}")

    tracking_uri = env_vars.get("MLFLOW_TRACKING_URI") or os.getenv("MLFLOW_TRACKING_URI") or "sqlite:///mlflow.db"
    print(f"✓ MLflow tracking URI: {tracking_uri}")

    if backend == "openai":
        has_openai = bool(env_vars.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))
        if not has_openai:
            print("  ⚠ OPENAI_API_KEY is missing (required for AGENT_BACKEND=openai)")
        return has_openai, backend

    optional_vars = ["DATABRICKS_CONFIG_PROFILE", "DATABRICKS_HOST", "DATABRICKS_TOKEN"]
    has_auth = any(env_vars.get(var) for var in optional_vars)
    if not has_auth:
        print(f"  ⚠ No authentication configured (need one of: {', '.join(optional_vars)})")

    return has_auth, backend


def check_databricks_auth() -> bool:
    """Check if Databricks authentication is working"""
    try:
        result = subprocess.run(
            ["databricks", "current-user", "me"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Try to extract username
            import json
            try:
                user_info = json.loads(result.stdout)
                username = user_info.get("userName", "unknown")
                print(f"✓ Databricks authentication working (user: {username})")
                return True
            except Exception:
                print("✓ Databricks authentication working")
                return True
        else:
            print("✗ Databricks authentication failed")
            print(f"  Error: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Databricks CLI timeout (check network connection)")
        return False
    except Exception as e:
        print(f"✗ Error checking Databricks auth: {e}")
        return False


def check_python_version() -> bool:
    """Check Python version"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} (>= 3.11 required)")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (>= 3.11 required)")
        return False


def check_dependencies(backend: str) -> bool:
    """Check if Python dependencies are installed for the selected backend."""
    try:
        import fastapi
        import mlflow
        import uvicorn
        import agents  # noqa: F401
        if backend == "databricks":
            import databricks.sdk  # noqa: F401
        print("✓ Core Python dependencies installed")
        return True
    except ImportError as e:
        print(f"✗ Missing Python dependencies: {e}")
        print("  Run: pip install -e .  or  uv sync")
        return False


def print_next_steps(backend: str) -> None:
    print()
    print("You're ready to start the agent:")
    if backend == "openai":
        print("  start-server --reload")
        print("  or: docker compose up --build")
        print("  Health check: http://localhost:8000/health")
    else:
        print("  start-server --reload")
        print("  Optional full app: start-app")


def main():
    print("=" * 60)
    print("Agent Setup Verification")
    print("=" * 60)
    print()

    checks = []

    print("1. Checking Python...")
    checks.append(check_python_version())
    print()

    env_path = Path(".env")
    env_vars = parse_env_file(env_path) if env_path.exists() else {}
    backend = detect_backend(env_vars)
    print(f"Selected backend: {backend}")
    print()

    print("2. Checking prerequisites...")
    uv_installed = check_command("uv", "uv")
    checks.append(uv_installed or check_command("pip", "pip"))
    if backend == "databricks":
        checks.append(check_command("databricks", "Databricks CLI"))
        checks.append(check_command("node", "Node.js"))
    else:
        print("✓ Databricks CLI not required for OpenAI mode")
        node_installed = shutil.which("node") is not None
        if node_installed:
            print("✓ Node.js is installed (optional for full web UI)")
        else:
            print("ℹ Node.js not installed (optional unless you want the Databricks-style web UI)")
    print()

    print("3. Checking configuration...")
    env_ok, backend = check_env_file()
    checks.append(env_ok)
    print()

    if backend == "databricks":
        print("4. Checking Databricks authentication...")
        checks.append(check_databricks_auth())
        print()
    else:
        print("4. Checking OpenAI authentication...")
        if os.getenv("OPENAI_API_KEY"):
            print("✓ OPENAI_API_KEY available in environment")
            checks.append(True)
        else:
            env_path = Path(".env")
            env_vars = parse_env_file(env_path) if env_path.exists() else {}
            has_key = bool(env_vars.get("OPENAI_API_KEY"))
            checks.append(has_key)
            print("✓ OPENAI_API_KEY configured" if has_key else "✗ OPENAI_API_KEY missing")
        print()

    print("5. Checking Python dependencies...")
    checks.append(check_dependencies(backend))
    print()

    print("=" * 60)
    if all(checks):
        print("✓ ALL CHECKS PASSED!")
        print_next_steps(backend)
    else:
        print("✗ SOME CHECKS FAILED")
        print()
        print("Please fix the issues above and run this script again.")
        print("For help, see QUICKSTART.md")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
