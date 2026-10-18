"""
FalkorDB Connection Client for GraphCorp Enterprise OS.
Provides unified, resilient access to FalkorDB Cloud, local Docker instances,
and seamless zero-dependency in-memory graph execution.
"""

import os
import logging
from typing import Optional, Dict, Any, Union
from dotenv import load_dotenv

# Load local environment variables if present
load_dotenv()

logger = logging.getLogger("graphcorp.db.client")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_active_graph_instance = None
_connection_metadata: Dict[str, Any] = {}


def get_connection_config() -> Dict[str, Any]:
    """Resolves FalkorDB connection parameters from environment."""
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    password = os.getenv("FALKORDB_PASSWORD", None)
    if password == "" or password == "None":
        password = None
    username = os.getenv("FALKORDB_USERNAME", None)
    graph_name = os.getenv("FALKORDB_GRAPH", "graphcorp")
    
    # Auto-detect SSL if using FalkorDB Cloud
    ssl_env = os.getenv("FALKORDB_SSL", "").lower()
    if ssl_env in ("1", "true", "yes"):
        ssl = True
    elif "falkordb.com" in host or port == 6380:
        ssl = True
    else:
        ssl = False

    return {
        "host": host,
        "port": port,
        "password": password,
        "username": username,
        "graph_name": graph_name,
        "ssl": ssl,
    }


def get_falkordb_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    username: Optional[str] = None,
    graph_name: Optional[str] = None,
    ssl: Optional[bool] = None,
    fallback_to_memory: bool = True,
    force_new: bool = False
) -> Any:
    """
    Connects to FalkorDB Cloud, local Docker, or high-performance in-memory fallback.
    Returns a Graph instance capable of executing Cypher queries.
    """
    global _active_graph_instance, _connection_metadata

    if _active_graph_instance is not None and not force_new:
        return _active_graph_instance

    cfg = get_connection_config()
    host = host or cfg["host"]
    port = port or cfg["port"]
    password = password if password is not None else cfg["password"]
    username = username if username is not None else cfg["username"]
    graph_name = graph_name or cfg["graph_name"]
    ssl = ssl if ssl is not None else cfg["ssl"]

    # 1. Attempt genuine connection to FalkorDB
    try:
        import falkordb
        client_kwargs = {
            "host": host,
            "port": port,
            "password": password,
            "ssl": ssl,
            "socket_connect_timeout": 1.5,
        }
        if username:
            client_kwargs["username"] = username

        db = falkordb.FalkorDB(**client_kwargs)
        graph = db.select_graph(graph_name)
        # Probe connection with a lightweight RO query
        graph.query("RETURN 1")

        is_cloud = "falkordb.com" in host
        conn_mode = "CONNECTED_TO_FALKORDB_CLOUD" if is_cloud else "CONNECTED_TO_LOCAL_DOCKER"
        logger.info(f"Successfully connected to FalkorDB [{conn_mode}] at {host}:{port} (graph: '{graph_name}')")

        _connection_metadata = {
            "mode": conn_mode,
            "is_live": True,
            "host": host,
            "port": port,
            "graph": graph_name,
            "ssl": ssl,
        }
        _active_graph_instance = graph
        return graph

    except Exception as e:
        if not fallback_to_memory:
            logger.error(f"Failed to connect to FalkorDB at {host}:{port}: {e}")
            raise e

        from src.db.in_memory_graph import InMemoryFalkorGraph
        logger.warning(
            f"FalkorDB server unreachable at {host}:{port} ({type(e).__name__}). "
            f"Falling back to high-performance In-Memory GraphCorp Engine (graph: '{graph_name}')."
        )
        graph = InMemoryFalkorGraph(graph_name=graph_name)
        _connection_metadata = {
            "mode": "IN_MEMORY_GRAPH_FALLBACK",
            "is_live": False,
            "host": host,
            "port": port,
            "graph": graph_name,
            "ssl": ssl,
            "reason": str(e),
        }
        _active_graph_instance = graph
        return graph


def get_connection_metadata() -> Dict[str, Any]:
    """Returns current active connection diagnostic details."""
    global _connection_metadata
    if not _connection_metadata:
        get_falkordb_client()
    return dict(_connection_metadata)


def reset_client() -> None:
    """Resets cached active connection instance."""
    global _active_graph_instance, _connection_metadata
    _active_graph_instance = None
    _connection_metadata = {}
