#!/usr/bin/env python3
"""
Agent Setup and Launch Script
Sets up authentication, MLflow tracing, and starts both Agent Server and Chat UI
"""

import os
import sys
import subprocess
import json
import time
import signal
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

AGENT_DIR = Path(__file__).parent.absolute()
ENV_FILE = AGENT_DIR / '.env'


def detect_backend() -> str:
    return (os.getenv('AGENT_BACKEND') or 'openai').strip().lower() or 'openai'

def print_section(text):
    """Print a section header"""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")

def print_step(text):
    """Print a step"""
    print(f"{BOLD}{BLUE}→{RESET} {text}")

def print_success(text):
    """Print success message"""
    print(f"{GREEN}✓{RESET} {text}")

def print_error(text):
    """Print error message"""
    print(f"{RED}✗{RESET} {text}", file=sys.stderr)

def print_info(text):
    """Print info message"""
    print(f"{YELLOW}ℹ{RESET} {text}")

def run_command(cmd, show_output=False, check=True):
    """Run a shell command"""
    try:
        if show_output:
            result = subprocess.run(cmd, shell=True, check=check, text=True)
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {cmd}")
        if e.stderr:
            print_error(e.stderr)
        return None

def check_databricks_auth():
    """Check if Databricks authentication is configured"""
    print_step("Checking Databricks authentication...")

    result = run_command("databricks auth profiles", check=False)
    if result and result.returncode == 0:
        print_success("Databricks CLI is configured")
        output = result.stdout
        if "DEFAULT" in output:
            print_success("Default profile found")
            return True
        else:
            print_info("No DEFAULT profile found. Running: databricks auth login")
            run_command("databricks auth login", show_output=True)
            return True
    else:
        print_error("Databricks CLI not configured or not installed")
        print_info("Please run: databricks auth login")
        return False

def create_mlflow_experiment():
    """Create MLflow experiment if needed"""
    print_step("Setting up MLflow experiment...")

    # Get username
    result = run_command("databricks current-user me | jq -r .userName", check=False)
    if not result or result.returncode != 0:
        # Try alternative without jq
        result = run_command("databricks current-user me", check=False)
        if result:
            try:
                data = json.loads(result.stdout)
                username = data.get('user_name', 'unknown')
            except:
                username = "unknown"
        else:
            return None
    else:
        username = result.stdout.strip()

    experiment_path = f"/Users/{username}/agents-on-apps"
    print_info(f"Experiment path: {experiment_path}")

    # Try to create experiment
    result = run_command(f'databricks experiments create-experiment "{experiment_path}" 2>/dev/null', check=False)

    if result and result.returncode == 0:
        output = result.stdout.strip()
        try:
            experiment_id = output.split('\n')[-1].strip()
            print_success(f"MLflow experiment created: {experiment_id}")
            return experiment_id
        except:
            pass

    # Try to get existing experiment
    result = run_command(f'databricks experiments get-by-name "{experiment_path}" | jq -r .experiment_id', check=False)
    if result and result.returncode == 0:
        experiment_id = result.stdout.strip()
        if experiment_id and experiment_id != "null":
            print_success(f"Using existing MLflow experiment: {experiment_id}")
            return experiment_id

    print_info("Could not determine experiment ID - you may need to create it manually")
    return None

def update_env_file(experiment_id, backend="databricks"):
    """Update .env file with experiment ID"""
    print_step("Updating .env file...")

    if not ENV_FILE.exists():
        print_info(f"Creating {ENV_FILE}")
        # Copy from example if available
        example_file = AGENT_DIR / '.env.example'
        if example_file.exists():
            ENV_FILE.write_text(example_file.read_text())
        else:
            if backend == "openai":
                env_content = """# Environment configuration for local/OpenAI mode
AGENT_BACKEND=openai
OPENAI_API_KEY=
AGENT_MODEL=gpt-4.1-mini
AGENT_FALLBACK_MODEL=gpt-4.1
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
API_PORT=8000
UI_PORT=7860
"""
            else:
                env_content = """# Environment configuration for Databricks Agent
DATABRICKS_CONFIG_PROFILE=DEFAULT
MLFLOW_EXPERIMENT_ID=
CHAT_APP_PORT=3000
MLFLOW_TRACKING_URI="databricks"
MLFLOW_REGISTRY_URI="databricks-uc"
"""
            ENV_FILE.write_text(env_content)

    if backend == "openai":
        content = ENV_FILE.read_text()
        replacements = {
            "AGENT_BACKEND": "openai",
            "MLFLOW_TRACKING_URI": "sqlite:///mlflow.db",
        }
        for key, value in replacements.items():
            if f"{key}=" in content:
                content = "\n".join(
                    f"{key}={value}" if line.startswith(f"{key}=") else line
                    for line in content.splitlines()
                )
            else:
                content += f"\n{key}={value}"
        ENV_FILE.write_text(content + ("\n" if not content.endswith("\n") else ""))
        print_success("Configured local/OpenAI defaults")
        return

    # Update MLFLOW_EXPERIMENT_ID if we have it
    if experiment_id:
        content = ENV_FILE.read_text()
        if 'MLFLOW_EXPERIMENT_ID=' in content:
            content = content.replace(
                'MLFLOW_EXPERIMENT_ID=',
                f'MLFLOW_EXPERIMENT_ID={experiment_id}'
            )
            ENV_FILE.write_text(content)
            print_success(f"Updated MLFLOW_EXPERIMENT_ID={experiment_id}")

    print_success(".env file configured")

def check_dependencies(backend="databricks"):
    """Check required Python packages"""
    print_step("Checking Python dependencies...")

    required_packages = [
        "fastapi",
        "uvicorn",
        "mlflow",
        "openai-agents",
        "python-dotenv",
    ]
    if backend == "databricks":
        required_packages.append("databricks-openai")

    missing = []
    for package in required_packages:
        # Convert package name to import name (e.g., python-dotenv -> dotenv)
        import_name = package.replace("-", "_").replace("python_dotenv", "dotenv")
        result = run_command(f'python3 -c "import {import_name}"', check=False)
        if result and result.returncode == 0:
            print_success(f"{package} is installed")
        else:
            missing.append(package)

    if missing:
        print_info(f"Installing missing packages: {', '.join(missing)}")
        run_command(f"pip install -q {' '.join(missing)}", show_output=True)

    print_success("All dependencies available")

def start_services(backend="databricks"):
    """Start Agent Server and Chat UI"""
    print_section("STARTING SERVICES")

    # Import dotenv here after dependencies are installed
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        print_error("python-dotenv not installed. Installing...")
        run_command("pip install -q python-dotenv", show_output=True)
        from dotenv import load_dotenv  # type: ignore

    # Load environment
    load_dotenv(ENV_FILE)

    if backend == "openai":
        print_info("Agent Server will run on: http://localhost:8000")
        print_info("Health check: http://localhost:8000/health")
        print_step("Starting local/OpenAI backend...")
        print_info("Press Ctrl+C to stop the server\n")
        run_command(f"cd {AGENT_DIR} && uv run start-server --port 8000 --reload", show_output=True)
        return

    port = os.getenv('CHAT_APP_PORT', '3000')
    print_info(f"Agent Server will run on: http://localhost:8000")
    print_info(f"Chat UI will run on: http://localhost:{port}")

    print_step("Starting Agent Server and Chat UI...")
    print_info("Press Ctrl+C to stop both services\n")

    result = run_command(f"cd {AGENT_DIR} && uv run start-app --port 8000", show_output=True, check=False)

    if result and result.returncode != 0:
        print_info("Fallback: starting server manually...")
        run_command(f"cd {AGENT_DIR} && uv run start-server --port 8000 --reload", show_output=True)

def open_browser():
    """Open browser to chat UI"""
    time.sleep(3)  # Wait for services to start

    port = os.getenv('CHAT_APP_PORT', '3000')
    url = f"http://localhost:{port}"

    import platform
    system = platform.system()

    if system == 'Darwin':  # macOS
        os.system(f'open "{url}"')
    elif system == 'Linux':
        # Try xdg-open, if it fails, print a message
        result = os.system(f'xdg-open "{url}" 2>/dev/null')
        if result != 0:
            print_info(f"Please open {url} in your browser")
    elif system == 'Windows':
        os.system(f'start "" "{url}"')
    else:
        print_info(f"Please open {url} in your browser")

def main():
    """Main setup and launch routine"""
    try:
        print_section("AGENT SETUP & LAUNCH")
        backend = detect_backend()

        if backend == "openai":
            print("\n[1/3] CONFIGURE LOCAL ENVIRONMENT")
            update_env_file(None, backend="openai")

            print("\n[2/3] VERIFY DEPENDENCIES")
            check_dependencies(backend="openai")

            print("\n[3/3] START AGENT SERVER")
            start_services(backend="openai")
            return

        # Step 1: Check Databricks auth
        print("\n[1/5] AUTHENTICATE WITH DATABRICKS")
        if not check_databricks_auth():
            print_error("Databricks authentication required. Exiting.")
            sys.exit(1)

        # Step 2: Create MLflow experiment
        print("\n[2/5] CONFIGURE MLFLOW TRACING")
        experiment_id = create_mlflow_experiment()

        # Step 3: Update .env
        print("\n[3/5] CONFIGURE ENVIRONMENT")
        update_env_file(experiment_id, backend="databricks")

        # Step 4: Check dependencies
        print("\n[4/5] VERIFY DEPENDENCIES")
        check_dependencies(backend="databricks")

        # Step 5: Start services
        print("\n[5/5] START AGENT SERVER & CHAT UI")
        start_services(backend="databricks")

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Shutdown requested...{RESET}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
