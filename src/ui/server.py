"""
FastAPI Real-Time Graph Visualizer Server for GraphCorp.
Provides:
1. 3-Pane Mission Control HTML Dashboard
2. Cytoscape.js Graph Representation API
3. Server-Sent Events (SSE) Live Telemetry Stream
4. Physical Git Log & Source Code Inspector
5. Async Project Execution Trigger
"""

import os
import json
import time
import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional, Set
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from src.db.client import get_falkordb_client
from src.db.schema import seed_initial_enterprise
from src.db.in_memory_graph import InMemoryFalkorGraph
from src.mcp.git_tools import GitWorkspaceTool
from src.mcp.fs_tools import mcp_filesystem_io

logger = logging.getLogger("graphcorp.ui.server")

# Global event bus and state
_event_subscribers: Set[asyncio.Queue] = set()
_recent_events: List[Dict[str, Any]] = []
_active_orchestrator = None
_is_running_lock = threading.Lock()
_is_running = False
_last_run_summary: Optional[Dict[str, Any]] = None


def broadcast_event(event: Dict[str, Any]) -> None:
    """Dispatches event to all connected web clients and stores in memory ring."""
    global _recent_events, _event_subscribers
    _recent_events.append(event)
    if len(_recent_events) > 200:
        _recent_events.pop(0)

    for q in list(_event_subscribers):
        try:
            q.put_nowait(event)
        except Exception:
            pass


def get_cytoscape_graph(graph: Any) -> Dict[str, Any]:
    """Formats FalkorDB entities into Cytoscape.js node/edge structures."""
    nodes = []
    edges = []
    counts = {"agents": 0, "tasks": 0, "prs": 0, "components": 0, "policies": 0}

    if isinstance(graph, InMemoryFalkorGraph):
        for node in graph.nodes.values():
            lbl = node.labels[0] if node.labels else "Entity"
            nid = str(node.id)
            p = node.properties
            title = p.get("name") or p.get("id") or p.get("title") or (f"commit:{p['sha'][:7]}" if p.get("sha") else None) or f"Node {nid}"
            status = node.properties.get("status", "IDLE")

            t_key = f"{lbl.lower()}s"
            if t_key in counts:
                counts[t_key] += 1

            nodes.append({
                "data": {
                    "id": f"node_{nid}",
                    "label": str(title),
                    "type": lbl.lower(),
                    "category": lbl,
                    "status": str(status),
                    "properties": node.properties
                }
            })

        for edge in graph.edges.values():
            edges.append({
                "data": {
                    "id": f"edge_{edge.id}",
                    "source": f"node_{edge.src_node.id}",
                    "target": f"node_{edge.dest_node.id}",
                    "label": edge.relation,
                    "type": edge.relation.lower(),
                    "properties": edge.properties
                }
            })
    else:
        # Live FalkorDB
        res_nodes = graph.query("MATCH (n) RETURN id(n), labels(n), properties(n)")
        for row in res_nodes.result_set:
            nid, lbls, props = row[0], row[1], row[2]
            lbl = lbls[0] if lbls else "Entity"
            title = props.get("name") or props.get("id") or props.get("title") or (f"commit:{props['sha'][:7]}" if props.get("sha") else None) or f"Node {nid}"
            status = props.get("status", "IDLE")

            t_key = f"{lbl.lower()}s"
            if t_key in counts:
                counts[t_key] += 1

            nodes.append({
                "data": {
                    "id": f"node_{nid}",
                    "label": str(title),
                    "type": lbl.lower(),
                    "category": lbl,
                    "status": str(status),
                    "properties": props
                }
            })

        res_edges = graph.query("MATCH (a)-[r]->(b) RETURN id(r), id(a), id(b), type(r), properties(r)")
        for row in res_edges.result_set:
            eid, src, dst, rtype, props = row[0], row[1], row[2], row[3], row[4]
            edges.append({
                "data": {
                    "id": f"edge_{eid}",
                    "source": f"node_{src}",
                    "target": f"node_{dst}",
                    "label": rtype,
                    "type": rtype.lower(),
                    "properties": props
                }
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "agents_count": counts["agents"],
            "tasks_count": counts["tasks"],
            "prs_count": counts["prs"],
            "components_count": counts["components"],
            "policies_count": counts["policies"]
        }
    }


class RunRequest(BaseModel):
    prompt: str = "Build dev-vault: an enterprise developer secret store CLI with AES-256 GCM"


def create_app(
    graph: Any = None,
    workspace_dir: str = "workspace/dev-vault"
) -> FastAPI:
    """Factory creating configured FastAPI Mission Control app."""
    app = FastAPI(title="GraphCorp Mission Control", version="1.0.0")
    active_graph = graph if graph is not None else get_falkordb_client()
    seed_initial_enterprise(active_graph, clean=False)

    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
    os.makedirs(static_dir, exist_ok=True)

    @app.get("/", response_class=HTMLResponse)
    def index():
        index_file = os.path.join(static_dir, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return f.read()
        return "<h1>GraphCorp Mission Control</h1><p>index.html not found.</p>"

    @app.get("/api/graph")
    def get_graph():
        """Returns Cytoscape-formatted JSON graph."""
        return get_cytoscape_graph(active_graph)

    @app.get("/api/events")
    async def sse_events(limit: int = 0):
        """Server-Sent Events (SSE) telemetry stream."""
        queue: asyncio.Queue = asyncio.Queue()
        _event_subscribers.add(queue)

        async def event_generator():
            emitted = 0
            try:
                # 1. Send past recent events for immediate context
                for ev in list(_recent_events):
                    yield f"event: message\ndata: {json.dumps(ev)}\n\n"
                    emitted += 1
                    if limit > 0 and emitted >= limit:
                        return

                # 2. Stream new live events
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)
                        yield f"event: message\ndata: {json.dumps(event)}\n\n"
                        emitted += 1
                        if limit > 0 and emitted >= limit:
                            return
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                _event_subscribers.discard(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    @app.post("/api/run")
    def trigger_run(req: RunRequest, background_tasks: BackgroundTasks):
        """Triggers autonomous multi-agent execution."""
        global _is_running, _last_run_summary

        with _is_running_lock:
            if _is_running:
                return JSONResponse({"status": "already_running", "message": "Execution already in progress"}, status_code=409)
            _is_running = True

        def execute():
            global _is_running, _last_run_summary
            from src.orchestration.engine import CompanyOrchestrator
            try:
                orch = CompanyOrchestrator(
                    graph=active_graph,
                    workspace_dir=workspace_dir,
                    event_callback=broadcast_event
                )
                summary = orch.run_project(req.prompt)
                _last_run_summary = summary
            except Exception as e:
                logger.error(f"Orchestration execution error: {e}")
                broadcast_event({"action": "EXECUTION_ERROR", "role": "SYSTEM", "error": str(e), "timestamp": time.time()})
            finally:
                with _is_running_lock:
                    _is_running = False

        background_tasks.add_task(execute)
        return {"status": "started", "prompt": req.prompt}

    @app.get("/api/repo/log")
    def get_repo_log():
        """Returns genuine git commit history from workspace/dev-vault."""
        git_tool = GitWorkspaceTool(workspace_dir=workspace_dir)
        commits = git_tool.get_log(max_count=25)
        raw_graph_res = git_tool._run_git(["log", "--graph", "--oneline", "-n", "20"])
        raw_graph = raw_graph_res.stdout if raw_graph_res.returncode == 0 else ""
        return {"commits": commits, "graph_log": raw_graph}

    @app.get("/api/repo/file")
    def get_repo_file(path: str = Query("src/crypto.py")):
        """Returns content of generated code files in workspace/dev-vault."""
        res = mcp_filesystem_io("read", file_path=path, working_dir=workspace_dir)
        return {
            "path": path,
            "exists": res.get("success", False),
            "content": res.get("content", ""),
            "line_count": res.get("line_count", 0),
            "bytes": res.get("bytes", 0)
        }

    @app.get("/api/status")
    def get_status():
        """Returns runtime execution state."""
        return {
            "is_running": _is_running,
            "last_summary": _last_run_summary,
            "events_count": len(_recent_events),
            "subscribers_count": len(_event_subscribers)
        }

    return app


app = None

def get_app():
    global app
    if app is None:
        app = create_app()
    return app
