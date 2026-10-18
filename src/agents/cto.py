"""
CTO Agent (Chief Technology Officer / Enterprise Architect).
Analyzes product charters, authors Architecture Decision Records (ADRs),
defines component boundaries, data contracts, and maps AST call graphs in FalkorDB.
"""

import time
import logging
from typing import Any, Dict, List, Optional
from src.agents.base import BaseAgent
from src.db.in_memory_graph import InMemoryFalkorGraph

logger = logging.getLogger("graphcorp.agents.cto")


class CTOAgent(BaseAgent):
    def __init__(self, graph: Any, event_emitter: Optional[Any] = None):
        super().__init__(
            agent_id="CTO",
            role="CTO",
            graph=graph,
            model="gemini-2.5-flash",
            event_emitter=event_emitter
        )

    def design_architecture(self, charter: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates product charter into concrete architecture specifications:
        ADRs, AST component definitions, security policies, and call graph topology.
        """
        self.set_status("ACTIVE")
        logger.info(f"CTO architecting system for project '{charter.get('name')}'")

        def fallback_architecture() -> Dict[str, Any]:
            return {
                "decision_record": {
                    "id": "ADR-001",
                    "title": "Cryptographic Engine Architecture for dev-vault",
                    "rationale": "Adopt AES-256 GCM authenticated encryption combined with Argon2id password-based key derivation function to resist GPU brute-force attacks and prevent ciphertext tampering.",
                    "chosen_option": "AES-256-GCM + Argon2id"
                },
                "components": [
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
                    }
                ],
                "call_graph": [
                    {"caller": "COMP-CLI", "callee": "COMP-STORAGE"},
                    {"caller": "COMP-CLI", "callee": "COMP-CRYPTO"},
                    {"caller": "COMP-STORAGE", "callee": "COMP-CRYPTO"}
                ],
                "policies": [
                    {
                        "id": "POL-SEC-01",
                        "name": "NIST-SP800-38D-AES-GCM",
                        "category": "SECURITY",
                        "rule_expression": "require AES-256-GCM + Argon2id",
                        "severity": "CRITICAL"
                    },
                    {
                        "id": "POL-QA-01",
                        "name": "ZERO-REGRESSION-SUITE",
                        "category": "SECURITY",
                        "rule_expression": "pytest pass rate == 100% with exit code 0",
                        "severity": "CRITICAL"
                    }
                ]
            }

        prompt = (
            f"You are the CTO / Enterprise Architect. Design the architecture for project: {charter}\n"
            f"Output JSON with keys: decision_record (id, title, rationale, chosen_option), "
            f"components (list of objects with id, name, file_path, language, exports, layer), "
            f"call_graph (list of caller-callee pairs), and policies (list of objects with id, name, category, rule_expression, severity)."
        )

        arch = self.generate(
            prompt=prompt,
            system_instruction="You are a principal software architect designing secure, modular Python systems.",
            expect_json=True,
            fallback_fn=fallback_architecture
        )

        # Validate structure
        if "components" not in arch or not arch["components"]:
            arch = fallback_architecture()

        now = int(time.time())

        # Register ADR and Policies in FalkorDB
        adr = arch["decision_record"]
        if isinstance(self.graph, InMemoryFalkorGraph):
            existing_adr = self.graph.find_nodes("DecisionRecord", id=adr["id"])
            if not existing_adr:
                self.graph.add_node(["DecisionRecord"], {
                    "id": adr["id"],
                    "title": adr["title"],
                    "rationale": adr["rationale"],
                    "chosen_option": adr["chosen_option"],
                    "timestamp": now
                })
        else:
            self.query(
                "MERGE (adr:DecisionRecord {id: $id}) "
                "ON CREATE SET adr.title = $title, adr.rationale = $rationale, adr.chosen_option = $opt, adr.timestamp = $ts",
                {"id": adr["id"], "title": adr["title"], "rationale": adr["rationale"], "opt": adr["chosen_option"], "ts": now}
            )

        # Register Components and Call Graph in FalkorDB
        comp_map = {}
        for c in arch["components"]:
            if isinstance(self.graph, InMemoryFalkorGraph):
                existing_c = self.graph.find_nodes("Component", id=c["id"])
                if existing_c:
                    comp_map[c["id"]] = existing_c[0]
                else:
                    comp_map[c["id"]] = self.graph.add_node(["Component"], c)
            else:
                self.query(
                    "MERGE (c:Component {id: $id}) "
                    "ON CREATE SET c.name = $name, c.file_path = $path, c.language = $lang, c.layer = $layer",
                    {"id": c["id"], "name": c["name"], "path": c["file_path"], "lang": c.get("language", "python"), "layer": c.get("layer", "CORE")}
                )

        for edge in arch.get("call_graph", []):
            caller_id = edge["caller"]
            callee_id = edge["callee"]
            if isinstance(self.graph, InMemoryFalkorGraph):
                if caller_id in comp_map and callee_id in comp_map:
                    self.graph.add_edge(comp_map[caller_id], "CALLS", comp_map[callee_id])
            else:
                self.query(
                    "MATCH (c1:Component {id: $c1}), (c2:Component {id: $c2}) MERGE (c1)-[:CALLS]->(c2)",
                    {"c1": caller_id, "c2": callee_id}
                )

        self.emit(
            action="CTO_ARCHITECTURE_FROZEN",
            details={
                "adr_id": adr["id"],
                "components": [c["name"] for c in arch["components"]],
                "call_graph_edges": len(arch.get("call_graph", []))
            },
            cypher="MERGE (adr:DecisionRecord) MERGE (c:Component)-[:CALLS]->(c)"
        )
        self.set_status("IDLE")
        return arch
