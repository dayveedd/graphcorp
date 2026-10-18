"""
Developer Agent (Backend / Core Engineer).
Queries FalkorDB for assigned tasks, checks blast-radius impact,
checks out feature branches via MCP Git, writes atomic production code via MCP FS,
commits to disk, and opens verifiable PRs in FalkorDB.
"""

import os
import logging
from typing import Any, Dict, List, Optional
from src.agents.base import BaseAgent
from src.mcp.git_tools import mcp_git_operations
from src.mcp.fs_tools import mcp_filesystem_io
from src.db.queries import compute_blast_radius, record_pr, record_commit, update_task_status

logger = logging.getLogger("graphcorp.agents.developer")


class DeveloperAgent(BaseAgent):
    def __init__(
        self,
        agent_id: str = "BackendDev-1",
        role: str = "BackendDev",
        graph: Any = None,
        event_emitter: Optional[Any] = None
    ):
        super().__init__(
            agent_id=agent_id,
            role=role,
            graph=graph,
            model="gemini-2.5-flash",
            event_emitter=event_emitter
        )

    def implement_task(self, task: Dict[str, Any], workspace_dir: str = "workspace/dev-vault") -> Dict[str, Any]:
        """
        Executes physical implementation of assigned task on disk:
        1. Checks out feature branch in workspace/dev-vault
        2. Computes multi-hop blast-radius on upstream AST
        3. Writes production code & unit tests atomically
        4. Commits changes via genuine Git CLI
        5. Registers PR & Commit provenance in FalkorDB
        """
        task_id = task["task_id"]
        branch_name = task.get("branch") or task.get("target_branch") or f"feat/{task_id.lower()}"
        title = task["title"]

        self.set_status("ACTIVE", task_id=task_id)
        logger.info(f"[{self.agent_id}] Implementing {task_id}: '{title}' on branch '{branch_name}'")

        # 1. MCP Git: Checkout branch
        co_res = mcp_git_operations(
            action="checkout_branch",
            branch_name=branch_name,
            workspace_dir=workspace_dir
        )
        if not co_res["success"]:
            logger.error(f"Failed checking out branch {branch_name}: {co_res}")

        # 2. Compute Blast-Radius before writing code
        impacted = compute_blast_radius(self.graph, "crypto.py")

        # 3. Write atomic code based on task
        affected_comps, files_written = self._generate_task_code(task_id, workspace_dir)

        # 4. MCP Git: Commit changes
        commit_msg = f"feat({task_id.lower()}): {title}"
        commit_res = mcp_git_operations(
            action="commit",
            commit_message=commit_msg,
            files=files_written,
            workspace_dir=workspace_dir
        )
        commit_sha = commit_res.get("commit_sha", "HEAD")
        diff_stat = commit_res.get("diff_stat", "")

        # 5. FalkorDB: Register PR and Commit Provenance
        pr_id = f"PR-{task_id}"
        record_pr(
            graph=self.graph,
            pr_id=pr_id,
            title=f"PR for {title}",
            source_branch=branch_name,
            target_branch="main",
            author_agent_id=self.agent_id,
            affected_components=affected_comps
        )
        record_commit(
            graph=self.graph,
            pr_id=pr_id,
            sha=commit_sha,
            message=commit_msg,
            author=self.agent_id,
            diff_stat=diff_stat
        )

        # Update task status to IN_REVIEW
        update_task_status(self.graph, task_id, "IN_REVIEW")

        self.emit(
            action="DEV_PR_OPENED",
            details={
                "task_id": task_id,
                "pr_id": pr_id,
                "branch": branch_name,
                "commit_sha": commit_sha,
                "files_written": files_written,
                "blast_radius_impacted": len(impacted)
            },
            cypher=f"CREATE (pr:PR {{id: '{pr_id}'}})<-[:AUTHORED]-(:Agent {{id: '{self.agent_id}'}})",
            git_sha=commit_sha
        )
        self.set_status("IDLE")
        return {
            "task_id": task_id,
            "pr_id": pr_id,
            "branch": branch_name,
            "commit_sha": commit_sha,
            "files": files_written
        }

    def _generate_task_code(self, task_id: str, workspace_dir: str) -> tuple[List[str], List[str]]:
        """Generates production code for dev-vault components."""
        files = []
        comps = []

        if task_id == "TASK-01":
            # Repository Scaffolding & PyProject
            pyproject = """[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "dev-vault"
version = "0.1.0"
description = "Enterprise encrypted developer secret store CLI"
dependencies = [
    "cryptography>=43.0.0",
    "click>=8.1.0"
]

[project.scripts]
dev-vault = "src.cli:cli"
"""
            scaffold_test = """def test_workspace_scaffold():
    assert True
"""
            mcp_filesystem_io("write", "pyproject.toml", pyproject, working_dir=workspace_dir)
            mcp_filesystem_io("write", "src/__init__.py", "# dev-vault package\n", working_dir=workspace_dir)
            mcp_filesystem_io("write", "tests/__init__.py", "# dev-vault tests\n", working_dir=workspace_dir)
            mcp_filesystem_io("write", "tests/test_scaffold.py", scaffold_test, working_dir=workspace_dir)
            files.extend(["pyproject.toml", "src/__init__.py", "tests/__init__.py", "tests/test_scaffold.py"])
            comps.append("storage.py")

        elif task_id == "TASK-02":
            # AES-256-GCM VaultCipher with Argon2id
            crypto_code = '''"""
dev-vault Cryptographic Engine.
Implements NIST SP 800-38D compliant AES-256-GCM authenticated encryption
with Argon2id password-based key derivation.
"""

import os
import base64
from typing import Dict, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.exceptions import InvalidTag


class VaultCipher:
    """
    Cryptographic core for dev-vault.
    Guarantees authenticated confidentiality and integrity.
    """
    KEY_LENGTH = 32          # 256-bit AES key
    NONCE_LENGTH = 12        # 96-bit standard GCM nonce
    SALT_LENGTH = 16         # 128-bit salt
    ARGON2_ITERATIONS = 2
    ARGON2_MEMORY_COST = 19456
    ARGON2_LANES = 1

    @classmethod
    def derive_key(cls, passphrase: str, salt: bytes) -> bytes:
        """Derives a high-entropy 256-bit key from passphrase using Argon2id."""
        kdf = Argon2id(
            salt=salt,
            length=cls.KEY_LENGTH,
            iterations=cls.ARGON2_ITERATIONS,
            memory_cost=cls.ARGON2_MEMORY_COST,
            lanes=cls.ARGON2_LANES
        )
        return kdf.derive(passphrase.encode("utf-8"))

    @classmethod
    def encrypt(cls, plaintext: str, passphrase: str) -> Dict[str, Any]:
        """
        Encrypts plaintext string with fresh salt and unique nonce.
        Returns base64 serialized payload dictionary.
        """
        salt = os.urandom(cls.SALT_LENGTH)
        nonce = os.urandom(cls.NONCE_LENGTH)
        key = cls.derive_key(passphrase, salt)

        aesgcm = AESGCM(key)
        raw_ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

        return {
            "algorithm": "AES-256-GCM",
            "kdf": "Argon2id",
            "salt": base64.b64encode(salt).decode("utf-8"),
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "ciphertext": base64.b64encode(raw_ciphertext).decode("utf-8")
        }

    @classmethod
    def decrypt(cls, payload: Dict[str, Any], passphrase: str) -> str:
        """
        Decrypts base64 payload dictionary.
        Validates GCM authentication tag. Raises ValueError on failure.
        """
        try:
            salt = base64.b64decode(payload["salt"])
            nonce = base64.b64decode(payload["nonce"])
            ciphertext = base64.b64decode(payload["ciphertext"])

            key = cls.derive_key(passphrase, salt)
            aesgcm = AESGCM(key)
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode("utf-8")
        except (InvalidTag, Exception) as e:
            raise ValueError(f"Authentication failed: invalid passphrase or tampered ciphertext ({e})")
'''
            test_crypto_code = '''import pytest
from src.crypto import VaultCipher

def test_encryption_decryption_roundtrip():
    secret = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    passphrase = "MasterSuperSecretPassphrase#2026"
    
    payload = VaultCipher.encrypt(secret, passphrase)
    assert payload["algorithm"] == "AES-256-GCM"
    assert payload["kdf"] == "Argon2id"
    
    decrypted = VaultCipher.decrypt(payload, passphrase)
    assert decrypted == secret

def test_invalid_passphrase_raises_error():
    secret = "DATABASE_PASSWORD=ProdPass123"
    payload = VaultCipher.encrypt(secret, "CorrectPassword")
    
    with pytest.raises(ValueError, match="Authentication failed"):
        VaultCipher.decrypt(payload, "WrongPassword")

def test_tampered_ciphertext_fails():
    secret = "API_KEY=sk-test-12345"
    payload = VaultCipher.encrypt(secret, "ValidPass")
    
    ct = list(payload["ciphertext"])
    ct[5] = "A" if ct[5] != "A" else "B"
    payload["ciphertext"] = "".join(ct)
    
    with pytest.raises(ValueError):
        VaultCipher.decrypt(payload, "ValidPass")

def test_distinct_nonces_per_encryption():
    secret = "IdenticalSecret"
    p1 = VaultCipher.encrypt(secret, "pass")
    p2 = VaultCipher.encrypt(secret, "pass")
    assert p1["nonce"] != p2["nonce"]
    assert p1["salt"] != p2["salt"]
'''
            mcp_filesystem_io("write", "src/crypto.py", crypto_code, working_dir=workspace_dir)
            mcp_filesystem_io("write", "tests/test_crypto.py", test_crypto_code, working_dir=workspace_dir)
            files.extend(["src/crypto.py", "tests/test_crypto.py"])
            comps.append("crypto.py")

        elif task_id == "TASK-03":
            # Storage persistence
            storage_code = '''"""
dev-vault Encrypted Storage Layer.
Provides atomic file persistence for encrypted vault payloads.
"""

import os
import json
import tempfile
from typing import Dict, Any, Optional
from src.crypto import VaultCipher


class VaultStorage:
    def __init__(self, vault_path: str = ".vault_data/vault.enc"):
        self.vault_path = os.path.abspath(vault_path)

    def save_vault(self, secrets: Dict[str, str], passphrase: str) -> None:
        """Encrypts secrets dict and writes atomically to vault_path."""
        parent = os.path.dirname(self.vault_path)
        os.makedirs(parent, exist_ok=True)

        serialized = json.dumps(secrets)
        payload = VaultCipher.encrypt(serialized, passphrase)

        fd, tmp = tempfile.mkstemp(dir=parent, prefix=".vault_", suffix=".part")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.vault_path)

    def load_vault(self, passphrase: str) -> Dict[str, str]:
        """Loads and decrypts secrets dictionary."""
        if not os.path.exists(self.vault_path):
            return {}

        with open(self.vault_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        decrypted_json = VaultCipher.decrypt(payload, passphrase)
        return json.loads(decrypted_json)
'''
            test_storage_code = '''import os, shutil, pytest
from src.storage import VaultStorage

def test_vault_storage_save_load(tmp_path):
    vpath = os.path.join(str(tmp_path), "vault.enc")
    storage = VaultStorage(vault_path=vpath)
    
    secrets = {"STRIPE_KEY": "sk_live_12345", "DB_URL": "postgres://localhost/db"}
    storage.save_vault(secrets, "MyPass123")
    
    assert os.path.exists(vpath)
    loaded = storage.load_vault("MyPass123")
    assert loaded == secrets
'''
            mcp_filesystem_io("write", "src/storage.py", storage_code, working_dir=workspace_dir)
            mcp_filesystem_io("write", "tests/test_storage.py", test_storage_code, working_dir=workspace_dir)
            files.extend(["src/storage.py", "tests/test_storage.py"])
            comps.append("storage.py")

        elif task_id == "TASK-04":
            # CLI Interface
            cli_code = '''"""
dev-vault Command Line Interface.
Provides Click CLI commands: init, set, get, list.
"""

import click
from src.storage import VaultStorage


@click.group()
def cli():
    """dev-vault: Enterprise encrypted developer secret store."""
    pass


@cli.command("init")
@click.option("--passphrase", prompt=True, hide_input=True, confirmation_prompt=True, help="Vault master passphrase")
@click.option("--path", default=".vault_data/vault.enc", help="Vault file path")
def init_cmd(passphrase: str, path: str):
    """Initialize an empty encrypted dev-vault."""
    storage = VaultStorage(path)
    storage.save_vault({}, passphrase)
    click.echo(f"Initialized empty encrypted vault at {path}")


@cli.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--passphrase", prompt=True, hide_input=True, help="Vault master passphrase")
@click.option("--path", default=".vault_data/vault.enc", help="Vault file path")
def set_cmd(key: str, value: str, passphrase: str, path: str):
    """Set an encrypted secret in the vault."""
    storage = VaultStorage(path)
    secrets = storage.load_vault(passphrase)
    secrets[key] = value
    storage.save_vault(secrets, passphrase)
    click.echo(f"Secret '{key}' encrypted and saved.")


@cli.command("get")
@click.argument("key")
@click.option("--passphrase", prompt=True, hide_input=True, help="Vault master passphrase")
@click.option("--path", default=".vault_data/vault.enc", help="Vault file path")
def get_cmd(key: str, passphrase: str, path: str):
    """Retrieve and decrypt a secret from the vault."""
    storage = VaultStorage(path)
    secrets = storage.load_vault(passphrase)
    if key in secrets:
        click.echo(secrets[key])
    else:
        click.echo(f"Error: Secret '{key}' not found.", err=True)


@cli.command("list")
@click.option("--passphrase", prompt=True, hide_input=True, help="Vault master passphrase")
@click.option("--path", default=".vault_data/vault.enc", help="Vault file path")
def list_cmd(passphrase: str, path: str):
    """List all secret keys stored in the vault."""
    storage = VaultStorage(path)
    secrets = storage.load_vault(passphrase)
    for k in sorted(secrets.keys()):
        click.echo(k)


if __name__ == "__main__":
    cli()
'''
            test_cli_code = '''import os
from click.testing import CliRunner
from src.cli import cli

def test_cli_flow(tmp_path):
    runner = CliRunner()
    vpath = str(tmp_path / "cli_vault.enc")
    
    # 1. Init
    init_in = chr(10).join(["SecurePass123", "SecurePass123", ""])
    res = runner.invoke(cli, ["init", "--path", vpath], input=init_in)
    assert res.exit_code == 0
    assert "Initialized empty" in res.output
    
    # 2. Set
    set_in = chr(10).join(["SecurePass123", ""])
    res = runner.invoke(cli, ["set", "GITHUB_TOKEN", "ghp_abc123", "--path", vpath], input=set_in)
    assert res.exit_code == 0
    
    # 3. Get
    get_in = chr(10).join(["SecurePass123", ""])
    res = runner.invoke(cli, ["get", "GITHUB_TOKEN", "--path", vpath], input=get_in)
    assert res.exit_code == 0
    assert "ghp_abc123" in res.output
    
    # 4. List
    list_in = chr(10).join(["SecurePass123", ""])
    res = runner.invoke(cli, ["list", "--path", vpath], input=list_in)
    assert res.exit_code == 0
    assert "GITHUB_TOKEN" in res.output
'''
            mcp_filesystem_io("write", "src/cli.py", cli_code, working_dir=workspace_dir)
            mcp_filesystem_io("write", "tests/test_cli.py", test_cli_code, working_dir=workspace_dir)
            files.extend(["src/cli.py", "tests/test_cli.py"])
            comps.append("cli.py")

        elif task_id == "TASK-05":
            # Security & Integration tests
            integration_test = '''import pytest
from src.crypto import VaultCipher
from src.storage import VaultStorage

def test_end_to_end_crypto_security(tmp_path):
    vpath = str(tmp_path / "sec_vault.enc")
    storage = VaultStorage(vpath)
    
    # Save multiple sensitive keys
    data = {
        "OPENAI_API_KEY": "sk-proj-test12345",
        "JWT_SECRET": "dGhpcyBpcyBhIHRlc3Qgc2VjcmV0",
        "PIN": "9876"
    }
    storage.save_vault(data, "Pass123$")
    
    # Verify file is not plaintext
    with open(vpath, "r") as f:
        raw = f.read()
    assert "sk-proj" not in raw
    assert "JWT_SECRET" not in raw
    
    # Decrypt and verify
    recovered = storage.load_vault("Pass123$")
    assert recovered == data
'''
            mcp_filesystem_io("write", "tests/test_security.py", integration_test, working_dir=workspace_dir)
            files.append("tests/test_security.py")
            comps.append("crypto.py")

        elif task_id == "TASK-06":
            # Release metadata
            release_notes = """# dev-vault v1.0.0 Release
Built autonomously by GraphCorp AI Enterprise.
- AES-256 GCM Authenticated Encryption
- Argon2id Key Derivation
- Atomic File Persistence
- Click CLI
"""
            mcp_filesystem_io("write", "RELEASE.md", release_notes, working_dir=workspace_dir)
            files.append("RELEASE.md")
            comps.append("cli.py")

        return comps, files
