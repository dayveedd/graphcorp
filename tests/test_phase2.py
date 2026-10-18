"""
Phase 2 Automated Integration Test: Multi-Agent Autonomous Brain & Orchestrator.
Validates end-to-end autonomous lifecycle execution:
CEO -> CTO -> PM -> Dev -> QA -> DevOps
Verifying genuine disk artifacts, Git provenance, and FalkorDB graph state.
"""

import os
import shutil
import pytest

from src.db.client import get_falkordb_client, reset_client
from src.db.schema import seed_initial_enterprise
from src.orchestration.engine import CompanyOrchestrator
from src.mcp.git_tools import GitWorkspaceTool
from src.mcp.bash_tools import mcp_bash_test_runner
from src.db.in_memory_graph import InMemoryFalkorGraph


WORKSPACE_DIR = os.path.abspath("workspace/dev-vault")


@pytest.fixture(scope="module")
def orchestrator_run_result():
    """Runs the full autonomous project lifecycle once for the test module."""
    reset_client()
    graph = get_falkordb_client(force_new=True)
    seed_initial_enterprise(graph, clean=True)

    if os.path.exists(WORKSPACE_DIR):
        shutil.rmtree(WORKSPACE_DIR)

    captured_events = []

    def event_listener(evt):
        captured_events.append(evt)

    orchestrator = CompanyOrchestrator(
        graph=graph,
        workspace_dir=WORKSPACE_DIR,
        event_callback=event_listener
    )

    prompt = "Build dev-vault: an encrypted secret store with AES-256 GCM crypto module and CLI parser"
    result = orchestrator.run_project(founder_prompt=prompt, max_iterations=12)

    return {
        "result": result,
        "graph": graph,
        "events": captured_events,
        "workspace_dir": WORKSPACE_DIR
    }


def test_real_files_created_in_workspace(orchestrator_run_result):
    """
    Verification a): Real files (src/crypto.py, tests/test_crypto.py, etc.)
    exist on disk in workspace/dev-vault.
    """
    ws = orchestrator_run_result["workspace_dir"]
    expected_files = [
        "pyproject.toml",
        "README.md",
        "src/__init__.py",
        "src/crypto.py",
        "src/storage.py",
        "src/cli.py",
        "tests/__init__.py",
        "tests/test_crypto.py",
        "tests/test_storage.py",
        "tests/test_cli.py",
        "tests/test_security.py",
        "RELEASE.md"
    ]

    for f in expected_files:
        full_path = os.path.join(ws, f)
        assert os.path.isfile(full_path), f"File {f} must physically exist on disk at {full_path}"
        assert os.path.getsize(full_path) > 0, f"File {f} must not be empty"


def test_real_git_history_and_merges(orchestrator_run_result):
    """
    Verification b): Real git commit history shows feature branch creation
    and clean merge commits on main.
    """
    ws = orchestrator_run_result["workspace_dir"]
    git_tool = GitWorkspaceTool(workspace_dir=ws)

    # Repository status must be clean on main
    status = git_tool.get_status()
    assert status["branch"] == "main"
    assert status["is_clean"] is True

    # Check commit log history
    logs = git_tool.get_log(max_count=25)
    assert len(logs) >= 5, f"Expected at least 5 git commits, got {len(logs)}"

    # Check for commits from tasks
    commit_messages = [l["message"] for l in logs]
    has_crypto_commit = any(
        "crypto" in msg.lower() or "vaultcipher" in msg.lower() or "aes" in msg.lower()
        for msg in commit_messages
    )
    has_merge_commit = any("merge" in msg.lower() for msg in commit_messages)
    assert has_crypto_commit, "Commit history must include crypto engine work"
    assert has_merge_commit, "Commit history must include verified release merges"


def test_falkordb_nodes_and_provenance(orchestrator_run_result):
    """
    Verification c): FalkorDB nodes reflect final status DONE and MERGED.
    """
    graph = orchestrator_run_result["graph"]

    if isinstance(graph, InMemoryFalkorGraph):
        tasks = graph.find_nodes("Task")
        assert len(tasks) >= 5
        done_tasks = [t for t in tasks if t.properties.get("status") == "DONE"]
        assert len(done_tasks) == len(tasks), f"All tasks in graph must be DONE. Tasks: {[(t.id, t['status']) for t in tasks]}"

        prs = graph.find_nodes("PR")
        assert len(prs) >= 3
        merged_prs = [p for p in prs if p.properties.get("status") == "MERGED"]
        assert len(merged_prs) == len(prs), "All PRs in graph must be MERGED"

        reviewed_edges = [e for e in graph.edges.values() if e.relation == "REVIEWED"]
        assert len(reviewed_edges) >= 3
        for e in reviewed_edges:
            assert e.properties.get("decision") == "APPROVED"
    else:
        # Live FalkorDB
        res_tasks = graph.query("MATCH (t:Task) RETURN count(t), count(CASE WHEN t.status = 'DONE' THEN 1 END)")
        total_tasks, done_tasks = res_tasks.result_set[0][0], res_tasks.result_set[0][1]
        assert total_tasks == done_tasks, f"All {total_tasks} tasks must be DONE"

        res_prs = graph.query("MATCH (pr:PR) RETURN count(pr), count(CASE WHEN pr.status = 'MERGED' THEN 1 END)")
        total_prs, merged_prs = res_prs.result_set[0][0], res_prs.result_set[0][1]
        assert total_prs == merged_prs, f"All {total_prs} PRs must be MERGED"


def test_automated_pytest_suite_passes(orchestrator_run_result):
    """
    Verification d): pytest returns 100% pass on all created test files.
    """
    ws = orchestrator_run_result["workspace_dir"]
    res = mcp_bash_test_runner("pytest tests/ -v", timeout_seconds=60, working_dir=ws)

    assert res["success"] is True, f"Pytest suite failed: {res['stdout']}\n{res['stderr']}"
    assert res["exit_code"] == 0
    assert res["summary"]["failed"] == 0
    assert res["summary"]["errors"] == 0
    assert res["summary"]["passed"] >= 8, f"Expected at least 8 passed unit tests, got {res['summary']['passed']}"


def test_telemetry_event_stream(orchestrator_run_result):
    """
    Verifies that the event stream emitted structured actions for all tiers.
    """
    events = orchestrator_run_result["events"]
    assert len(events) >= 15, f"Expected rich event stream, got {len(events)} events"

    actions = [e["action"] for e in events]
    assert "CEO_CHARTER_APPROVED" in actions
    assert "CTO_ARCHITECTURE_FROZEN" in actions
    assert "PM_DAG_DISPATCHED" in actions
    assert any("DEV_PR_OPENED" in a for a in actions)
    assert any("QA_PR_APPROVED" in a for a in actions)
    assert any("DEVOPS_MERGED_TASK_DONE" in a for a in actions)
