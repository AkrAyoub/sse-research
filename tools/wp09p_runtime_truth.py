#!/usr/bin/env python3
"""WP-09P: same-profile artifact vs *actually deployed* runtime vs gas report.

Offline local-only: no external network, RPC, git, deployment, or Actions.
The Foundry test deploys to ephemeral in-process EVM, never public chain.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

EIP170 = 24576
TEST_NAME = "WP09PBytecodeTruth.t.sol"
TARGET = Path("foundry/test") / TEST_NAME
PATTERN = re.compile(r"WP09P_ACTUAL_RUNTIME_BYTES\s+(\d+)")


def get_artifact_size(path: Path) -> int:
    doc = json.loads(path.read_text(encoding="utf-8"))
    bytecode = doc["deployedBytecode"]["object"]
    if not isinstance(bytecode, str) or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+", bytecode):
        raise RuntimeError("Invalid deployedBytecode field in " + str(path))
    return (len(bytecode) - 2) // 2


def parse_actual_runtime(stdout: str) -> int:
    samples = [int(m.group(1)) for m in PATTERN.finditer(stdout)]
    if len(samples) != 1:
        raise RuntimeError(f"Expected one WP09P_ACTUAL_RUNTIME_BYTES log; found {len(samples)}")
    return samples[0]


def parse_gas_report(stdout: str) -> int | None:
    lines = stdout.splitlines()
    for i, line in enumerate(lines):
        if "contracts/SSESettlement.sol:SSESettlement Contract" not in line:
            continue
        for following in lines[i+1:i+20]:
            # Foundry prints gas report columns with ASCII or Unicode pipes.
            m = re.match(r"\s*[│|]\s*([0-9,]+)\s*[│|]\s*([0-9,]+)\s*[│|]", following)
            if m:
                return int(m.group(2).replace(",", ""))
    return None


def check_repo(repo: Path) -> None:
    for name in ("foundry.toml", "contracts/SSESettlement.sol"):
        if not (repo / name).is_file():
            raise RuntimeError(f"Not a valid SSE repo: missing {name}")


def install(repo: Path) -> None:
    src = Path(__file__).resolve().parents[1] / TARGET
    dst = repo / TARGET
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        raise RuntimeError("Distribution is missing test file: " + str(src))
    if dst.exists():
        if dst.read_bytes() != src.read_bytes():
            raise RuntimeError("Refusing to overwrite existing different test: " + str(dst))
        print("Already installed:", dst)
        return
    shutil.copy2(src, dst)
    print("Installed test-only file:", dst)


def run_command(command: list[str], repo: Path, env: dict[str,str]) -> tuple[int,str]:
    try:
        r = subprocess.run(command, cwd=repo, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing locally installed executable: {command[0]}") from exc
    return r.returncode, r.stdout + r.stderr


def analyze(artifact_before: int, artifact_after: int, live: int, report: int | None) -> dict:
    same = artifact_after == live
    return {
        "artifact_before_test_bytes": artifact_before,
        "artifact_after_test_bytes": artifact_after,
        "actual_evm_runtime_bytes": live,
        "forge_gas_report_deployment_size_bytes": report,
        "eip170_limit": EIP170,
        "actual_evm_runtime_headroom_bytes": EIP170 - live,
        "artifact_matches_live": same,
        "gas_report_matches_live": report == live if report is not None else None,
        "artifact_changed_during_test": artifact_before != artifact_after,
        "decision": (
            "LIVE_AND_ARTIFACT_AGREE" if same else "ARTIFACT_AND_LIVE_DIFFER_REVIEW_COMPILER_BUILD"
        ),
    }


def verify(repo: Path, runs: int) -> dict:
    check_repo(repo)
    if not 1 <= runs <= 100_000:
        raise RuntimeError("Invalid optimizer runs")
    install(repo)
    base = repo / ".local" / "wp09p" / f"runs_{runs}"
    base.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "FOUNDRY_PROFILE": "default", "FOUNDRY_OPTIMIZER": "true",
        "FOUNDRY_OPTIMIZER_RUNS": str(runs), "FOUNDRY_OFFLINE": "true",
        "FOUNDRY_OUT": str((base / "out").resolve()),
        "FOUNDRY_CACHE_PATH": str((base / "cache").resolve()),
    })
    rc, stdout = run_command(["forge", "config", "--json"], repo, env)
    if rc:
        raise RuntimeError("forge config failed: " + stdout[-600:])
    cfg = json.loads(stdout)
    if not cfg.get("optimizer") or int(cfg.get("optimizer_runs",-1)) != runs:
        raise RuntimeError("Optimizer config mismatch")
    if Path(str(cfg.get("out", ""))).resolve() != (base / "out").resolve():
        raise RuntimeError("Isolated out path was ignored")
    if Path(str(cfg.get("cache_path", ""))).resolve() != (base / "cache").resolve():
        raise RuntimeError("Isolated cache path was ignored")
    (base / "effective_forge_config.json").write_text(json.dumps({
        k:cfg.get(k) for k in ("optimizer","optimizer_runs","via_ir","evm_version","solc_version","out","cache_path")
    },indent=2)+"\n",encoding="utf-8")

    rc, output = run_command(["forge","build","--sizes"], repo, env)
    (base / "build.log").write_text(output, encoding="utf-8")
    if rc:
        raise RuntimeError(f"Build failed; inspect {base/'build.log'}\n" + output[-700:])
    artifact = base / "out" / "SSESettlement.sol" / "SSESettlement.json"
    pre = get_artifact_size(artifact)

    # The test reports actual EVM extcodesize, not a Forge artifact estimate.
    rc, output = run_command(["forge","test", "--match-path", str(TARGET).replace("\\","/"),
                             "--gas-report", "-vv"], repo, env)
    (base / "runtime_probe.log").write_text(output, encoding="utf-8")
    if rc:
        raise RuntimeError(f"Runtime probe failed; inspect {base/'runtime_probe.log'}\n"+output[-900:])
    live = parse_actual_runtime(output)
    post = get_artifact_size(artifact)
    report = parse_gas_report(output)
    result = analyze(pre,post,live,report)
    result["optimizer_runs"] = runs
    result["compiler_config"] = "effective_forge_config.json"
    result["notes"] = [
        "Runtime code length measured with address(settlement).code.length in ephemeral Foundry EVM.",
        "Gas report may reflect a different compilation artifact; do not treat its size as a deployability proof if it disagrees with actual EVM runtime.",
        "No production code modified, no public-chain transaction performed.",
    ]
    (base / "runtime_reconciliation.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("Result:",base / "runtime_reconciliation.json")
    return result


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=["install","verify"])
    p.add_argument("--repo",type=Path,default=Path.cwd())
    p.add_argument("--runs",type=int,default=200)
    args=p.parse_args()
    repo=args.repo.resolve()
    check_repo(repo)
    if args.action == "install":
        install(repo)
    else:
        verify(repo,args.runs)
    return 0

if __name__ == "__main__":
    try:sys.exit(main())
    except (RuntimeError,OSError,ValueError,KeyError,json.JSONDecodeError) as e:
        print("WP09P ERROR:",e,file=sys.stderr)
        sys.exit(2)
