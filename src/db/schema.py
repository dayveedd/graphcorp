"""
FalkorDB Enterprise Schema & Seeding Engine for GraphCorp.
Defines the 9 core node ontologies and 10 directed relationship types
for autonomous multi-agent coordination.
"""

import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("graphcorp.db.schema")

CORE_NODE_LABELS = [
    "Agent",
    "Project",
    "Task",
    "Component",
    "Endpoint",
    "PR",
    "Commit",
    "Policy",
    "DecisionRecord",
]

CORE_RELATIONSHIPS = [
    "REPORTS_TO",
    "ASSIGNED_TO",
    "DEPENDS_ON",
    "IMPLEMENTS",
    "CALLS",
    "AUTHORED",
    "HAS_COMMIT",
    "REVIEWED",
    "ENFORCES",
    "AFFECTS",
    "GOVERNED_BY",
]


def create_indices(graph: Any) -> Dict[str, Any]:
    """
    Creates range and property indices for the 9 core node labels
    to ensure sub-millisecond Cypher traversals.
    """
    index_targets = [
        ("Agent", "id"),
        ("Agent", "role"),
        ("Project", "id"),
        ("Task", "id"),
        ("Task", "status"),
        ("Component", "id"),
        ("Component", "name"),
        ("Endpoint", "id"),
        ("Endpoint", "path"),
        ("PR", "id"),
        ("PR", "status"),
        ("Commit", "sha"),
        ("Policy", "id"),
        ("Policy", "name"),
        ("DecisionRecord", "id"),
    ]

    created = 0
    errors = []

    for label, prop in index_targets:
        try:
            if hasattr(graph, "create_node_range_index"):
                graph.create_node_range_index(label, prop)
                created += 1
            else:
                graph.query(f"CREATE INDEX ON :{label}({prop})")
                created += 1
        except Exception as e:
            # Index may already exist
            errors.append(f"{label}.{prop}: {e}")

    logger.info(f"Verified / created {created} graph indices across {len(CORE_NODE_LABELS)} node labels.")
    return {"indices_created": created, "errors": errors}


def seed_initial_enterprise(graph: Any, clean: bool = False) -> Dict[str, int]:
    """
    Seeds the complete GraphCorp enterprise knowledge graph:
    1. Executive, Planning & Engineering Org Chart
    2. Corporate Security and Quality Policies
    3. Architecture Decision Records (ADRs)
    4. Target Project (dev-vault)
    5. Component Call Graph (AST architecture)
    6. Task Dependency DAG
    """
    if clean:
        try:
            graph.delete()
        except Exception as e:
            logger.debug(f"Graph clean exception (ignoring): {e}")

    # Ensure indices are in place
    create_indices(graph)

    # Check if graph is an InMemoryFalkorGraph for optimized direct node/edge creation
    from src.db.in_memory_graph import InMemoryFalkorGraph
    is_in_memory = isinstance(graph, InMemoryFalkorGraph)

    now = int(time.time())

    # 1. ORG CHART AGENTS
    agents_data = [
        {"id": "CEO", "role": "CEO", "model": "gemini-2.5-pro", "status": "IDLE", "current_task_id": ""},
        {"id": "CTO", "role": "CTO", "model": "gemini-2.5-pro", "status": "IDLE", "current_task_id": ""},
        {"id": "PM", "role": "PM", "model": "gemini-2.5-flash", "status": "IDLE", "current_task_id": ""},
        {"id": "BackendDev-1", "role": "BackendDev", "model": "gemini-2.5-flash", "status": "IDLE", "current_task_id": ""},
        {"id": "CLIDev-2", "role": "CLIDev", "model": "gemini-2.5-flash", "status": "IDLE", "current_task_id": ""},
        {"id": "QATester-1", "role": "QATester", "model": "gemini-2.5-flash", "status": "IDLE", "current_task_id": ""},
        {"id": "DevOps-1", "role": "DevOps", "model": "gemini-2.5-flash", "status": "IDLE", "current_task_id": ""},
    ]

    agent_nodes = {}
    for a in agents_data:
        if is_in_memory:
            agent_nodes[a["id"]] = graph.add_node(["Agent"], a)
        else:
            graph.query(
                "CREATE (a:Agent {id: $id, role: $role, model: $model, status: $status, current_task_id: $current_task_id})",
                a
            )

    # Org Reporting Relationships
    reports = [
        ("CTO", "CEO"),
        ("PM", "CEO"),
        ("BackendDev-1", "CTO"),
        ("CLIDev-2", "CTO"),
        ("QATester-1", "CTO"),
        ("DevOps-1", "CTO"),
    ]
    for sub, mgr in reports:
        if is_in_memory:
            graph.add_edge(agent_nodes[sub], "REPORTS_TO", agent_nodes[mgr])
        else:
            graph.query(
                "MATCH (sub:Agent {id: $sub}), (mgr:Agent {id: $mgr}) CREATE (sub)-[:REPORTS_TO]->(mgr)",
                {"sub": sub, "mgr": mgr}
            )

    # 2. POLICIES
    policies_data = [
        {
            "id": "POL-SEC-01",
            "name": "NIST-SP800-38D-AES-GCM",
            "category": "SECURITY",
            "rule_expression": "require AES-256-GCM + Argon2id",
            "severity": "CRITICAL"
        },
        {
            "id": "POL-STYLE-01",
            "name": "PEP8-CLEAN-CODE",
            "category": "STYLE",
            "rule_expression": "flake8 / ruff compliance with 0 errors",
            "severity": "WARNING"
        },
        {
            "id": "POL-QA-01",
            "name": "ZERO-REGRESSION-SUITE",
            "category": "SECURITY",
            "rule_expression": "pytest pass rate == 100% with exit code 0",
            "severity": "CRITICAL"
        },
    ]
    policy_nodes = {}
    for p in policies_data:
        if is_in_memory:
            policy_nodes[p["id"]] = graph.add_node(["Policy"], p)
        else:
            graph.query(
                "CREATE (p:Policy {id: $id, name: $name, category: $category, rule_expression: $rule_expression, severity: $severity})",
                p
            )

    # 3. DECISION RECORD (ADR)
    adr_data = {
        "id": "ADR-001",
        "title": "Cryptographic Engine Architecture for dev-vault",
        "rationale": "Adopt AES-256 GCM authenticated encryption combined with Argon2id password-based key derivation function to resist GPU brute-force attacks and prevent ciphertext tampering.",
        "chosen_option": "AES-256-GCM + Argon2id",
        "timestamp": now
    }
    if is_in_memory:
        adr_node = graph.add_node(["DecisionRecord"], adr_data)
    else:
        graph.query(
            "CREATE (adr:DecisionRecord {id: $id, title: $title, rationale: $rationale, chosen_option: $chosen_option, timestamp: $timestamp})",
            adr_data
        )

    # 4. PROJECT (dev-vault)
    proj_data = {
        "id": "PROJ-DEVVAULT",
        "name": "dev-vault",
        "repo_path": "workspace/dev-vault",
        "target_branch": "main",
        "created_at": now
    }
    if is_in_memory:
        proj_node = graph.add_node(["Project"], proj_data)
    else:
        graph.query(
            "CREATE (p:Project {id: $id, name: $name, repo_path: $repo_path, target_branch: $target_branch, created_at: $created_at})",
            proj_data
        )

    # 5. CODE COMPONENTS & CALL GRAPH
    components_data = [
        {
            "id": "COMP-CRYPTO",
            "name": "crypto.py",
            "file_path": "src/crypto.py",
            "language": "python",
            "exports": ["VaultCipher", "derive_key", "encrypt_data", "decrypt_data"],
            "layer": "CORE"
        },
        {
            "id": "COMP-STORAGE",
            "name": "storage.py",
            "file_path": "src/storage.py",
            "language": "python",
            "exports": ["VaultStorage", "save_vault", "load_vault"],
            "layer": "IO"
        },
        {
            "id": "COMP-CLI",
            "name": "cli.py",
            "file_path": "src/cli.py",
            "language": "python",
            "exports": ["cli", "init_cmd", "set_cmd", "get_cmd", "list_cmd"],
            "layer": "CLI"
        },
    ]
    comp_nodes = {}
    for c in components_data:
        if is_in_memory:
            comp_nodes[c["id"]] = graph.add_node(["Component"], c)
        else:
            graph.query(
                "CREATE (c:Component {id: $id, name: $name, file_path: $file_path, language: $language, layer: $layer})",
                c
            )

    # Call graph edges:
    # CLI calls STORAGE, CLI calls CRYPTO, STORAGE calls CRYPTO
    call_edges = [
        ("COMP-CLI", "COMP-STORAGE"),
        ("COMP-CLI", "COMP-CRYPTO"),
        ("COMP-STORAGE", "COMP-CRYPTO"),
    ]
    for caller, callee in call_edges:
        if is_in_memory:
            graph.add_edge(comp_nodes[caller], "CALLS", comp_nodes[callee])
        else:
            graph.query(
                "MATCH (c1:Component {id: $c1}), (c2:Component {id: $c2}) CREATE (c1)-[:CALLS]->(c2)",
                {"c1": caller, "c2": callee}
            )

    # 6. TASK DAG FOR DEV-VAULT
    tasks_data = [
        {
            "id": "TASK-01",
            "title": "Repo Scaffolding & PyProject Configuration",
            "status": "READY",
            "branch": "feat/scaffold",
            "assigned_to": "DevOps-1",
            "implemented_by": "COMP-STORAGE",
            "depends_on": []
        },
        {
            "id": "TASK-02",
            "title": "Implement AES-256-GCM VaultCipher with Argon2id",
            "status": "BLOCKED",
            "branch": "feat/crypto-engine",
            "assigned_to": "BackendDev-1",
            "implemented_by": "COMP-CRYPTO",
            "depends_on": ["TASK-01"],
            "enforces": "POL-SEC-01",
            "governed_by": "ADR-001"
        },
        {
            "id": "TASK-03",
            "title": "Implement Encrypted File Storage Persistence",
            "status": "BLOCKED",
            "branch": "feat/storage-io",
            "assigned_to": "BackendDev-1",
            "implemented_by": "COMP-STORAGE",
            "depends_on": ["TASK-02"]
        },
        {
            "id": "TASK-04",
            "title": "Implement dev-vault Click CLI Commands",
            "status": "BLOCKED",
            "branch": "feat/cli-interface",
            "assigned_to": "CLIDev-2",
            "implemented_by": "COMP-CLI",
            "depends_on": ["TASK-03"]
        },
        {
            "id": "TASK-05",
            "title": "Automated Pytest Security and Unit Test Suite",
            "status": "BLOCKED",
            "branch": "feat/qa-suite",
            "assigned_to": "QATester-1",
            "implemented_by": "COMP-CRYPTO",
            "depends_on": ["TASK-04"],
            "enforces": "POL-QA-01"
        },
        {
            "id": "TASK-06",
            "title": "DevOps Fast-Forward Merge & Production Packaging",
            "status": "BLOCKED",
            "branch": "feat/release",
            "assigned_to": "DevOps-1",
            "implemented_by": "COMP-CLI",
            "depends_on": ["TASK-05"]
        },
    ]

    task_nodes = {}
    for t in tasks_data:
        props = {"id": t["id"], "title": t["title"], "status": t["status"], "branch": t["branch"]}
        if is_in_memory:
            task_nodes[t["id"]] = graph.add_node(["Task"], props)
        else:
            graph.query(
                "CREATE (t:Task {id: $id, title: $title, status: $status, branch: $branch})",
                props
            )

    # Link task relationships: DEPENDS_ON, ASSIGNED_TO, IMPLEMENTS, ENFORCES, GOVERNED_BY
    for t in tasks_data:
        t_id = t["id"]

        # ASSIGNED_TO
        agent_id = t["assigned_to"]
        if is_in_memory:
            graph.add_edge(agent_nodes[agent_id], "ASSIGNED_TO", task_nodes[t_id])
        else:
            graph.query(
                "MATCH (a:Agent {id: $aid}), (t:Task {id: $tid}) CREATE (a)-[:ASSIGNED_TO]->(t)",
                {"aid": agent_id, "tid": t_id}
            )

        # IMPLEMENTS (Component -> Task)
        comp_id = t["implemented_by"]
        if is_in_memory:
            graph.add_edge(comp_nodes[comp_id], "IMPLEMENTS", task_nodes[t_id])
        else:
            graph.query(
                "MATCH (c:Component {id: $cid}), (t:Task {id: $tid}) CREATE (c)-[:IMPLEMENTS]->(t)",
                {"cid": comp_id, "tid": t_id}
            )

        # DEPENDS_ON
        for dep_id in t["depends_on"]:
            if is_in_memory:
                graph.add_edge(task_nodes[t_id], "DEPENDS_ON", task_nodes[dep_id])
            else:
                graph.query(
                    "MATCH (t1:Task {id: $t1}), (t2:Task {id: $t2}) CREATE (t1)-[:DEPENDS_ON]->(t2)",
                    {"t1": t_id, "t2": dep_id}
                )

        # ENFORCES
        if "enforces" in t:
            pol_id = t["enforces"]
            if is_in_memory:
                graph.add_edge(task_nodes[t_id], "ENFORCES", policy_nodes[pol_id])
            else:
                graph.query(
                    "MATCH (t:Task {id: $tid}), (p:Policy {id: $pid}) CREATE (t)-[:ENFORCES]->(p)",
                    {"tid": t_id, "pid": pol_id}
                )

        # GOVERNED_BY
        if "governed_by" in t:
            g_adr = t["governed_by"]
            if is_in_memory:
                graph.add_edge(task_nodes[t_id], "GOVERNED_BY", adr_node)
            else:
                graph.query(
                    "MATCH (t:Task {id: $tid}), (adr:DecisionRecord {id: $aid}) CREATE (t)-[:GOVERNED_BY]->(adr)",
                    {"tid": t_id, "aid": g_adr}
                )

    counts = {
        "agents": len(agents_data),
        "policies": len(policies_data),
        "decision_records": 1,
        "components": len(components_data),
        "tasks": len(tasks_data),
    }
    logger.info(f"GraphCorp enterprise graph successfully seeded: {counts}")
    return counts
