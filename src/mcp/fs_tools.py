"""
Model Context Protocol (MCP) - FileSystem I/O Tool.
Provides atomic file creation, directory tree inspection, and safe file reads
for autonomous agents modifying the workspace codebase.
"""

import os
import shutil
import tempfile
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("graphcorp.mcp.fs")


class FileSystemTool:
    """
    Safe, atomic file system operations inside the workspace repository.
    Prevents race conditions and partial file writes via atomic file swapping.
    """
    def __init__(self, base_dir: str = "workspace/dev-vault"):
        self.base_dir = os.path.abspath(base_dir)

    def _resolve_safe_path(self, relative_path: str) -> str:
        """Resolves path and enforces boundary sandbox check."""
        target = os.path.abspath(os.path.join(self.base_dir, relative_path.lstrip("/")))
        if not target.startswith(self.base_dir):
            raise PermissionError(f"Path '{relative_path}' resolves outside sandbox base directory '{self.base_dir}'")
        return target

    def write_file(self, relative_path: str, content: str, atomic: bool = True) -> Dict[str, Any]:
        """
        Atomically writes file content.
        Uses temporary sibling file and os.replace to guarantee atomic disk writes.
        """
        target_path = self._resolve_safe_path(relative_path)
        parent_dir = os.path.dirname(target_path)
        os.makedirs(parent_dir, exist_ok=True)

        encoded_data = content.encode("utf-8")
        num_lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

        if atomic:
            # Write to sibling temp file first
            fd, tmp_path = tempfile.mkstemp(dir=parent_dir, prefix=".tmp_", suffix=".part")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(encoded_data)
                    f.flush()
                    os.fsync(f.fileno())
                # Atomic rename
                os.replace(tmp_path, target_path)
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                logger.error(f"Failed to write file atomically: {e}")
                return {"success": False, "error": str(e)}
        else:
            with open(target_path, "wb") as f:
                f.write(encoded_data)

        logger.debug(f"Wrote {len(encoded_data)} bytes ({num_lines} lines) to {relative_path}")
        return {
            "success": True,
            "path": relative_path,
            "absolute_path": target_path,
            "bytes_written": len(encoded_data),
            "lines": num_lines
        }

    def read_file(self, relative_path: str) -> Dict[str, Any]:
        """Reads file content safely with UTF-8 decoding."""
        target_path = self._resolve_safe_path(relative_path)
        if not os.path.exists(target_path):
            return {"success": False, "error": f"File does not exist: {relative_path}"}
        if os.path.isdir(target_path):
            return {"success": False, "error": f"Target is a directory, not a file: {relative_path}"}

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.splitlines()
            return {
                "success": True,
                "path": relative_path,
                "content": content,
                "bytes": len(content.encode("utf-8")),
                "line_count": len(lines)
            }
        except Exception as e:
            logger.error(f"Failed reading file {relative_path}: {e}")
            return {"success": False, "error": str(e)}

    def exists(self, relative_path: str) -> bool:
        """Checks if file or directory exists."""
        try:
            target_path = self._resolve_safe_path(relative_path)
            return os.path.exists(target_path)
        except Exception:
            return False

    def list_dir(self, relative_path: str = "", recursive: bool = True) -> Dict[str, Any]:
        """
        Lists directory contents recursively, excluding git metadata and cache artifacts.
        """
        target_path = self._resolve_safe_path(relative_path)
        if not os.path.exists(target_path):
            return {"success": False, "error": f"Directory not found: {relative_path}"}

        ignore_set = {".git", "__pycache__", ".pytest_cache", ".DS_Store", "venv", ".vault_data"}
        entries = []

        if recursive:
            for root, dirs, files in os.walk(target_path):
                # Filter in-place to avoid descending into ignored directories
                dirs[:] = [d for d in dirs if d not in ignore_set]
                for d in dirs:
                    full_p = os.path.join(root, d)
                    rel_p = os.path.relpath(full_p, self.base_dir)
                    entries.append({"path": rel_p, "type": "directory", "size": 0})
                for f in files:
                    if f in ignore_set:
                        continue
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, self.base_dir)
                    try:
                        sz = os.path.getsize(full_p)
                    except OSError:
                        sz = 0
                    entries.append({"path": rel_p, "type": "file", "size": sz})
        else:
            for item in os.listdir(target_path):
                if item in ignore_set:
                    continue
                full_p = os.path.join(target_path, item)
                rel_p = os.path.relpath(full_p, self.base_dir)
                is_dir = os.path.isdir(full_p)
                sz = 0 if is_dir else os.path.getsize(full_p)
                entries.append({"path": rel_p, "type": "directory" if is_dir else "file", "size": sz})

        return {
            "success": True,
            "base_dir": self.base_dir,
            "count": len(entries),
            "entries": entries
        }

    def delete_file(self, relative_path: str) -> Dict[str, Any]:
        """Safely removes a file or directory inside sandbox."""
        target_path = self._resolve_safe_path(relative_path)
        if not os.path.exists(target_path):
            return {"success": True, "message": "Already does not exist"}

        try:
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            return {"success": True, "path": relative_path}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Standard MCP Tool Handler conforming to PRD Section 5 & 6
def mcp_filesystem_io(
    action: str,
    file_path: Optional[str] = None,
    content: Optional[str] = None,
    working_dir: str = "workspace/dev-vault",
    recursive: bool = True
) -> Dict[str, Any]:
    """
    MCP tool interface: 'mcp_filesystem_io'
    Provides atomic file creation, file inspection, and directory tree listing.
    """
    tool = FileSystemTool(base_dir=working_dir)

    if action == "write":
        if not file_path:
            return {"success": False, "error": "file_path is required for write"}
        return tool.write_file(relative_path=file_path, content=content or "")
    elif action == "read":
        if not file_path:
            return {"success": False, "error": "file_path is required for read"}
        return tool.read_file(relative_path=file_path)
    elif action == "list":
        return tool.list_dir(relative_path=file_path or "", recursive=recursive)
    elif action == "exists":
        if not file_path:
            return {"success": False, "error": "file_path is required for exists"}
        return {"success": True, "exists": tool.exists(file_path)}
    elif action == "delete":
        if not file_path:
            return {"success": False, "error": "file_path is required for delete"}
        return tool.delete_file(relative_path=file_path)
    else:
        return {"success": False, "error": f"Unknown filesystem action: '{action}'"}
