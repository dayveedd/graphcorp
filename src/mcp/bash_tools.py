"""
Model Context Protocol (MCP) - Bash Test Runner Tool.
Executes automated pytest suites, linters, and python validation scripts
in isolated subprocesses with precise exit-code and stdout/stderr capture.
"""

import os
import re
import sys
import time
import subprocess
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("graphcorp.mcp.bash")


class BashRunnerTool:
    """
    Subprocess execution engine for running test suites and command-line tools.
    Automatically binds the active Python virtual environment for pytest and dependencies.
    """
    def __init__(self, default_cwd: str = "workspace/dev-vault"):
        self.default_cwd = os.path.abspath(default_cwd)

    def _get_execution_env(self, custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = os.environ.copy()
        # Ensure our venv's bin directory is at the front of PATH
        venv_bin = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "venv", "bin"))
        if os.path.isdir(venv_bin):
            env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
            env["VIRTUAL_ENV"] = os.path.abspath(os.path.join(venv_bin, ".."))

        # Add workspace to PYTHONPATH so imports like 'from src.crypto import ...' resolve
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{self.default_cwd}:{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = self.default_cwd

        if custom_env:
            env.update(custom_env)
        return env

    def run_command(
        self,
        command: str,
        timeout_seconds: int = 30,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Executes a bash shell command with timeout, capturing stdout, stderr, and exit code.
        """
        work_dir = os.path.abspath(cwd) if cwd else self.default_cwd
        os.makedirs(work_dir, exist_ok=True)

        exec_env = self._get_execution_env(env)
        start_time = time.perf_counter()

        logger.info(f"Executing bash command in {work_dir}: '{command}' (timeout: {timeout_seconds}s)")

        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
                env=exec_env
            )
            duration = time.perf_counter() - start_time
            parsed_summary = self._parse_pytest_output(res.stdout + "\n" + res.stderr)

            return {
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration_seconds": round(duration, 3),
                "timed_out": False,
                "summary": parsed_summary
            }

        except subprocess.TimeoutExpired as te:
            duration = time.perf_counter() - start_time
            stdout = te.stdout.decode() if isinstance(te.stdout, bytes) else (te.stdout or "")
            stderr = te.stderr.decode() if isinstance(te.stderr, bytes) else (te.stderr or "")
            logger.error(f"Command timed out after {timeout_seconds}s: '{command}'")
            return {
                "success": False,
                "exit_code": 124,
                "stdout": stdout,
                "stderr": f"Command timed out after {timeout_seconds} seconds: {stderr}",
                "duration_seconds": round(duration, 3),
                "timed_out": True,
                "summary": {}
            }
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(f"Command execution error: {e}")
            return {
                "success": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e),
                "duration_seconds": round(duration, 3),
                "timed_out": False,
                "summary": {}
            }

    def _parse_pytest_output(self, output: str) -> Dict[str, int]:
        """Parses standard pytest summary line if present."""
        summary = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        # Example: "==== 3 passed, 1 failed in 0.24s ===="
        passed_m = re.search(r"(\d+)\s+passed", output)
        failed_m = re.search(r"(\d+)\s+failed", output)
        errors_m = re.search(r"(\d+)\s+error", output)
        skipped_m = re.search(r"(\d+)\s+skipped", output)

        if passed_m:
            summary["passed"] = int(passed_m.group(1))
        if failed_m:
            summary["failed"] = int(failed_m.group(1))
        if errors_m:
            summary["errors"] = int(errors_m.group(1))
        if skipped_m:
            summary["skipped"] = int(skipped_m.group(1))

        return summary


# Standard MCP Tool Handler conforming to PRD Section 5 & 6
def mcp_bash_test_runner(
    command: str,
    timeout_seconds: int = 30,
    working_dir: str = "workspace/dev-vault"
) -> Dict[str, Any]:
    """
    MCP tool interface: 'mcp_bash_test_runner'
    Executes automated unit tests and linter suites in the project workspace.
    """
    runner = BashRunnerTool(default_cwd=working_dir)
    return runner.run_command(command=command, timeout_seconds=timeout_seconds)
