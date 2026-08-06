"""One-command launcher for the whole travel ecosystem (local dev).

Starts the 3 MCP servers and both A2A remote agents as subprocesses, waits for
each port to accept connections, then launches the Gradio host UI in the
foreground.

    uv run python run_all.py                  # everything + UI
    uv run python run_all.py --backend-only   # services only (for tests)

Ctrl-C stops everything. Data and the vector DB are built automatically on first
run if missing.
"""
from __future__ import annotations

import argparse
import atexit
import os
import signal
import socket
import subprocess
import sys
import time

from common.config import CHROMA_DIR, POLICY_DOCS_DIR, SEED_DIR, settings
from common.logging_utils import enable_utf8_stdout

# This launcher prints ✓ / • / ↓ status characters, which raise
# UnicodeEncodeError on a cp1252 Windows console. Every service entry point does
# this too; the launcher must not be the exception.
enable_utf8_stdout()

SERVICES = [
    ("MCP1 travel-knowledge", "mcp_server_1.main", settings.mcp1_port),
    ("MCP2 travel-operations", "mcp_server_2.main", settings.mcp2_port),
    ("MCP3 travel-policies", "mcp_server_3.main", settings.mcp3_port),
    ("Remote Agent 1 (LangGraph)", "remote_agent_1.main", settings.rag_agent_port),
    ("Remote Agent 2 (Agno)", "remote_agent_2.main", settings.workflow_agent_port),
]

_procs: list[subprocess.Popen] = []


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_port(port: int, timeout: float = 60.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if _port_open(port):
            return True
        time.sleep(0.5)
    return False


def _kill_hint(port: int) -> str:
    """Platform-appropriate one-liner for freeing a stuck port."""
    if sys.platform == "win32":
        return (f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{port}.*LISTENING\') '
                f'do taskkill /F /PID %a')
    return f"lsof -ti tcp:{port} | xargs kill -9"


def _stop_all() -> None:
    for proc in _procs:
        if proc.poll() is None:
            proc.terminate()
    for proc in _procs:
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def _run(module: str) -> None:
    subprocess.run([sys.executable, "-m", module], check=True)


def _ensure_data() -> None:
    if not SEED_DIR.exists() or not any(SEED_DIR.glob("*.csv")):
        print("Seed data missing — generating synthetic demo data...")
        _run("scripts.generate_data")
    if not POLICY_DOCS_DIR.exists() or not any(POLICY_DOCS_DIR.glob("*.md")):
        print("Policy documents missing — generating them...")
        _run("scripts.generate_policies")
    if not CHROMA_DIR.exists() or not any(CHROMA_DIR.iterdir()):
        print("Vector DB missing — building it now (throttled, a few minutes)...")
        _run("ingest.build_vectordb")


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the travel agent ecosystem.")
    parser.add_argument("--backend-only", action="store_true",
                        help="Start MCP servers and remote agents without the UI.")
    args = parser.parse_args()

    if not settings.llm_configured:
        sys.exit("GOOGLE_API_KEY is not set in .env — add your free Gemini key "
                 "from https://aistudio.google.com/apikey first.")

    _ensure_data()
    atexit.register(_stop_all)

    # Children inherit this console, so force UTF-8 in them too rather than
    # relying on each one reconfiguring itself before its first print.
    child_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    for label, module, port in SERVICES:
        if _port_open(port):
            print(f"  • {label} already running on :{port} — reusing")
            continue
        print(f"Starting {label} on :{port} ...")
        _procs.append(subprocess.Popen([sys.executable, "-m", module], env=child_env))

    failed = False
    for label, _, port in SERVICES:
        if _wait_for_port(port):
            print(f"  ✓ {label} ready on :{port}")
        else:
            print(f"  ✗ {label} did NOT start on :{port}")
            failed = True
    if failed:
        _stop_all()
        sys.exit("One or more services failed to start — see the logs above.")

    if args.backend_only:
        print("\nBackend services are up. Press Ctrl-C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
        return

    # A UI left over from a previous run holds the port; Gradio's own error for
    # this is a bare traceback, so check first and explain what to do.
    if _port_open(settings.ui_port):
        print(f"\nThe UI port :{settings.ui_port} is already in use — a host UI from "
              f"an earlier run is probably still open.\n")
        print(f"  Either just use the one already running:  "
              f"http://{settings._client_host}:{settings.ui_port}")
        print(f"  or free the port and re-run:               "
              f"{_kill_hint(settings.ui_port)}")
        print(f"  or pick another port:                      "
              f"UI_PORT=7861 uv run python run_all.py")
        print("\nBackend services are still running. Press Ctrl-C to stop them.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
        return

    print("\nAll backend services are up. Launching the travel planner UI...\n")
    from host_agent.gradio_app import launch_ui

    try:
        launch_ui()
    except OSError as exc:
        # Lost a race for the port, or the bind was refused.
        sys.exit(f"\nCould not start the UI on :{settings.ui_port}: {exc}\n"
                 f"Free the port ({_kill_hint(settings.ui_port)}) or set UI_PORT "
                 f"to something else.")


if __name__ == "__main__":
    try:
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    except Exception:
        pass
    main()
