#!/usr/bin/env python3
"""R92: repair ONLY already-created, known chain31340 EL/BN Docker networking.

Designed for Docker 29 failed-start/empty-networks post-reboot regression.
No container creation/deletion, no network creation, no wallets, no validators.
Role-specific original IP, network, aliases, and host port binding checks.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import os
import subprocess
import sys

ROLES = {
    "owner": {
        "ip": "fca0:2328:776e:4750:395b::1",
        "network": "sse31340-g2-internal",
        "internal": True,
        "containers": (
            ("sse31340-g2-el-r40", "172.18.0.2", "sse31340-g2-el"),
            ("sse31340-g2-bn", "172.18.0.3", None),
        ),
        "bindings": {
            "sse31340-g2-el-r40": {
                "8545/tcp": ("127.0.0.1", "18545"),
                "30404/tcp": ("fca0:2328:776e:4750:395b::1", "30404"),
                "30404/udp": ("fca0:2328:776e:4750:395b::1", "30404"),
            },
            "sse31340-g2-bn": {
                "5052/tcp": ("127.0.0.1", "15052"),
                "9000/tcp": ("fca0:2328:776e:4750:395b::1", "9000"),
                "9000/udp": ("fca0:2328:776e:4750:395b::1", "9000"),
                "9001/udp": ("fca0:2328:776e:4750:395b::1", "9001"),
            },
        },
    },
    "observer": {
        "ip": "fca0:2328:77b8:6578:a55::1",
        "network": "sse31340-r59-nonsigning-bridge",
        "internal": False,
        "containers": (
            ("sse31340-r59-nonsigning-el", "172.18.0.2", None),
            ("sse31340-r59-nonsigning-bn", "172.18.0.3", None),
        ),
        "bindings": {
            "sse31340-r59-nonsigning-el": {
                "8545/tcp": ("127.0.0.1", "28545"),
                "30404/tcp": ("fca0:2328:77b8:6578:a55::1", "30404"),
                "30404/udp": ("fca0:2328:77b8:6578:a55::1", "30404"),
            },
            "sse31340-r59-nonsigning-bn": {
                "5052/tcp": ("127.0.0.1", "25052"),
                "9000/tcp": ("fca0:2328:77b8:6578:a55::1", "9000"),
                "9000/udp": ("fca0:2328:77b8:6578:a55::1", "9000"),
                "9001/udp": ("fca0:2328:77b8:6578:a55::1", "9001"),
            },
        },
    },
}

class Refused(RuntimeError):
    pass

def run(argv: list[str], timeout: int = 20) -> str:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, check=False,
                           timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused("reviewed host operation unavailable") from exc
    if p.returncode:
        raise Refused("reviewed host operation failed: " + argv[0])
    return p.stdout.strip()

def docker(*args: str) -> str:
    return run(["docker", *args], timeout=80)

def inspect(name: str) -> dict:
    obj = json.loads(docker("inspect", "--format", "{{json .}}", name))
    if not isinstance(obj, dict):
        raise Refused("invalid Docker metadata")
    return obj

def verify_environment(role: str) -> dict:
    cfg = ROLES[role]
    ip = ipaddress.ip_address(cfg["ip"])
    assert ip.version == 6
    addr = run(["ip", "-6", "addr", "show", "dev", "ztrb6cq527"])
    if str(ip) + "/40" not in addr:
        raise Refused("actual expected ZeroTier IPv6 not ready")
    net = json.loads(docker("network", "inspect", cfg["network"], "--format", "{{json .}}"))
    if net.get("Driver") != "bridge" or net.get("Internal") is not cfg["internal"]:
        raise Refused("Docker network isolation differs")
    if role == "owner":
        vc = inspect("sse31340-g2-vc")
        if vc["State"].get("Running") is True:
            raise Refused("validator already running; refuse unrelated recovery")
    return cfg

def verify_container(name: str, cfg: dict) -> tuple[dict, bool]:
    obj = inspect(name)
    host = obj.get("HostConfig") or {}
    if host.get("NetworkMode") != cfg["network"]:
        raise Refused("Docker primary network changed")
    bindings = host.get("PortBindings") or {}
    expected = cfg["bindings"][name]
    if set(bindings) != set(expected):
        raise Refused("unexpected configured published port keys")
    for key, pair in expected.items():
        value = bindings.get(key)
        if not isinstance(value, list) or len(value) != 1 or (
            value[0].get("HostIp"), value[0].get("HostPort")
        ) != pair:
            raise Refused("unexpected Docker published host endpoint")
    return obj, bool(obj.get("State", {}).get("Running"))

def verify_attachment(obj: dict, cfg: dict, expected_ip: str, alias: str | None) -> bool:
    nets = obj.get("NetworkSettings", {}).get("Networks") or {}
    if set(nets).difference({cfg["network"]}):
        raise Refused("unexpected additional network on Ethereum client")
    record = nets.get(cfg["network"])
    if record is None:
        return False
    if record.get("IPAddress") != expected_ip:
        raise Refused("container internal IP changed")
    if alias and alias not in (record.get("Aliases") or []) and alias not in (record.get("DNSNames") or []):
        raise Refused("original execution DNS alias missing")
    return True

def published(obj: dict, expected: dict) -> bool:
    ports = obj.get("NetworkSettings", {}).get("Ports") or {}
    for port, (ip, hostport) in expected.items():
        bindings = ports.get(port)
        if not isinstance(bindings, list) or not any(
            isinstance(x, dict) and x.get("HostIp") == ip and x.get("HostPort") == hostport
            for x in bindings
        ):
            return False
    return True

def perform(role: str, apply: bool) -> int:
    cfg = verify_environment(role)
    planned = []
    for name, container_ip, alias in cfg["containers"]:
        obj, running = verify_container(name, cfg)
        attached = verify_attachment(obj, cfg, container_ip, alias)
        working_ports = published(obj, cfg["bindings"][name])
        planned.append((name, container_ip, alias, running, attached, working_ports))
    for name, _, _, running, attached, ports in planned:
        print(f"R92_ROLE={role} CLIENT={name} RUNNING={running} ATTACHED={attached} HOST_PORTS={ports}", flush=True)
    if not apply:
        return 0
    for name, container_ip, alias, running, attached, ports in planned:
        if not attached:
            argv = ["network", "connect", "--ip", container_ip]
            if alias:
                argv += ["--alias", alias]
            docker(*argv, cfg["network"], name)
            if running:
                docker("restart", "--time", "60", name)
            else:
                docker("start", name)
        elif not running:
            docker("start", name)
        # Owner's original internal bridge intentionally has no Docker host
        # publications. R92 host relay separately supplies those endpoints.
        obj = inspect(name)
        if not obj.get("State", {}).get("Running"):
            raise Refused("client not running after guarded recovery")
        if not verify_attachment(obj, cfg, container_ip, alias):
            raise Refused("client not attached after guarded recovery")
        if role == "observer" and not published(obj, cfg["bindings"][name]):
            raise Refused("observer host ports absent after guarded recovery")
    print("R92_GUARDED_EXISTING_CLIENT_RECOVERY_OK=true", flush=True)
    return 0

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=tuple(ROLES), required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if os.geteuid() != 0:
        print("R92_REQUIRES_ROOT_FOR_READONLY_DOCKER_INSPECTION", file=sys.stderr)
        return 2
    try:
        return perform(args.role, args.apply)
    except (Refused, KeyError, TypeError, ValueError, AssertionError) as exc:
        print("R92_GUARDED_RECOVERY_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
