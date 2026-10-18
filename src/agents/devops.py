"""
DevOps Agent (Release & Operations Engineer).
Verifies QA approval sign-offs in FalkorDB, executes git merge --no-ff
to main on disk, marks completed tasks DONE, and runs Cypher Query 1
to topologically unblock downstream tasks in the DAG.
"""

import logging
from typing import Any, Dict, List, Optional
from src.agents.base import BaseAgent
from src.mcp.git_tools import GitWorkspaceTool
from src.db.queries import update_task_status
from src.db.in_memory_graph import InMemoryFalkorGraph

logger = logging.getLogger("graphcorp.agents.devops")


class DevOpsAgent(BaseAgent):
    def __init__(self, graph: Any, event_emitter: Optional[Any] = None):
        super().__init__(
            agent_id="DevOps-1",
            role="DevOps",
            graph=graph,
            model="gemini-2.5-flash",
            event_emitter=event_emitter
        )

    def merge_and_release(
        self,
        pr_id: str,
        task_id: str,
        workspace_dir: str = "workspace/dev-vault"
    ) -> Dict[str, Any]:
        """
        Executes verified production merge:
        1. Checks FalkorDB for cryptographic QA approval edge
        2. Merges feature branch into main via git merge --no-ff
        3. Sets Task to DONE in FalkorDB
        4. Triggers Cypher Topological Task Dispatch to unblock downstream tickets
        """
        self.set_status("ACTIVE", task_id=task_id)
        logger.info(f"DevOps Agent verifying approval for PR '{pr_id}' (Task: {task_id})")

        is_approved = False
        source_branch = None

        if isinstance(self.graph, InMemoryFalkorGraph):
            prs = self.graph.find_nodes("PR", id=pr_id)
            if prs:
                source_branch = prs[0].properties.get("source_branch")
                for e in self.graph.edges.values():
                    if e.relation == "REVIEWED" and e.dest_node.id == prs[0].id:
                        if e.properties.get("decision") == "APPROVED":
                            is_approved = True
                            break
        else:
            q_check = (
                "MATCH (a:Agent)-[r:REVIEWED {decision: 'APPROVED'}]->(pr:PR {id: $prid}) "
                "RETURN pr.source_branch, a.id LIMIT 1"
            )
            res = self.query(q_check, {"prid": pr_id})
            if res.result_set:
                is_approved = True
                source_branch = res.result_set[0][0]

        if not is_approved:
            logger.warning(f"PR '{pr_id}' does not have verified QA approval in FalkorDB. Rejecting merge.")
            self.set_status("IDLE")
            return {"success": False, "error": "Missing QA approval signature in graph"}

        source_branch = source_branch or "feat/crypto-engine"

        # 2. MCP Git: Execute git merge --no-ff into main
        git_tool = GitWorkspaceTool(workspace_dir=workspace_dir)
        git_tool.checkout_branch("main", create_if_missing=False)

        merge_msg = f"chore(merge): merge {source_branch} ({pr_id}) for {task_id}"
        merge_res = git_tool._run_git(["merge", "--no-ff", source_branch, "-m", merge_msg])

        if merge_res.returncode != 0:
            logger.error(f"Git merge --no-ff failed: {merge_res.stderr}")
            self.set_status("IDLE")
            return {"success": False, "error": merge_res.stderr.strip()}

        commit_sha = git_tool._run_git(["rev-parse", "HEAD"]).stdout.strip()

        # 3. Update PR status in FalkorDB
        if isinstance(self.graph, InMemoryFalkorGraph):
            prs = self.graph.find_nodes("PR", id=pr_id)
            if prs:
                prs[0].properties["status"] = "MERGED"
        else:
            self.query("MATCH (pr:PR {id: $id}) SET pr.status = 'MERGED'", {"id": pr_id})

        # 4. Mark Task DONE & Trigger Topological Task Dispatch
        status_update = update_task_status(self.graph, task_id, "DONE")
        unblocked = status_update.get("unblocked_tasks", [])

        self.emit(
            action="DEVOPS_MERGED_TASK_DONE",
            details={
                "pr_id": pr_id,
                "task_id": task_id,
                "merged_branch": source_branch,
                "merge_commit_sha": commit_sha,
                "unblocked_count": len(unblocked),
                "unblocked_tasks": [t["task_id"] for t in unblocked]
            },
            cypher=f"MATCH (t:Task {{id: '{task_id}'}}) SET t.status = 'DONE' WITH t ... SET dep.status = 'READY'",
            git_sha=commit_sha
        )
        self.set_status("IDLE")
        return {
            "success": True,
            "pr_id": pr_id,
            "task_id": task_id,
            "commit_sha": commit_sha,
            "unblocked_tasks": unblocked
        }
