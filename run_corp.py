#!/usr/bin/env python3
"""
GraphCorp CLI Entrypoint & Autonomous Enterprise Runner.
Target Track: Track 01 (Agents That Act on Connected Data) | WeMakeDevs Graph Hacks

Usage:
  python run_corp.py --prompt "Build dev-vault: an enterprise developer secret store CLI with AES-256 GCM"
  python run_corp.py --no-ui
"""

import sys
import os
import time
import argparse
import threading
import uvicorn
from typing import Dict, Any

from src.db.client import get_falkordb_client, get_connection_metadata
from src.db.schema import seed_initial_enterprise
from src.orchestration.engine import CompanyOrchestrator
from src.ui.server import broadcast_event, create_app

# ANSI Terminal Styling
WHITE = "[97m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
PURPLE = "\033[95m"
BLUE = "\033[94m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(port: int, serve_ui: bool, meta: Dict[str, Any]):
    banner = f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════════╗
║                          G R A P H C O R P                               ║
║           Autonomous AI Software Enterprise Powered by FalkorDB          ║
║      Track 01: Agents That Act on Connected Data | WeMakeDevs Hackathon  ║
╚══════════════════════════════════════════════════════════════════════════╝{RESET}
{DIM}• FalkorDB Engine Target:{RESET} {BOLD}{meta.get('graph', 'graphcorp')}{RESET} ({meta.get('mode', 'READY')})
{DIM}• Target Workspace:{RESET}       {BOLD}workspace/dev-vault{RESET} (Genuine Git + AST + Pytest)
"""
    if serve_ui:
        banner += f"{DIM}• Mission Control UI:{RESET}     {BOLD}{GREEN}http://localhost:{port}{RESET} (Cytoscape.js Living Canvas)\n"
    print(banner)


def terminal_event_logger(event: Dict[str, Any]):
    """Pretty prints structured agent events to the console."""
    action = event.get("action", "")
    role = event.get("role", "SYSTEM")
    agent_id = event.get("agent_id", role)
    details = event.get("details", {})
    ts = time.strftime("%H:%M:%S", time.localtime(event.get("timestamp", time.time())))

    color = BLUE
    if "CEO" in role:
        color = CYAN
    elif "CTO" in role:
        color = PURPLE
    elif "PM" in role:
        color = YELLOW
    elif "Dev" in role:
        color = CYAN
    elif "QA" in role:
        color = GREEN if "APPROVED" in action else YELLOW
    elif "DevOps" in role:
        color = GREEN

    tag = f"{color}[{ts}] [{role:9s}]{RESET}"

    if action == "CEO_CHARTER_APPROVED":
        print(f"{tag} {BOLD}Product Charter Approved:{RESET} '{details.get('name')}'")
    elif action == "CTO_ARCHITECTURE_FROZEN":
        print(f"{tag} {BOLD}Architecture Frozen:{RESET} ADR={details.get('adr_id')} Components={details.get('components')}")
    elif action == "PM_DAG_DISPATCHED":
        print(f"{tag} {BOLD}Task DAG Dispatched:{RESET} {details.get('ready_count')} tasks READY out of {details.get('total_tasks')}")
    elif action == "DEV_PR_OPENED":
        print(f"{tag} {BOLD}Opened PR:{RESET} {details.get('pr_id')} (Branch: {details.get('branch')}) Commit: {event.get('git_sha', '')[:7]}")
    elif action == "QA_PR_APPROVED":
        passed = details.get("tests_passed", 0)
        print(f"{tag} {BOLD}{GREEN}✓ QA Sign-off APPROVED:{RESET} PR {details.get('pr_id')} (Pytest: {passed} passed, exit code 0)")
    elif action == "DEVOPS_MERGED_TASK_DONE":
        print(f"{tag} {BOLD}{GREEN}⚡ DevOps Merge to main:{RESET} Task {details.get('task_id')} DONE -> Unblocked {details.get('unblocked_count')} task(s)")
    else:
        print(f"{tag} {action}: {details}")

    # Mirror to web visualizer SSE stream
    broadcast_event(event)


def start_server_daemon(host: str, port: int, graph: Any):
    """Launches FastAPI web server in background daemon thread."""
    app = create_app(graph=graph)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def main():
    parser = argparse.ArgumentParser(
        description="GraphCorp: Autonomous AI Software Enterprise Powered by FalkorDB",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Build dev-vault: an enterprise developer secret store CLI with AES-256 GCM",
        help="Founder product prompt guiding autonomous software creation."
    )
    parser.add_argument(
        "--serve-ui",
        action="store_true",
        default=True,
        help="Launch the real-time FastAPI + Cytoscape.js visualizer web console."
    )
    parser.add_argument(
        "--no-ui",
        dest="serve_ui",
        action="store_false",
        help="Disable the web visualizer and run in pure terminal mode."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the Mission Control web server (default: 8000)."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address for the web server (default: 0.0.0.0)."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=15,
        help="Max orchestrator delivery loop iterations (default: 15)."
    )
    args = parser.parse_args()

    # 1. Connect to FalkorDB Engine
    graph = get_falkordb_client()
    seed_initial_enterprise(graph, clean=True)
    meta = get_connection_metadata()

    # 2. Print Welcome Banner
    print_banner(port=args.port, serve_ui=args.serve_ui, meta=meta)

    # 3. Launch Web UI if enabled
    if args.serve_ui:
        start_server_daemon(host=args.host, port=args.port, graph=graph)
        time.sleep(0.5)

    # 4. Instantiate Orchestrator
    orchestrator = CompanyOrchestrator(
        graph=graph,
        workspace_dir="workspace/dev-vault",
        event_callback=terminal_event_logger
    )

    print(f"{BOLD}{WHITE}>>> INGESTING FOUNDER PROMPT:{RESET} \"{args.prompt}\"\n")
    start_time = time.time()

    # 5. Run Autonomous Enterprise
    summary = orchestrator.run_project(founder_prompt=args.prompt, max_iterations=args.iterations)

    elapsed = round(time.time() - start_time, 2)
    print(f"\n{BOLD}{GREEN}══════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{GREEN}✓ AUTONOMOUS SOFTWARE SPRINT COMPLETE IN {elapsed}s{RESET}")
    print(f"{BOLD}{GREEN}══════════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{DIM}• Project Artifact:{RESET}      {BOLD}workspace/dev-vault{RESET}")
    print(f"{DIM}• Tasks Completed:{RESET}       {BOLD}{len(summary.get('tasks_completed', []))}{RESET} ({', '.join(summary.get('tasks_completed', []))})")
    print(f"{DIM}• Pull Requests Merged:{RESET}  {BOLD}{len(summary.get('prs_merged', []))}{RESET}")
    print(f"{DIM}• Automated Pytest Run:{RESET}  {BOLD}{GREEN}{summary.get('final_test_passed', 0)} Passed, 0 Failed (Exit Code: {summary.get('final_test_exit_code', 0)}){RESET}")
    print(f"{DIM}• FalkorDB Graph State:{RESET}  {BOLD}{summary.get('graph_nodes', 0)} Nodes, {summary.get('graph_edges', 0)} Relationships{RESET}")
    print(f"{DIM}• Telemetry Events:{RESET}      {BOLD}{summary.get('events_emitted', 0)} emitted{RESET}")

    if args.serve_ui:
        print(f"\n{BOLD}{CYAN}⚡ Mission Control Dashboard active at: http://localhost:{args.port}{RESET}")
        print(f"{DIM}(Press Ctrl+C to terminate server){RESET}")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Shutting down GraphCorp Mission Control.{RESET}")


if __name__ == "__main__":
    main()
