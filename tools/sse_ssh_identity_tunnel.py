#!/usr/bin/env python3
"""Discover a moved SSH peer using an operator-pinned ED25519 host key.

Bounded private IPv4 lab fallback for an unavailable secure mesh. Does not
rewrite known_hosts, accept changed host keys or touch Ethereum secrets.
--run execs a foreground SSH tunnel for systemd to supervise.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import stat
import subprocess
import sys


class DiscoveryError(ValueError):
    pass


ALIAS = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,80}\Z")
USER = re.compile(r"[a-z_][a-z0-9_-]{0,31}\Z")


def private_file(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise DiscoveryError("expected existing absolute non-symlink file")
    st = p.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o077:
        raise DiscoveryError("file must be user-owned, private, and regular")
    return p


def read_pin(path: str, alias: str) -> str:
    if not ALIAS.fullmatch(alias):
        raise DiscoveryError("invalid stable host alias")
    lines = [line.split() for line in private_file(path).read_text("ascii").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if len(lines) != 1 or len(lines[0]) < 3 or lines[0][:2] != [alias, "ssh-ed25519"]:
        raise DiscoveryError("expected one pinned ED25519 known_hosts alias entry")
    key = lines[0][2]
    if not re.fullmatch(r"[A-Za-z0-9+/]{40,}={0,2}", key):
        raise DiscoveryError("invalid pinned SSH public key")
    return key


def allowed_network(cidr: str) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(cidr, strict=True)
    except ValueError as exc:
        raise DiscoveryError("invalid explicit CIDR") from exc
    if (not isinstance(network, ipaddress.IPv4Network) or not network.is_private
            or network.prefixlen < 24 or network.num_addresses > 256):
        raise DiscoveryError("only one explicit private IPv4 /24 or smaller is permitted")
    return network


def scan_host(ip: str, key: str, timeout: int) -> bool:
    try:
        result = subprocess.run(
            ["/usr/bin/ssh-keyscan", "-T", str(timeout), "-t", "ed25519", ip],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=timeout + 2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    # The scan is only a hint. The SSH handshake proves the pinned host key.
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == ip and fields[1] == "ssh-ed25519" and fields[2] == key:
            return True
    return False


def discover(cidr: str, key: str, *, timeout: int = 2, workers: int = 24,
             scan=scan_host) -> str:
    net = allowed_network(cidr)
    if not 1 <= timeout <= 5 or not 1 <= workers <= 32:
        raise DiscoveryError("discovery timeout/workers outside safe bounds")
    hosts = [str(ip) for ip in net.hosts()]
    matches = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {executor.submit(scan, ip, key, timeout): ip for ip in hosts}
        for task in as_completed(pending):
            if task.result():
                matches.append(pending[task])
    if len(matches) != 1:
        raise DiscoveryError(f"peer identity discovery ambiguous/unavailable; matches={len(matches)}")
    return matches[0]


def ssh_command(*, ip: str, user: str, identity: str, alias: str,
                known_hosts: str, local_port: int, target_port: int) -> list[str]:
    if not USER.fullmatch(user):
        raise DiscoveryError("invalid SSH Unix user")
    if not 1 <= local_port <= 65535 or not 1 <= target_port <= 65535:
        raise DiscoveryError("invalid port")
    read_pin(known_hosts, alias)
    private_file(identity)
    return ["/usr/bin/ssh", "-NT", "-i", identity,
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no",
            "-o", f"HostKeyAlias={alias}",
            "-o", f"UserKnownHostsFile={known_hosts}",
            "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=7",
            "-o", "ServerAliveInterval=20", "-o", "ServerAliveCountMax=3",
            "-o", "ForwardAgent=no",
            "-L", f"127.0.0.1:{local_port}:127.0.0.1:{target_port}",
            f"{user}@{ip}"]


def main() -> int:
    p = argparse.ArgumentParser(description="Pinned read-only discovery or supervised SSH loopback tunnel")
    p.add_argument("--cidr", required=True, help="explicit approved private /24 or narrower")
    p.add_argument("--alias", required=True, help="stable SSH host-key alias")
    p.add_argument("--known-hosts", required=True, help="private alias ssh-ed25519 key record")
    p.add_argument("--ssh-user", required=True)
    p.add_argument("--identity", required=True, help="VM-local SSH client key, not Ethereum")
    p.add_argument("--local-port", type=int, default=8545)
    p.add_argument("--target-port", type=int, default=8545)
    p.add_argument("--run", action="store_true", help="exec SSH forward (systemd supervised)")
    a = p.parse_args()
    try:
        key = read_pin(a.known_hosts, a.alias)
        cmd = ssh_command(ip="127.0.0.1", user=a.ssh_user, identity=a.identity,
                          alias=a.alias, known_hosts=a.known_hosts,
                          local_port=a.local_port, target_port=a.target_port)
        ip = discover(a.cidr, key)
        if not a.run:
            print(json.dumps({"result": "PINNED_SSH_PEER_FOUND_UNVERIFIED_HANDSHAKE",
                              "ip": ip, "hostKeyAlias": a.alias,
                              "network": a.cidr, "tunnelStarted": False}, sort_keys=True))
            return 0
        cmd[-1] = f"{a.ssh_user}@{ip}"
        # Only authenticated SSH may open the local forward; no TOFU.
        os.execv(cmd[0], cmd)
        return 0
    except (DiscoveryError, OSError, UnicodeError, ValueError) as exc:
        print("SSE_SSH_DISCOVERY_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
