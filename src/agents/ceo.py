"""
CEO Agent (Chief Executive Officer).
Parses founder prompts, formalizes project charters, and registers
enterprise project boundaries and business logic constraints in FalkorDB.
"""

import time
import logging
from typing import Any, Dict, Optional
from src.agents.base import BaseAgent
from src.db.in_memory_graph import InMemoryFalkorGraph

logger = logging.getLogger("graphcorp.agents.ceo")


class CEOAgent(BaseAgent):
    def __init__(self, graph: Any, event_emitter: Optional[Any] = None):
        super().__init__(
            agent_id="CEO",
            role="CEO",
            graph=graph,
            model="gemini-2.5-flash",
            event_emitter=event_emitter
        )

    def authorize_project(self, founder_prompt: str) -> Dict[str, Any]:
        """
        Parses the founder prompt, formulates formal scope boundaries,
        and registers the (:Project) entity in FalkorDB.
        """
        self.set_status("ACTIVE")
        logger.info(f"CEO analyzing founder prompt: '{founder_prompt}'")

        def fallback_charter() -> Dict[str, Any]:
            return {
                "project_id": "PROJ-DEVVAULT",
                "name": "dev-vault",
                "repo_path": "workspace/dev-vault",
                "target_branch": "main",
                "charter_summary": "Enterprise developer secret store CLI in Python using AES-256 GCM authenticated encryption and Argon2id key derivation.",
                "security_constraints": [
                    "AES-256-GCM cipher with random 12-byte nonce per encryption",
                    "Argon2id key derivation (length=32, iterations=2, memory=19456KB)",
                    "Zero plaintext secrets stored on disk"
                ],
                "deliverables": [
                    "Core crypto engine (src/crypto.py)",
                    "Encrypted storage persistence (src/storage.py)",
                    "Click command-line interface (src/cli.py)",
                    "Automated pytest test suite (tests/)"
                ]
            }

        prompt = (
            f"You are the CEO of an autonomous AI software company. "
            f"Review this founder prompt: '{founder_prompt}'\n"
            f"Generate a formal JSON Product Charter with keys: project_id, name, repo_path, "
            f"target_branch, charter_summary, security_constraints (list of strings), and deliverables (list of strings)."
        )

        charter = self.generate(
            prompt=prompt,
            system_instruction="You are a strict, visionary enterprise software CEO defining clear product boundaries.",
            expect_json=True,
            fallback_fn=fallback_charter
        )

        # Ensure essential keys exist
        if not charter.get("project_id"):
            charter["project_id"] = "PROJ-DEVVAULT"
        if not charter.get("name"):
            charter["name"] = "dev-vault"
        if not charter.get("repo_path"):
            charter["repo_path"] = "workspace/dev-vault"
        if not charter.get("target_branch"):
            charter["target_branch"] = "main"

        # Register Project entity in FalkorDB
        now = int(time.time())
        if isinstance(self.graph, InMemoryFalkorGraph):
            existing = self.graph.find_nodes("Project", id=charter["project_id"])
            if not existing:
                self.graph.add_node(["Project"], {
                    "id": charter["project_id"],
                    "name": charter["name"],
                    "repo_path": charter["repo_path"],
                    "target_branch": charter["target_branch"],
                    "created_at": now
                })
        else:
            cypher = (
                "MERGE (p:Project {id: $id}) "
                "ON CREATE SET p.name = $name, p.repo_path = $repo, p.target_branch = $tgt, p.created_at = $now "
                "ON MATCH SET p.name = $name, p.repo_path = $repo"
            )
            self.query(cypher, {
                "id": charter["project_id"],
                "name": charter["name"],
                "repo": charter["repo_path"],
                "tgt": charter["target_branch"],
                "now": now
            })

        self.emit(
            action="CEO_CHARTER_APPROVED",
            details={"project_id": charter["project_id"], "name": charter["name"], "charter": charter},
            cypher=f"MERGE (p:Project {{id: '{charter['project_id']}'}})"
        )
        self.set_status("IDLE")
        return charter
