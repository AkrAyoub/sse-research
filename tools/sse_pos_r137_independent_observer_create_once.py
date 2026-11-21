#!/usr/bin/env python3
"""R137: create-once genuine non-signing chain31340 EL+CL on a NEW operator host.

Plan inspects only. Apply requires an interactive local authorization.
Never run on VM4706 or VM4707, never operate an existing signer, and
never claim independent peer connectivity without separate live evidence.
This installer intentionally reuses R59's exact proven chain archive/image
pins and its host security guards; new resources have separate names.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

import sse_pos_r59_native_ipv6_observer as r59
import sse_pos_r136_independent_observer_preflight as r136

class Refused(ValueError):
    pass

def names(node_id: str):
    # IDs are first validated by R136, and Docker names stay < 128 bytes.
    suffix = node_id  # R136 validates <=63 characters; do not truncate identities.
    return {"network": "sse31340-r137-" + suffix,
            "el": "sse31340-r137-" + suffix + "-el",
            "bn": "sse31340-r137-" + suffix + "-bn"}

def data_root(node_id: str):
    return Path.home() / ".local" / "share" / ("sse-r137-" + node_id)

def require_absent(root, resources):
    if root.exists() or root.is_symlink():
        raise Refused("this operator state already exists; do not overwrite or retry apply")
    for kind, name in (("network", resources["network"]),
                       ("container", resources["el"]),
                       ("container", resources["bn"])):
        if r59.resource_exists(kind, name):
            raise Refused("pre-existing Docker resource; do not overwrite")

def validate_seeds(el_enode, bn_enr):
    # Require actual peer-record *syntax* and an explicitly supplied bootstrap.
    # Signatures, remote identity and reachability are NOT checked here.
    if not r59.bootnodes(el_enode, bn_enr):
        raise Refused("execution enode AND beacon ENR are mandatory")
    return True

def preflight(manifest, archive, el_enode, bn_enr):
    obj = r136.load_manifest(manifest)
    if archive.expanduser().resolve() != r59.ARCHIVE.resolve():
        raise Refused("use existing operator-local public chain archive path")
    size = r136.verify_archive(archive)
    r59.guard_owner()  # Refuses existing owner state, or the original R59 observer state.
    r59.inspect_archive()  # Verify each original-chain genesis/config file, not just tar hash.
    iface, ip = r59.overlay_ip()  # Detect dynamic host IPv6; no VM4707 pinned address.
    r59.docker(["info", "--format", "{{.ServerVersion}}"])
    r59.images()
    validate_seeds(el_enode, bn_enr)
    res = names(obj["nodeId"])
    root = data_root(obj["nodeId"])
    require_absent(root, res)
    return {"manifest": obj, "size": size, "iface": iface, "ip": ip,
            "resources": res, "root": root}

def docker_run(image, name, network, root, bindings, args, *, beacon=False):
    command = ["run", "-d", "--pull", "never", "--platform", "linux/amd64",
               "--name", name, "--hostname", name, "--restart", "unless-stopped",
               "--stop-timeout", "60", "--init", "--network", network,
               "--user", f"{os.geteuid()}:{os.getegid()}", "--read-only",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--cpus", "1.5" if beacon else "2", "--memory", "4g",
               "--pids-limit", "384",
               "--tmpfs", "/tmp:rw,nosuid," + ("noexec" if beacon else "exec") + ",size=256m",
               "--mount", f"type=bind,source={root / 'testnet'},target=/testnet,readonly",
               "--mount", f"type=bind,source={root / 'engine.jwt'},target=/jwt/engine.jwt,readonly",
               "--mount", f"type=bind,source={root / ('beacon' if beacon else 'el')},target=/data"]
    for binding in bindings:
        command += ["--publish", binding]
    if beacon:
        command += ["--entrypoint", "lighthouse"]
    command += [image, *args]
    r59.docker(command, timeout=60)

def apply(plan, el_enode, bn_enr):
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise Refused("local interactive authorization required")
    print("Create exactly ONE new real non-signing Besu+Lighthouse observer; "
          "DO NOT use on either existing VM. No validator or new genesis. "
          "Partial failures must be reviewed manually, never blindly rerun.",
          file=sys.stderr)
    if input("Type CREATE-INDEPENDENT-NONSIGNING-OBSERVER: ") != "CREATE-INDEPENDENT-NONSIGNING-OBSERVER":
        raise Refused("explicit authorization absent")
    # Recheck identity/absence immediately before the first mutation.
    r59.guard_owner()
    require_absent(plan["root"], plan["resources"])
    original = r59.inspect_archive()
    root = plan["root"]
    res = plan["resources"]
    ip = plan["ip"]
    # Exclusivity marker: never overwrite pre-existing data or re-enter a partial apply.
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(mode=0o700)
    for segment in ("testnet", "el", "beacon"):
        (root / segment).mkdir(mode=0o700)
    for name in r59.EXPECTED:
        r59.create_file(root / "testnet" / name, original[r59.PREFIX + name])
    # Key is strictly for Engine API authentication between local EL and CL.
    import secrets
    r59.create_file(root / "engine.jwt", secrets.token_hex(32).encode("ascii"))
    r59.docker(["network", "create", "--driver", "bridge", "--ipv6", res["network"]],
               timeout=35)
    print("R137_NEW_DOCKER_NETWORK_CREATED=true", flush=True)
    el_args = [
        "--network-id=31340", "--genesis-file=/testnet/genesis.json",
        "--data-path=/data", "--p2p-enabled=true", "--discovery-enabled=true",
        "--discovery-mode=BOTH", "--p2p-interface=0.0.0.0",
        "--p2p-host=127.0.0.1", "--p2p-interface-ipv6=::",
        "--p2p-host-ipv6=" + ip, "--p2p-port=30303", "--p2p-port-ipv6=30404",
        "--p2p-discovery-port-ipv6=30404", "--p2p-ipv6-outbound-enabled=true",
        "--nat-method=NONE", "--rpc-http-enabled", "--rpc-http-host=0.0.0.0",
        "--rpc-http-port=8545", "--rpc-http-api=ETH,NET,WEB3",
        "--host-allowlist=localhost,127.0.0.1", "--engine-rpc-enabled",
        "--engine-rpc-port=8551", "--engine-host-allowlist=" + res["el"],
        "--engine-jwt-secret=/jwt/engine.jwt", "--bootnodes=" + el_enode]
    # Published ports are precisely actual per-host 6plane P2P and loopback RPC.
    el_bindings = [f"[{ip}]:30404:30404/tcp", f"[{ip}]:30404:30404/udp",
                   "127.0.0.1:28545:8545/tcp"]
    bn_bindings = [f"[{ip}]:9000:9000/tcp", f"[{ip}]:9000:9000/udp",
                   f"[{ip}]:9001:9001/udp", "127.0.0.1:25052:5052/tcp"]
    docker_run(r59.BESU_REF, res["el"], res["network"], root,
               el_bindings, el_args)
    r59.inspect_published(res["el"], el_bindings, r59.BESU_ID)
    print("R137_NEW_BESU_CONTAINER_SUBMITTED=true", flush=True)
    bn_args = [
        "--testnet-dir=/testnet", "--datadir=/data", "bn",
        "--execution-endpoint=http://" + res["el"] + ":8551",
        "--execution-jwt=/jwt/engine.jwt", "--http", "--http-address=0.0.0.0",
        "--http-port=5052", "--listen-address=::", "--port6=9000",
        "--discovery-port6=9000", "--quic-port6=9001",
        "--enr-address=" + ip, "--enr-tcp6-port=9000", "--enr-udp6-port=9000",
        "--enr-quic6-port=9001", "--enable-private-discovery",
        "--disable-upnp", "--disable-enr-auto-update",
        "--allow-insecure-genesis-sync", "--boot-nodes=" + bn_enr]
    docker_run(r59.LIGHTHOUSE_REF, res["bn"], res["network"], root,
               bn_bindings, bn_args, beacon=True)
    r59.inspect_published(res["bn"], bn_bindings, r59.LIGHTHOUSE_ID)
    print("R137_NEW_BEACON_CONTAINER_SUBMITTED=true", flush=True)
    return {"newNonSigningClientsSubmitted": True,
            "peerHandshakeVerified": False, "finalityVerified": False,
            "validatorCreated": False, "engineHostPublished": False,
            "root": str(root), "resources": res}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--execution-seed-enode-v6", required=True)
    p.add_argument("--beacon-seed-enr", required=True)
    args = p.parse_args(argv)
    try:
        item = preflight(args.manifest, args.archive,
                         args.execution_seed_enode_v6, args.beacon_seed_enr)
        report = {
            "schema": "SSE_R137_INDEPENDENT_OBSERVER_INSTALL_V1",
            "nodeId": item["manifest"]["nodeId"], "hostOverlayIpv6": item["ip"],
            "archiveVerified": True, "imagePinsVerified": True,
            "createOnceResources": item["resources"],
            "dataRoot": str(item["root"]),
            "hostPublishedEngine8551": False, "validatorCreated": False,
            "actualNativePeersVerified": False,
            "actualFinalityAgreementVerified": False,
            "mode": "PLAN_NO_MUTATION" if args.plan else "AUTHORIZED_CREATE"
        }
        if args.apply:
            report.update(apply(item, args.execution_seed_enode_v6,
                                args.beacon_seed_enr))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (Refused, r59.R59Refused, r136.Refused,
            OSError, ValueError, KeyError, TypeError) as exc:
        print("R137_INDEPENDENT_OBSERVER_REFUSED: " + type(exc).__name__ + ": " + str(exc),
              file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
