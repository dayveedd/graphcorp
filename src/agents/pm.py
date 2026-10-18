"""
PM Agent (Product Manager / Scrum Master).
Decomposes system architecture into atomic engineering task DAGs,
encodes dependency edges in FalkorDB, and computes the critical path via Cypher.
"""

import logging
from typing import Any, Dict, List, Optional
from src.agents.base import BaseAgent
from src.db.in_memory_graph import InMemoryFalkorGraph
from src.db.queries import dispatch_unblocked_tasks, get_ready_tasks

logger = logging.getLogger("graphcorp.agents.pm")


class PMAgent(BaseAgent):
    def __init__(self, graph: Any, event_emitter: Optional[Any] = None):
        super().__init__(
            agent_id="PM",
            role="PM",
            graph=graph,
            model="gemini-2.5-flash",
            event_emitter=event_emitter
        )

    def plan_task_dag(self, arch: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Translates architecture into an executable DAG of atomic engineering tasks.
        Enforces strict prerequisite ordering and policy associations in FalkorDB.
        """
        self.set_status("ACTIVE")
        logger.info("PM translating architecture into atomic Task Dependency DAG")

        def fallback_tasks() -> List[Dict[str, Any]]:
            return [
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
                }
            ]

        prompt = (
            f"You are the PM / Scrum Master. Given architecture: {arch}\n"
            f"Generate a list of atomic Task objects with keys: id, title, status (READY or BLOCKED), "
            f"branch, assigned_to (DevOps-1, BackendDev-1, CLIDev-2, QATester-1), "
            f"implemented_by (COMP-id), and depends_on (list of task ids)."
        )

        tasks_resp = self.generate(
            prompt=prompt,
            system_instruction="You are a strict technical PM building topologically ordered software engineering task DAGs.",
            expect_json=True,
            fallback_fn=fallback_tasks
        )

        tasks = tasks_resp if isinstance(tasks_resp, list) else tasks_resp.get("tasks", fallback_tasks())
        if not tasks:
            tasks = fallback_tasks()

        # Seed Tasks into FalkorDB
        is_in_memory = isinstance(self.graph, InMemoryFalkorGraph)
        task_nodes = {}
        for t in tasks:
            props = {"id": t["id"], "title": t["title"], "status": t["status"], "branch": t["branch"]}
            if is_in_memory:
                existing = self.graph.find_nodes("Task", id=t["id"])
                if existing:
                    task_nodes[t["id"]] = existing[0]
                    existing[0].properties.update(props)
                else:
                    task_nodes[t["id"]] = self.graph.add_node(["Task"], props)
            else:
                self.query(
                    "MERGE (t:Task {id: $id}) "
                    "ON CREATE SET t.title = $title, t.status = $status, t.branch = $branch "
                    "ON MATCH SET t.title = $title, t.status = $status, t.branch = $branch",
                    props
                )

        # Wire task relationships (DEPENDS_ON, ASSIGNED_TO, IMPLEMENTS, ENFORCES, GOVERNED_BY)
        for t in tasks:
            tid = t["id"]
            # DEPENDS_ON
            for dep in t.get("depends_on", []):
                if is_in_memory:
                    if tid in task_nodes and dep in task_nodes:
                        self.graph.add_edge(task_nodes[tid], "DEPENDS_ON", task_nodes[dep])
                else:
                    self.query(
                        "MATCH (t1:Task {id: $t1}), (t2:Task {id: $t2}) MERGE (t1)-[:DEPENDS_ON]->(t2)",
                        {"t1": tid, "t2": dep}
                    )

            # ASSIGNED_TO
            agent_id = t.get("assigned_to")
            if agent_id:
                if is_in_memory:
                    agents = self.graph.find_nodes("Agent", id=agent_id)
                    if agents and tid in task_nodes:
                        self.graph.add_edge(agents[0], "ASSIGNED_TO", task_nodes[tid])
                else:
                    self.query(
                        "MATCH (a:Agent {id: $aid}), (t:Task {id: $tid}) MERGE (a)-[:ASSIGNED_TO]->(t)",
                        {"aid": agent_id, "tid": tid}
                    )

            # IMPLEMENTS
            comp_id = t.get("implemented_by")
            if comp_id:
                if is_in_memory:
                    comps = self.graph.find_nodes("Component", id=comp_id)
                    if comps and tid in task_nodes:
                        self.graph.add_edge(comps[0], "IMPLEMENTS", task_nodes[tid])
                else:
                    self.query(
                        "MATCH (c:Component {id: $cid}), (t:Task {id: $tid}) MERGE (c)-[:IMPLEMENTS]->(t)",
                        {"cid": comp_id, "tid": tid}
                    )

            # ENFORCES
            pol_id = t.get("enforces")
            if pol_id:
                if is_in_memory:
                    pols = self.graph.find_nodes("Policy", id=pol_id)
                    if pols and tid in task_nodes:
                        self.graph.add_edge(task_nodes[tid], "ENFORCES", pols[0])
                else:
                    self.query(
                        "MATCH (t:Task {id: $tid}), (p:Policy {id: $pid}) MERGE (t)-[:ENFORCES]->(p)",
                        {"tid": tid, "pid": pol_id}
                    )

            # GOVERNED_BY
            adr_id = t.get("governed_by")
            if adr_id:
                if is_in_memory:
                    adrs = self.graph.find_nodes("DecisionRecord", id=adr_id)
                    if adrs and tid in task_nodes:
                        self.graph.add_edge(task_nodes[tid], "GOVERNED_BY", adrs[0])
                else:
                    self.query(
                        "MATCH (t:Task {id: $tid}), (adr:DecisionRecord {id: $aid}) MERGE (t)-[:GOVERNED_BY]->(adr)",
                        {"tid": tid, "aid": adr_id}
                    )

        # Execute initial topological dispatch
        ready_tasks = get_ready_tasks(self.graph)

        self.emit(
            action="PM_DAG_DISPATCHED",
            details={
                "total_tasks": len(tasks),
                "ready_count": len(ready_tasks),
                "ready_tasks": [t["task_id"] for t in ready_tasks]
            },
            cypher="MATCH (t:Task {status: 'BLOCKED'})-[:DEPENDS_ON]->(dep:Task) ..."
        )
        self.set_status("IDLE")
        return tasks
