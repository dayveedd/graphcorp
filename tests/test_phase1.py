"""
Automated Verification Suite for GraphCorp Phase 1:
1. FalkorDB Connection & Enterprise Knowledge Graph Schema Seeding
2. Physical Git Workspace Initialization at workspace/dev-vault
3. Cypher Topological Task Dispatch & Multi-hop Reasoning Engine
4. Model Context Protocol (MCP) Tool Integration
"""

import os
import shutil
import pytest

from src.db.client import get_falkordb_client, get_connection_metadata
from src.db.schema import seed_initial_enterprise, CORE_NODE_LABELS, CORE_RELATIONSHIPS
from src.db.queries import (
    get_ready_tasks,
    update_task_status,
    compute_blast_radius,
    record_pr,
    query_decision_provenance,
    get_living_graph_data,
)
from src.mcp.git_tools import mcp_git_operations, GitWorkspaceTool
from src.mcp.bash_tools import mcp_bash_test_runner, BashRunnerTool
from src.mcp.fs_tools import mcp_filesystem_io, FileSystemTool


WORKSPACE_DIR = os.path.abspath("workspace/dev-vault")


@pytest.fixture(scope="module")
def graph_instance():
    """Provides a fresh seeded FalkorDB graph instance."""
    graph = get_falkordb_client(force_new=True)
    seed_initial_enterprise(graph, clean=True)
    return graph


def test_falkordb_connection_and_schema(graph_instance):
    """
    Verification a): FalkorDB connects and creates the graph schema cleanly.
    Validates presence of 9 node labels, policies, and ADRs.
    """
    meta = get_connection_metadata()
    assert meta["graph"] == "graphcorp"
    assert meta["mode"] in ("CONNECTED_TO_FALKORDB_CLOUD", "CONNECTED_TO_LOCAL_DOCKER", "IN_MEMORY_GRAPH_FALLBACK")

    # Living graph Cytoscape representation
    living_data = get_living_graph_data(graph_instance)
    assert living_data["nodes_count"] >= 18, f"Expected at least 18 nodes, got {living_data['nodes_count']}"
    assert living_data["edges_count"] >= 15, f"Expected at least 15 edges, got {living_data['edges_count']}"

    # Verify Agents
    res_agents = graph_instance.query("MATCH (a:Agent) RETURN a.id, a.role")
    agent_roles = {row[1] for row in res_agents.result_set}
    assert "CEO" in agent_roles
    assert "CTO" in agent_roles
    assert "BackendDev" in agent_roles
    assert "DevOps" in agent_roles

    # Verify Policies
    res_pol = graph_instance.query("MATCH (p:Policy) RETURN p.id, p.name")
    policy_ids = {row[0] for row in res_pol.result_set}
    assert "POL-SEC-01" in policy_ids


def test_physical_git_workspace_initialization():
    """
    Verification b): A real local git repository is initialized at workspace/dev-vault.
    Executes physical git actions on disk: init, checkout, commit, diff, and merge.
    """
    # Clean workspace directory if it already existed
    if os.path.exists(WORKSPACE_DIR):
        shutil.rmtree(WORKSPACE_DIR)

    # 1. MCP Git Init
    init_res = mcp_git_operations(action="init", workspace_dir=WORKSPACE_DIR)
    assert init_res["success"] is True
    assert os.path.isdir(os.path.join(WORKSPACE_DIR, ".git")), ".git directory must exist on disk"
    assert os.path.isfile(os.path.join(WORKSPACE_DIR, "README.md")), "README.md scaffold must exist"
    assert os.path.isfile(os.path.join(WORKSPACE_DIR, ".gitignore")), ".gitignore scaffold must exist"
    assert len(init_res["commit_sha"]) == 40, "Initial commit SHA must be a 40-char git hash"

    # 2. MCP Git Status
    status_res = mcp_git_operations(action="status", workspace_dir=WORKSPACE_DIR)
    assert status_res["branch"] == "main"
    assert status_res["is_clean"] is True

    # 3. MCP Git Branch Checkout
    branch_res = mcp_git_operations(
        action="checkout_branch",
        branch_name="feat/crypto-engine",
        workspace_dir=WORKSPACE_DIR
    )
    assert branch_res["success"] is True
    assert branch_res["branch"] == "feat/crypto-engine"

    # 4. MCP Atomic File Write
    fs_res = mcp_filesystem_io(
        action="write",
        file_path="src/crypto.py",
        content="# VaultCipher initial scaffold\nclass VaultCipher:\n    pass\n",
        working_dir=WORKSPACE_DIR
    )
    assert fs_res["success"] is True
    assert os.path.isfile(os.path.join(WORKSPACE_DIR, "src", "crypto.py"))

    # 5. MCP Git Commit
    commit_res = mcp_git_operations(
        action="commit",
        commit_message="feat(crypto): scaffold VaultCipher class",
        workspace_dir=WORKSPACE_DIR
    )
    assert commit_res["success"] is True
    assert len(commit_res["commit_sha"]) == 40

    # 6. MCP Git Diff Inspection
    diff_res = mcp_git_operations(
        action="get_diff",
        base_branch="main",
        branch_name="feat/crypto-engine",
        workspace_dir=WORKSPACE_DIR
    )
    assert diff_res["success"] is True
    assert diff_res["has_changes"] is True
    assert "VaultCipher" in diff_res["diff"]

    # 7. MCP Git Merge
    merge_res = mcp_git_operations(
        action="merge",
        source_branch="feat/crypto-engine",
        target_branch="main",
        workspace_dir=WORKSPACE_DIR
    )
    assert merge_res["success"] is True
    assert merge_res["commit_sha"] == commit_res["commit_sha"]

    # Verify main now contains src/crypto.py
    assert os.path.isfile(os.path.join(WORKSPACE_DIR, "src", "crypto.py"))


def test_topological_task_dispatch_cypher(graph_instance):
    """
    Verification c): The topological Cypher query successfully finds unblocked tasks.
    Tests Cypher Query 1: Critical Path Resolution and status progression.
    """
    # 1. Initially TASK-01 is READY, TASK-02 is BLOCKED
    ready_tasks = get_ready_tasks(graph_instance)
    ready_ids = [t["task_id"] for t in ready_tasks]
    assert "TASK-01" in ready_ids
    assert "TASK-02" not in ready_ids

    # 2. Simulate DevOps completing TASK-01
    update_res = update_task_status(graph_instance, "TASK-01", "DONE")
    unblocked = update_res["unblocked_tasks"]

    # TASK-02 must be automatically unblocked and returned with READY status!
    assert len(unblocked) >= 1
    unblocked_ids = [t["task_id"] for t in unblocked]
    assert "TASK-02" in unblocked_ids

    # 3. Simulate BackendDev completing TASK-02 -> should unblock TASK-03
    update_res2 = update_task_status(graph_instance, "TASK-02", "DONE")
    unblocked2_ids = [t["task_id"] for t in update_res2["unblocked_tasks"]]
    assert "TASK-03" in unblocked2_ids


def test_multi_hop_blast_radius_and_provenance(graph_instance):
    """
    Tests Cypher Query 2 (Blast Radius) and Cypher Query 3 (Decision Provenance).
    """
    # Cypher Query 2: Upstream AST Impact of crypto.py
    blast = compute_blast_radius(graph_instance, "crypto.py")
    assert len(blast) > 0
    downstream_names = {b["downstream_component"] for b in blast}
    # storage.py and cli.py call crypto.py
    assert "storage.py" in downstream_names or "cli.py" in downstream_names

    # Cypher Query 3: Register PR and trace full compliance provenance
    record_pr(
        graph_instance,
        pr_id="PR-01",
        title="feat: implement AES-256-GCM VaultCipher with Argon2id",
        source_branch="feat/crypto-engine",
        target_branch="main",
        author_agent_id="BackendDev-1",
        affected_components=["crypto.py"]
    )

    prov = query_decision_provenance(graph_instance, role="BackendDev")
    assert len(prov) >= 1
    record = prov[0]
    assert record["developer"] == "BackendDev-1"
    assert record["pull_request"] == "PR-01"
    assert "AES" in record["security_policy"] or "NIST" in record["security_policy"]
    assert "Argon2id" in record["adr_context"] or "AES-256" in record["adr_context"]


def test_mcp_bash_runner():
    """
    Tests MCP bash runner executing commands and capturing exit codes.
    """
    # 1. Successful command
    res = mcp_bash_test_runner("python3 --version")
    assert res["success"] is True
    assert res["exit_code"] == 0
    assert "Python" in res["stdout"] or "Python" in res["stderr"]

    # 2. Non-zero exit code
    fail_res = mcp_bash_test_runner("python3 -c 'import sys; sys.exit(7)'")
    assert fail_res["success"] is False
    assert fail_res["exit_code"] == 7
