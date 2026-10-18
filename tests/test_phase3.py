"""
Automated Verification Suite for Phase 3:
FastAPI Visualizer Server, Cytoscape.js Graph Model, and SSE Event Stream.
"""

import json
import pytest
from fastapi.testclient import TestClient
from src.ui.server import create_app, broadcast_event, _recent_events
from src.db.client import get_falkordb_client
from src.db.schema import seed_initial_enterprise


@pytest.fixture(scope="module")
def client():
    """Initializes a FastAPI test client with seeded FalkorDB graph."""
    graph = get_falkordb_client(force_new=True)
    seed_initial_enterprise(graph, clean=True)
    app = create_app(graph=graph)
    return TestClient(app)


def test_index_html_served(client):
    """
    Verification a): GET / returns 200 with Cytoscape.js script tags.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    text = resp.text.lower()
    assert "cytoscape" in text, "HTML must load Cytoscape.js library"
    assert "graphcorp" in text, "HTML must contain GraphCorp branding"
    assert "pane 1" in text or "falkordb graph canvas" in text
    assert "pane 2" in text or "reasoning" in text
    assert "pane 3" in text or "terminal" in text


def test_api_graph_structure(client):
    """
    Verification b): GET /api/graph returns valid JSON with nodes and edges.
    """
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()

    assert "nodes" in data, "Response must contain 'nodes' array"
    assert "edges" in data, "Response must contain 'edges' array"
    assert "stats" in data, "Response must contain 'stats' object"

    nodes = data["nodes"]
    edges = data["edges"]
    assert len(nodes) >= 15, f"Expected at least 15 graph nodes, got {len(nodes)}"
    assert len(edges) >= 10, f"Expected at least 10 graph edges, got {len(edges)}"

    # Validate Cytoscape node schema
    first_node = nodes[0]
    assert "data" in first_node
    assert "id" in first_node["data"]
    assert "label" in first_node["data"]
    assert "type" in first_node["data"]
    assert "status" in first_node["data"]

    # Validate Cytoscape edge schema
    first_edge = edges[0]
    assert "data" in first_edge
    assert "id" in first_edge["data"]
    assert "source" in first_edge["data"]
    assert "target" in first_edge["data"]
    assert "label" in first_edge["data"]


def test_api_repo_log_and_code_viewer(client):
    """
    Verification c): GET /api/repo/log returns genuine git commit history,
    and GET /api/repo/file returns physical source code.
    """
    # 1. Test Git Log
    resp_log = client.get("/api/repo/log")
    assert resp_log.status_code == 200
    log_data = resp_log.json()
    assert "commits" in log_data
    assert isinstance(log_data["commits"], list)
    assert len(log_data["commits"]) >= 1, "Must contain at least initial scaffold commit"
    first_commit = log_data["commits"][0]
    assert "sha" in first_commit
    assert len(first_commit["sha"]) == 40

    # 2. Test Code Viewer
    resp_file = client.get("/api/repo/file?path=pyproject.toml")
    assert resp_file.status_code == 200
    file_data = resp_file.json()
    assert file_data["path"] == "pyproject.toml"
    assert file_data["exists"] is True
    assert "dev-vault" in file_data["content"]


def test_event_broadcasting_and_queue(client):
    """
    Verification d): The event streaming queue handles dispatching and receiving events.
    """
    test_event = {
        "action": "TEST_VERIFICATION_EVENT",
        "agent_id": "QATester-1",
        "role": "QATester",
        "cypher_query": "MATCH (t:Task) RETURN count(t)",
        "details": {"test_metric": 42}
    }
    broadcast_event(test_event)

    # Verify event was captured in memory ring
    assert any(e.get("action") == "TEST_VERIFICATION_EVENT" for e in _recent_events)

    # Verify SSE endpoint connects and streams events with limit=2
    with client.stream("GET", "/api/events?limit=1") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        lines = []
        for line in response.iter_lines():
            if line:
                lines.append(line)
        assert any("data:" in l for l in lines)


def test_api_status_endpoint(client):
    """
    Tests /api/status endpoint returns valid runtime state.
    """
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_running" in data
    assert "events_count" in data
    assert isinstance(data["events_count"], int)
