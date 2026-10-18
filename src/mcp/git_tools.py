"""
Model Context Protocol (MCP) - Git Operations Tool.
Executes genuine Git CLI commands on disk in the target workspace.
Zero mock data / zero smokes and mirrors.
"""

import os
import subprocess
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("graphcorp.mcp.git")


class GitWorkspaceTool:
    """
    Physical Git CLI controller executing inside workspace/dev-vault.
    Guarantees verifiable git commits, branch checkouts, diff reviews, and merges.
    """
    def __init__(self, workspace_dir: str = "workspace/dev-vault"):
        self.workspace_dir = os.path.abspath(workspace_dir)

    def _run_git(
        self,
        args: List[str],
        env_extra: Optional[Dict[str, str]] = None,
        check: bool = False
    ) -> subprocess.CompletedProcess:
        """Executes a git command in the workspace directory."""
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)

        # Default non-interactive git configuration
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["PAGER"] = "cat"

        cmd = ["git"] + args
        logger.debug(f"Running git in {self.workspace_dir}: {' '.join(cmd)}")
        res = subprocess.run(
            cmd,
            cwd=self.workspace_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        if check and res.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\nStderr: {res.stderr}\nStdout: {res.stdout}")
        return res

    def init_repo(self, initial_branch: str = "main", initial_commit: bool = True) -> Dict[str, Any]:
        """
        Initializes physical git repository at workspace/dev-vault,
        sets local identity, and optionally creates initial scaffolding commit.
        """
        os.makedirs(self.workspace_dir, exist_ok=True)

        # Run git init
        self._run_git(["init", "-b", initial_branch], check=False)
        # Fallback if older git doesn't support -b
        self._run_git(["checkout", "-b", initial_branch], check=False)

        # Configure local git author so commits never fail
        self._run_git(["config", "user.name", "GraphCorp Autonomous Agent"])
        self._run_git(["config", "user.email", "agent@graphcorp.ai"])

        # Create standard .gitignore
        gitignore_path = os.path.join(self.workspace_dir, ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w") as f:
                f.write("__pycache__/\n*.py[cod]\n.pytest_cache/\n.vault_data/\n*.egg-info/\n")

        # Create basic README if not present
        readme_path = os.path.join(self.workspace_dir, "README.md")
        if not os.path.exists(readme_path):
            with open(readme_path, "w") as f:
                f.write("# dev-vault\n\nEnterprise Encrypted Developer Secret Store CLI (AES-256 GCM + Argon2id)\n")

        commit_sha = None
        if initial_commit:
            self._run_git(["add", "-A"])
            res = self._run_git(["commit", "-m", "chore: initial repository scaffolding for dev-vault"])
            if res.returncode == 0:
                rev = self._run_git(["rev-parse", "HEAD"])
                commit_sha = rev.stdout.strip()
            else:
                # Might already be committed
                rev = self._run_git(["rev-parse", "HEAD"])
                if rev.returncode == 0:
                    commit_sha = rev.stdout.strip()

        logger.info(f"Initialized physical git repository at {self.workspace_dir} (branch: {initial_branch}, sha: {commit_sha})")
        return {
            "success": True,
            "workspace_dir": self.workspace_dir,
            "branch": initial_branch,
            "commit_sha": commit_sha,
        }

    def checkout_branch(self, branch_name: str, create_if_missing: bool = True) -> Dict[str, Any]:
        """Checks out branch; creates if missing."""
        # Check current branch
        curr = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
        if curr == branch_name:
            return {"success": True, "branch": branch_name, "message": f"Already on branch {branch_name}"}

        # Try normal checkout first
        res = self._run_git(["checkout", branch_name])
        if res.returncode == 0:
            return {"success": True, "branch": branch_name, "message": f"Switched to branch {branch_name}"}

        if create_if_missing:
            res_new = self._run_git(["checkout", "-b", branch_name])
            if res_new.returncode == 0:
                logger.info(f"Created and checked out new branch: {branch_name}")
                return {"success": True, "branch": branch_name, "message": f"Created and switched to branch {branch_name}"}
            return {"success": False, "error": res_new.stderr.strip()}

        return {"success": False, "error": res.stderr.strip()}

    def commit(
        self,
        commit_message: str,
        files: Optional[List[str]] = None,
        author_name: str = "GraphCorp Dev Agent",
        author_email: str = "dev@graphcorp.ai"
    ) -> Dict[str, Any]:
        """Stages files and creates physical git commit on disk."""
        if files:
            for f in files:
                self._run_git(["add", f])
        else:
            self._run_git(["add", "-A"])

        # Check if there are staged changes
        diff_check = self._run_git(["diff", "--cached", "--quiet"])
        if diff_check.returncode == 0:
            curr_sha = self._run_git(["rev-parse", "HEAD"]).stdout.strip()
            return {
                "success": True,
                "commit_sha": curr_sha,
                "message": "Nothing to commit, working tree clean",
                "diff_stat": "0 files changed"
            }

        author_env = {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        }

        res = self._run_git(["commit", "-m", commit_message], env_extra=author_env)
        if res.returncode != 0:
            return {"success": False, "error": res.stderr.strip()}

        sha = self._run_git(["rev-parse", "HEAD"]).stdout.strip()
        stat_res = self._run_git(["diff-tree", "--no-commit-id", "--stat", "-r", "HEAD"])
        diff_stat = stat_res.stdout.strip()

        logger.info(f"Created Git commit {sha[:8]}: '{commit_message}'")
        return {
            "success": True,
            "commit_sha": sha,
            "message": commit_message,
            "author": author_name,
            "diff_stat": diff_stat
        }

    def get_diff(self, base_branch: str = "main", target_branch: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches unified git diff.
        If target_branch is provided: git diff base_branch..target_branch
        Else: git diff base_branch
        """
        if target_branch:
            diff_arg = f"{base_branch}..{target_branch}"
        else:
            diff_arg = base_branch

        res = self._run_git(["diff", diff_arg])
        stat_res = self._run_git(["diff", "--stat", diff_arg])

        return {
            "success": True,
            "comparison": diff_arg,
            "diff": res.stdout,
            "diff_stat": stat_res.stdout.strip(),
            "has_changes": bool(res.stdout.strip())
        }

    def merge(
        self,
        source_branch: str,
        target_branch: str = "main",
        commit_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Merges source_branch into target_branch.
        Executes genuine git checkout + git merge.
        """
        co_res = self.checkout_branch(target_branch, create_if_missing=False)
        if not co_res["success"]:
            return co_res

        merge_args = ["merge", source_branch]
        if commit_message:
            merge_args.extend(["-m", commit_message])
        else:
            merge_args.append("--no-edit")

        res = self._run_git(merge_args)
        if res.returncode != 0:
            return {
                "success": False,
                "error": res.stderr.strip(),
                "stdout": res.stdout.strip()
            }

        sha = self._run_git(["rev-parse", "HEAD"]).stdout.strip()
        logger.info(f"Merged {source_branch} into {target_branch} (HEAD: {sha[:8]})")
        return {
            "success": True,
            "target_branch": target_branch,
            "source_branch": source_branch,
            "commit_sha": sha,
            "output": res.stdout.strip()
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns physical repository status."""
        branch_res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        status_res = self._run_git(["status", "--porcelain"])

        branch = branch_res.stdout.strip()
        status_lines = [line.strip() for line in status_res.stdout.splitlines() if line.strip()]

        return {
            "branch": branch,
            "is_clean": len(status_lines) == 0,
            "changes_count": len(status_lines),
            "changes": status_lines
        }

    def get_log(self, max_count: int = 10) -> List[Dict[str, str]]:
        """Returns commit history."""
        fmt = "%H|%an|%ae|%at|%s"
        res = self._run_git(["log", f"-n{max_count}", f"--format={fmt}"])
        commits = []
        for line in res.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "sha": parts[0],
                    "author_name": parts[1],
                    "author_email": parts[2],
                    "timestamp": parts[3],
                    "message": parts[4]
                })
        return commits


# Standard MCP Tool Handler conforming to PRD Section 5 & 6
def mcp_git_operations(
    action: str,
    branch_name: Optional[str] = None,
    commit_message: Optional[str] = None,
    files: Optional[List[str]] = None,
    workspace_dir: str = "workspace/dev-vault",
    base_branch: str = "main",
    source_branch: Optional[str] = None,
    target_branch: Optional[str] = "main",
) -> Dict[str, Any]:
    """
    MCP tool interface: 'mcp_git_operations'
    action: enum ["init", "checkout_branch", "commit", "get_diff", "merge", "status", "log"]
    """
    tool = GitWorkspaceTool(workspace_dir=workspace_dir)

    if action == "init":
        return tool.init_repo(initial_branch=branch_name or "main")
    elif action == "checkout_branch":
        if not branch_name:
            return {"success": False, "error": "branch_name is required for checkout_branch"}
        return tool.checkout_branch(branch_name)
    elif action == "commit":
        if not commit_message:
            return {"success": False, "error": "commit_message is required for commit"}
        return tool.commit(commit_message=commit_message, files=files)
    elif action == "get_diff":
        return tool.get_diff(base_branch=base_branch, target_branch=branch_name or source_branch)
    elif action == "merge":
        src = source_branch or branch_name
        if not src:
            return {"success": False, "error": "source_branch or branch_name required for merge"}
        return tool.merge(source_branch=src, target_branch=target_branch, commit_message=commit_message)
    elif action == "status":
        return tool.get_status()
    elif action == "log":
        return {"success": True, "commits": tool.get_log()}
    else:
        return {"success": False, "error": f"Unknown git action: '{action}'"}
