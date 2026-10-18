"""
Base Agent Engine for GraphCorp Autonomous Workforce.
Provides core identity, FalkorDB graph state synchronization,
Gemini API integration with deterministic fallback generation,
and real-time event streaming.
"""

from __future__ import annotations
import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("graphcorp.agents.base")


class BaseAgent:
    """
    Abstract base class for all GraphCorp autonomous agents.
    Every agent maintains real-time synchronization with FalkorDB and
    communicates decisions through structured graph actions.
    """
    def __init__(
        self,
        agent_id: str,
        role: str,
        graph: Any,
        model: str = "gemini-2.5-flash",
        event_emitter: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.agent_id = agent_id
        self.role = role
        self.graph = graph
        self.model = model
        self.status = "IDLE"
        self.current_task_id: Optional[str] = None
        self.event_emitter = event_emitter
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.qwen_api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
        self.qwen_model = os.getenv("QWEN_MODEL", "qwen3.8-flash")
        self.qwen_base_url = os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions")
        self.api_key = self.gemini_api_key

    def set_status(self, new_status: str, task_id: Optional[str] = None) -> None:
        """Updates agent status both locally and inside FalkorDB."""
        self.status = new_status
        if task_id is not None:
            self.current_task_id = task_id

        cypher = "MATCH (a:Agent {id: $id}) SET a.status = $status, a.current_task_id = $task_id"
        params = {"id": self.agent_id, "status": self.status, "task_id": self.current_task_id or ""}
        try:
            self.graph.query(cypher, params)
        except Exception as e:
            logger.debug(f"Status sync to graph (ignored): {e}")

        self.emit(
            action=f"STATUS_CHANGE_{new_status}",
            details={"status": new_status, "current_task_id": self.current_task_id},
            cypher=cypher
        )

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a Cypher query on FalkorDB."""
        return self.graph.query(cypher, params or {})

    def emit(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        cypher: str = "",
        git_sha: str = "",
        pytest_log: str = ""
    ) -> Dict[str, Any]:
        """Constructs and emits a structured telemetry event."""
        event = {
            "timestamp": time.time(),
            "iso_time": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id,
            "role": self.role,
            "action": action,
            "status": self.status,
            "cypher_query": cypher.strip(),
            "git_sha": git_sha,
            "pytest_log": pytest_log,
            "details": details or {}
        }
        if self.event_emitter:
            try:
                self.event_emitter(event)
            except Exception as e:
                logger.error(f"Event emitter error: {e}")
        return event

    def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        expect_json: bool = True,
        fallback_fn: Optional[Callable[[], Any]] = None
    ) -> Any:
        """
        Executes generation via Qwen (DashScope) or Gemini REST API.
        Falls back seamlessly to deterministic domain logic if offline or rate-limited.
        """
        # 1. Prioritize Qwen Cloud (e.g. qwen3.8-flash) if key is provided
        if self.qwen_api_key:
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})

                body = {
                    "model": self.qwen_model,
                    "messages": messages,
                    "temperature": 0.2
                }
                if expect_json:
                    body["response_format"] = {"type": "json_object"}

                headers = {
                    "Authorization": f"Bearer {self.qwen_api_key}",
                    "Content-Type": "application/json"
                }
                resp = httpx.post(self.qwen_base_url, json=body, headers=headers, timeout=12.0)
                if resp.status_code == 200:
                    raw_text = resp.json()["choices"][0]["message"]["content"].strip()
                    if expect_json:
                        if raw_text.startswith("```"):
                            lines = raw_text.splitlines()
                            raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                        return json.loads(raw_text)
                    return raw_text
                else:
                    logger.warning(f"Qwen API returned status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"Qwen API request failed ({e}). Utilizing fallback.")

        # 2. Fallback to Gemini if configured
        if self.gemini_api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.gemini_api_key}"
                contents = []
                if system_instruction:
                    contents.append({"role": "user", "parts": [{"text": f"System Instructions:\n{system_instruction}\n\nTask:\n{prompt}"}]})
                else:
                    contents.append({"role": "user", "parts": [{"text": prompt}]})

                body = {
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.2,
                    }
                }
                if expect_json:
                    body["generationConfig"]["responseMimeType"] = "application/json"

                resp = httpx.post(url, json=body, timeout=4.0)
                if resp.status_code == 200:
                    raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if expect_json:
                        if raw_text.startswith("```"):
                            lines = raw_text.splitlines()
                            raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                        return json.loads(raw_text)
                    return raw_text
                else:
                    logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"Gemini API request failed ({e}). Utilizing deterministic domain reasoning.")

        if fallback_fn:
            return fallback_fn()
        return {} if expect_json else ""
