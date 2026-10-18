"""
Company Orchestrator Engine for GraphCorp Enterprise OS.
Coordinates autonomous workforce lifecycle across Executive, Delivery, and Operating tiers.
Executes the full pipeline:
CEO -> CTO -> PM -> Dev -> QA -> DevOps
Emits live telemetry events for the Mission Control dashboard.
"""

import time
import logging
from typing import Any, Callable, Dict, List, Optional
from src.db.client import get_falkordb_client
from src.db.schema import seed_initial_enterprise
from src.db.queries import get_ready_tasks, get_living_graph_data
from src.mcp.git_tools import mcp_git_operations
from src.mcp.bash_tools import mcp_bash_test_runner
from src.agents.ceo import CEOAgent
from src.agents.cto import CTOAgent
from src.agents.pm import PMAgent
from src.agents.developer import DeveloperAgent
from src.agents.qa import QAAgent
from src.agents.devops import DevOpsAgent
from src.db.in_memory_graph import InMemoryFalkorGraph

logger = logging.getLogger("graphcorp.orchestration.engine")


class CompanyOrchestrator:
    """
    Central Nervous System Orchestrator.
    Drives autonomous multi-agent execution grounded in FalkorDB connected data.
    """
    def __init__(
        self,
        graph: Any = None,
        workspace_dir: str = "workspace/dev-vault",
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.workspace_dir = workspace_dir
        self.event_callback = event_callback
        self.events: List[Dict[str, Any]] = []

        # Initialize or connect to FalkorDB
        self.graph = graph if graph is not None else get_falkordb_client()
        seed_initial_enterprise(self.graph, clean=False)

        # Initialize physical git repository in workspace
        mcp_git_operations(action="init", workspace_dir=self.workspace_dir)

        # Initialize Agents
        self.ceo = CEOAgent(self.graph, event_emitter=self._record_event)
        self.cto = CTOAgent(self.graph, event_emitter=self._record_event)
        self.pm = PMAgent(self.graph, event_emitter=self._record_event)
        self.backend_dev = DeveloperAgent(
            agent_id="BackendDev-1",
            role="BackendDev",
            graph=self.graph,
            event_emitter=self._record_event
        )
        self.cli_dev = DeveloperAgent(
            agent_id="CLIDev-2",
            role="CLIDev",
            graph=self.graph,
            event_emitter=self._record_event
        )
        self.qa = QAAgent(self.graph, event_emitter=self._record_event)
        self.devops = DevOpsAgent(self.graph, event_emitter=self._record_event)

    def _record_event(self, event: Dict[str, Any]) -> None:
        """Appends event to internal ring and calls external streaming subscriber."""
        self.events.append(event)
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns recent telemetry events."""
        return self.events[-limit:]

    def run_project(self, founder_prompt: str, max_iterations: int = 20) -> Dict[str, Any]:
        """
        Executes end-to-end autonomous enterprise development loop:
        1. CEO authors Charter & Project constraints
        2. CTO establishes ADRs, Component AST boundaries, and Call Graph
        3. PM plans atomic Task DAG and initiates topological resolution
        4. Delivery Iteration Loop:
           - PM dispatches READY tasks
           - Dev checks out feat/ branch, writes atomic code & tests, commits, opens PR
           - QA fetches real git diff, runs pytest via MCP Bash runner, approves PR
           - DevOps executes fast-forward git merge to main, marks Task DONE, and unblocks next DAG tasks
        """
        start_time = time.time()
        logger.info(f"GraphCorp Orchestrator starting run with prompt: '{founder_prompt}'")

        # 1. Executive Tier: CEO
        charter = self.ceo.authorize_project(founder_prompt)

        # 2. Planning Tier: CTO
        arch = self.cto.design_architecture(charter)

        # 3. Planning Tier: PM
        tasks = self.pm.plan_task_dag(arch)

        # 4. Delivery Tier Execution Loop
        iteration = 0
        completed_tasks = []
        prs_merged = []

        while iteration < max_iterations:
            iteration += 1
            ready_tasks = get_ready_tasks(self.graph)

            if not ready_tasks:
                # Check if all tasks in graph are DONE
                all_done = self._check_all_tasks_done()
                if all_done:
                    logger.info("All tasks in enterprise DAG are marked DONE! Development cycle complete.")
                    break
                else:
                    logger.warning("No READY tasks discovered and pending tasks remain. Breaking to prevent deadlock.")
                    break

            for task in ready_tasks:
                task_id = task["task_id"]
                logger.info(f"--- Iteration {iteration}: Processing {task_id} ({task['title']}) ---")

                # Select developer based on component layer / assignment
                dev_agent = self.cli_dev if "CLI" in task.get("title", "") or task_id == "TASK-04" else self.backend_dev

                # Developer implements code, commits, and opens PR
                dev_res = dev_agent.implement_task(task, workspace_dir=self.workspace_dir)
                pr_id = dev_res["pr_id"]

                # QA audits git diff and executes pytest
                qa_res = self.qa.review_pr(pr_id, workspace_dir=self.workspace_dir)

                if qa_res["success"] and qa_res["decision"] == "APPROVED":
                    # DevOps merges to main and unblocks next DAG tasks
                    devops_res = self.devops.merge_and_release(pr_id, task_id, workspace_dir=self.workspace_dir)
                    if devops_res["success"]:
                        completed_tasks.append(task_id)
                        prs_merged.append(pr_id)
                else:
                    logger.error(f"QA review rejected PR {pr_id}: {qa_res}")

        # Final Verification: Run full pytest suite across workspace
        final_test_res = mcp_bash_test_runner("pytest tests/ -v", working_dir=self.workspace_dir)

        duration = round(time.time() - start_time, 2)
        living_graph = get_living_graph_data(self.graph)

        summary = {
            "success": len(completed_tasks) > 0 and final_test_res["success"],
            "project_name": charter.get("name", "dev-vault"),
            "duration_seconds": duration,
            "iterations": iteration,
            "tasks_completed": completed_tasks,
            "prs_merged": prs_merged,
            "final_test_exit_code": final_test_res["exit_code"],
            "final_test_passed": final_test_res["summary"].get("passed", 0),
            "events_emitted": len(self.events),
            "graph_nodes": living_graph["nodes_count"],
            "graph_edges": living_graph["edges_count"]
        }
        logger.info(f"Autonomous orchestration finished in {duration}s: {summary}")
        return summary

    def _check_all_tasks_done(self) -> bool:
        """Verifies if every Task in FalkorDB has status DONE."""
        if isinstance(self.graph, InMemoryFalkorGraph):
            tasks = self.graph.find_nodes("Task")
            if not tasks:
                return False
            return all(t.properties.get("status") == "DONE" for t in tasks)
        else:
            res = self.graph.query("MATCH (t:Task) RETURN t.status")
            if not res.result_set:
                return False
            return all(row[0] == "DONE" for row in res.result_set)
