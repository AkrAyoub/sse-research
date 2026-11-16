#!/usr/bin/env python3
"""R6 Ubuntu lab installer: pinned Git checkout + read-only SSE role-agent.

No wallet secrets, registration, transaction signing, Docker, port publishing,
validator setup or runtime auto-update. Default is a read-only JSON plan;
--apply is an explicit opt-in to local Ubuntu system changes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY = "https://github.com/AkrAyoub/sse-research.git"
COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}\Z")
ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}\Z")
NAME_RE = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
ALLOWED_ROLES = frozenset(("consumer", "provider", "monitor", "observer"))
SERVICE_NAME = "sse-vm-role-agent.service"
UNIT_DIR = Path("/etc/systemd/system")
VERSIONED_DEPENDENCIES = ("pycryptodome==3.23.0", "eth-account==0.14.0")


class BootstrapError(ValueError):
    pass


@dataclass(frozen=True)
class InstallSpec:
    revision: str
    node_id: str
    roles: tuple[str, ...]
    rpc_url: str
    chain_id: int
    settlement: str
    install_root: Path
    wallet: str | None = None
    broker_url: str | None = None
    enrollment_token_file: Path | None = None
    board_address: str | None = None
    committee_address: str | None = None

    @property
    def release(self) -> Path:
        return self.install_root / "releases" / self.revision

    @property
    def runtime(self) -> Path:
        return self.install_root / "runtime" / self.revision


def make_spec(*, revision: str, node_id: str, role_names: str, rpc_url: str,
              chain_id: int, settlement: str, install_root: Path,
              wallet: str | None = None, broker_url: str | None = None,
              enrollment_token_file: Path | None = None,
              board_address: str | None = None,
              committee_address: str | None = None) -> InstallSpec:
    if type(revision) is not str or not COMMIT_RE.fullmatch(revision):
        raise BootstrapError("requires externally approved full 40-character commit SHA")
    if type(node_id) is not str or not NAME_RE.fullmatch(node_id):
        raise BootstrapError("invalid node ID")
    if type(role_names) is not str:
        raise BootstrapError("invalid roles")
    role_tuple = tuple(x.strip() for x in role_names.split(","))
    if not role_tuple or len(set(role_tuple)) != len(role_tuple) or (
        any(x not in ALLOWED_ROLES for x in role_tuple)
    ):
        raise BootstrapError("roles must be unique consumer/provider/monitor/observer")
    if type(chain_id) is not int or not 1 <= chain_id < 2**256:
        raise BootstrapError("invalid chain ID")
    if type(settlement) is not str or not ADDR_RE.fullmatch(settlement) or int(settlement, 16) == 0:
        raise BootstrapError("invalid settlement contract address")
    if wallet is not None and (
        type(wallet) is not str or not ADDR_RE.fullmatch(wallet) or int(wallet, 16) == 0
    ):
        raise BootstrapError("invalid public wallet address")
    if type(rpc_url) is not str:
        raise BootstrapError("invalid RPC URL")
    u = urlsplit(rpc_url)
    try:
        port = u.port
    except ValueError as exc:
        raise BootstrapError("invalid RPC port") from exc
    if (u.scheme not in ("https", "http") or not u.hostname
        or u.username is not None or u.password is not None
        or u.query or u.fragment or u.path not in ("", "/")
        or (u.scheme == "http" and u.hostname not in ("localhost", "127.0.0.1", "::1"))
        or (port is not None and not 1 <= port <= 65535)):
        raise BootstrapError("RPC requires HTTPS or loopback HTTP, no URL credentials/path/query")
    root = Path(install_root)
    # Validate a POSIX install target even when this DRY_RUN is reviewed from
    # Windows/Git Bash. --apply independently requires Ubuntu.
    posix_root = root.as_posix()
    if (not posix_root.startswith("/") or posix_root == "/"
        or ".." in root.parts or len(root.parts) < 3
        or root.parts[1] not in ("opt", "srv")
        or not re.fullmatch(r"/(?:[a-zA-Z0-9._-]+/)*[a-zA-Z0-9._-]+", posix_root)):
        raise BootstrapError("install root must be safe absolute path below /opt or /srv")
    # Check each preexisting ancestor: a symlink may bypass the intended root.
    if os.name == "posix" and any(p.is_symlink() for p in (root, *root.parents)):
        raise BootstrapError("symlink install paths are forbidden")
    if bool(broker_url) != bool(enrollment_token_file):
        raise BootstrapError("mesh broker and token file must be configured together")
    if broker_url:
        host = urlsplit(broker_url)
        if (host.scheme != "https" or not host.hostname or
            host.username or host.password or host.path not in ("", "/") or
            host.query or host.fragment):
            raise BootstrapError("mesh broker must be an HTTPS origin")
        if Path(enrollment_token_file).as_posix() != "/run/sse/enrollment.token":
            raise BootstrapError("mesh enrollment token requires /run/sse/enrollment.token")
    if (board_address is None) != (committee_address is None):
        raise BootstrapError("node marketplace board and committee addresses are required together")
    if board_address is not None:
        for label, candidate in (("resource board", board_address),
                                 ("committee pool", committee_address)):
            if (type(candidate) is not str or not ADDR_RE.fullmatch(candidate)
                    or int(candidate, 16) == 0):
                raise BootstrapError("invalid " + label + " address")
    return InstallSpec(revision.lower(), node_id, role_tuple, rpc_url, chain_id,
                       settlement.lower(), root, None if wallet is None else wallet.lower(),
                       broker_url.rstrip("/") if broker_url else None,
                       Path(enrollment_token_file) if enrollment_token_file else None,
                       board_address.lower() if board_address else None,
                       committee_address.lower() if committee_address else None)


def describe(spec: InstallSpec) -> dict:
    return {
        "kind": "SSE_UBUNTU_FIRST_BOOT_PLAN",
        "mode": "DRY_RUN",
        "repository": REPOSITORY,
        "approvedCommit": spec.revision,
        "installRoot": spec.install_root.as_posix(),
        "nodeId": spec.node_id,
        "rolesConfigured": list(spec.roles),
        "chainId": spec.chain_id,
        "settlement": spec.settlement,
        "publicWallet": spec.wallet,
        "meshBrokerConfigured": spec.broker_url is not None,
        "meshBrokerOrigin": spec.broker_url,
        "marketplacePreviewConfigured": spec.board_address is not None,
        "actionsIfApplied": [
            "fetch immutable commit and verify checkout HEAD",
            "install isolated pinned cryptographic and Ethereum signing dependencies",
            "run read-only chain/contract/wallet preflight",
            "create locked-down sseagent user and read-only systemd role heartbeat",
        ],
        "walletKeysInstalled": False,
        "roleActivated": False,
        "monitorBondRegistered": False,
        "providerWorkloadStarted": False,
        "ethereumTransactionsSent": False,
    }


def systemd_unit(spec: InstallSpec) -> str:
    """Run the isolated node-local UI; no RPC credentials or keys in unit."""
    script = spec.release / "services" / "role-agent" / "agent.py"
    chain_env = ""
    if spec.board_address is not None:
        chain_env = (
            "Environment=SSE_CHAIN_ID=" + str(spec.chain_id) + "\n"
            "Environment=SSE_BOARD_ADDRESS=" + spec.board_address + "\n"
            "Environment=SSE_SETTLEMENT_ADDRESS=" + spec.settlement + "\n"
            "Environment=SSE_COMMITTEE_POOL_ADDRESS=" + spec.committee_address + "\n"
        )
    return (
        "[Unit]\nDescription=SSE experimental read-only VM role heartbeat\n"
        "After=network-online.target\nWants=network-online.target\n\n"
        "[Service]\nType=simple\nUser=sseagent\nGroup=sseagent\n"
        "WorkingDirectory=" + script.parent.as_posix() + "\n"
        "Environment=SSE_NODE_ID=" + spec.node_id + "\n"
        "Environment=SSE_ROLES=" + ",".join(spec.roles) + "\n"
        "Environment=SSE_REVISION=" + spec.revision + "\n"
        "Environment=SSE_AGENT_HOST=127.0.0.1\n"
        "Environment=SSE_AGENT_PORT=8765\n"
        "Environment=SSE_NODE_SETTINGS_FILE=/var/lib/sse-role-agent/preferences.json\n"
        + chain_env +
        "LoadCredential=ui-token:/etc/sse/node-ui.token\n"
        "StateDirectory=sse-role-agent\n"
        "ExecStart=" + (spec.runtime / "bin" / "python").as_posix() + " "
        + script.as_posix() + "\n"
        "Restart=on-failure\nRestartSec=4\n"
        "NoNewPrivileges=yes\nProtectSystem=strict\nProtectHome=yes\n"
        "PrivateTmp=yes\nCapabilityBoundingSet=\n\n"
        "[Install]\nWantedBy=multi-user.target\n"
    )


def _run(args: list[str], *, stdout: bool = False) -> str:
    try:
        done = subprocess.run(args, capture_output=True, text=True, check=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        # Avoid leaking tokens that might appear in subprocess diagnostics.
        raise BootstrapError("bootstrap command failed; review local installer logs") from exc
    return done.stdout if stdout else ""


def _head(path: Path) -> str:
    return _run(["git", "-C", str(path), "rev-parse", "--verify", "HEAD"], stdout=True).strip().lower()


def ensure_agent_user() -> None:
    """Create a locked-down service account only if absent; never alter existing users."""
    import pwd
    try:
        info = pwd.getpwnam("sseagent")
    except KeyError:
        _run(["useradd", "--system", "--no-create-home",
              "--shell", "/usr/sbin/nologin", "sseagent"])
        info = pwd.getpwnam("sseagent")
    if info.pw_uid == 0 or info.pw_shell not in ("/usr/sbin/nologin", "/bin/false"):
        raise BootstrapError("existing sseagent user is not sufficiently restricted")



def ensure_node_ui_token() -> None:
    """Provision private per-node UI auth without storing credentials in Git or unit text."""
    folder = Path("/etc/sse")
    if folder.is_symlink():
        raise BootstrapError("symlinked SSE credential directory forbidden")
    folder.mkdir(mode=0o700, exist_ok=True)
    st = folder.stat()
    if st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o700:
        raise BootstrapError("SSE credential directory must be root-owned mode 0700")
    path = folder / "node-ui.token"
    if path.is_symlink():
        raise BootstrapError("SSE credential path must not be symlink")
    if path.exists():
        st = path.stat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0
                or stat.S_IMODE(st.st_mode) != 0o600 or
                not 32 <= st.st_size <= 256):
            raise BootstrapError("unsafe existing SSE UI credential")
        return
    token = secrets.token_urlsafe(36) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(token)


def _assert_ubuntu() -> None:
    info = Path("/etc/os-release")
    if not info.is_file() or not any(x.strip() == "ID=ubuntu" for x in info.read_text().splitlines()):
        raise BootstrapError("this installer applies only to Ubuntu")
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise BootstrapError("--apply requires root; run the DRY_RUN without sudo")
    for cmd in ("git", "python3", "systemctl"):
        if not shutil.which(cmd):
            raise BootstrapError("missing command " + cmd + "; install OS dependencies first")


def apply(spec: InstallSpec) -> dict:
    """Explicit root-only installation; never overwrites an existing service."""
    _assert_ubuntu()
    import fcntl

    unit_path = UNIT_DIR / SERVICE_NAME
    if unit_path.exists() or unit_path.is_symlink():
        raise BootstrapError("service already installed; refuse implicit update/overwrite")

    spec.install_root.mkdir(mode=0o755, parents=True, exist_ok=True)
    lock = spec.install_root / ".bootstrap.lock"
    with lock.open("a+b") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        if unit_path.exists() or unit_path.is_symlink():
            raise BootstrapError("service installed concurrently; refusing overwrite")
        releases = spec.install_root / "releases"
        runtime = spec.install_root / "runtime"
        releases.mkdir(mode=0o755, exist_ok=True)
        runtime.mkdir(mode=0o755, exist_ok=True)
        if any(x.is_symlink() for x in (releases, runtime, spec.release, spec.runtime)):
            raise BootstrapError("symlink release/runtime paths are forbidden")

        if spec.release.exists():
            if not (spec.release / ".git").is_dir() or _head(spec.release) != spec.revision:
                raise BootstrapError("existing release has unexpected Git commit")
        else:
            stage = Path(tempfile.mkdtemp(prefix=".sse-stage-", dir=releases))
            try:
                source = stage / "source"
                _run(["git", "clone", "--quiet", "--no-checkout", REPOSITORY, str(source)])
                _run(["git", "-C", str(source), "fetch", "--quiet", "origin", spec.revision])
                _run(["git", "-C", str(source), "checkout", "--quiet", "--detach", spec.revision])
                if _head(source) != spec.revision:
                    raise BootstrapError("fetched checkout failed immutable revision check")
                source.rename(spec.release)
            finally:
                shutil.rmtree(stage)

        if not (spec.runtime / "bin" / "python").is_file():
            if spec.runtime.exists():
                raise BootstrapError("unexpected partial Python runtime; refuse repair")
            _run(["python3", "-m", "venv", str(spec.runtime)])
            _run([str(spec.runtime / "bin" / "python"), "-m", "pip", "install",
                  "--disable-pip-version-check", "--no-input", *VERSIONED_DEPENDENCIES])

        preflight = [
            str(spec.runtime / "bin" / "python"),
            str(spec.release / "tools" / "sse_vm_join_preflight.py"),
            "--checkout", str(spec.release),
            "--revision", spec.revision,
            "--roles", ",".join(spec.roles),
            "--rpc-url", spec.rpc_url,
            "--chain-id", str(spec.chain_id),
            "--settlement", spec.settlement,
        ]
        if spec.broker_url is not None:
            # Mesh is required before chain preflight when the RPC lives in the
            # private overlay. Abort on invalid/missing one-time credentials.
            _run(["python3", str(spec.release / "tools" / "sse_vm_enroll.py"),
                  "--node-id", spec.node_id, "--roles", ",".join(spec.roles),
                  "--broker-url", spec.broker_url,
                  "--token-file", str(spec.enrollment_token_file), "--apply"])

        if spec.wallet is not None:
            preflight.extend(["--wallet", spec.wallet])
        try:
            report = json.loads(_run(preflight, stdout=True))
        except (ValueError, json.JSONDecodeError) as exc:
            raise BootstrapError("VM preflight output invalid") from exc
        if (report.get("result") != "PASS" or report.get("revision") != spec.revision
            or report.get("roleActivated") is not False
            or report.get("writesOrTransactionsSent") is not False):
            raise BootstrapError("VM join preflight did not pass its read-only gate")

        ensure_agent_user()
        ensure_node_ui_token()
        unit = systemd_unit(spec)
        # The install command creates a root-owned mode-0644 unit, refusing
        # to replace any preexisting unit.
        staged = spec.install_root / ("." + SERVICE_NAME + ".new")
        with staged.open("x", encoding="utf-8") as output:
            output.write(unit)
        try:
            _run(["install", "-o", "root", "-g", "root", "-m", "0644", str(staged), str(unit_path)])
            _run(["systemctl", "daemon-reload"])
            _run(["systemctl", "enable", "--now", SERVICE_NAME])
        finally:
            staged.unlink(missing_ok=True)
        return {
            "result": "READ_ONLY_ROLE_AGENT_INSTALLED",
            "revision": spec.revision,
            "service": SERVICE_NAME,
            "nodeLocalUi": "http://127.0.0.1:8765/ui",
            "draftSettingsAvailable": True,
            "preflight": "PASS",
            "roleActivated": False,
            "ethereumTransactionsSent": False,
        }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SSE Ubuntu pinned Git bootstrap; dry-run by default")
    p.add_argument("--revision", required=True, help="approved full 40-character SHA, not HEAD")
    p.add_argument("--node-id", required=True)
    p.add_argument("--roles", required=True)
    p.add_argument("--rpc-url", required=True)
    p.add_argument("--chain-id", required=True, type=int)
    p.add_argument("--settlement", required=True)
    p.add_argument("--wallet", help="optional public wallet, NEVER private key")
    p.add_argument("--board", help="public OpenResourceBoard address for node-local previews")
    p.add_argument("--committee-pool", help="public OpenMonitorCommittee address for node-local previews")
    p.add_argument("--broker-url", help="optional HTTPS SSE mesh enrollment broker origin")
    p.add_argument("--enrollment-token-file", type=Path,
                   help="root-only one-time node token at /run/sse/enrollment.token")
    p.add_argument("--install-root", type=Path, default=Path("/opt/sse"))
    p.add_argument("--apply", action="store_true",
                   help="explicitly allow local Ubuntu Git/venv/systemd changes")
    args = p.parse_args(argv)
    try:
        spec = make_spec(revision=args.revision, node_id=args.node_id,
                         role_names=args.roles, rpc_url=args.rpc_url,
                         chain_id=args.chain_id, settlement=args.settlement,
                         install_root=args.install_root, wallet=args.wallet,
                         broker_url=args.broker_url,
                         enrollment_token_file=args.enrollment_token_file,
                         board_address=args.board,
                         committee_address=args.committee_pool)
        print(json.dumps(apply(spec) if args.apply else describe(spec),
                         sort_keys=True, indent=2))
        return 0
    except (BootstrapError, OSError, ValueError) as exc:
        print("SSE_BOOTSTRAP_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
