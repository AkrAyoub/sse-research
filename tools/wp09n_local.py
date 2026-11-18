#!/usr/bin/env python3
"""WP-09N local-only size sweep + successful-call Foundry benchmarks.

Never uses git remote, RPC, curl, npm, GitHub Actions, or deployment commands.
Requires locally installed forge, locally cached solc and forge-std.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

EIP170 = 24_576
TARGET_HEADROOM = 2_048
NAME = "SSESettlement"
CASE_PATTERN = re.compile(r"WP09N\|([a-z_]+)\|([a-z_]+)\s+(\d+)")


def repo_paths(repo: Path) -> tuple[Path, Path]:
    config = repo / "foundry.toml"
    if not config.is_file() or not (repo / "contracts" / "SSESettlement.sol").is_file():
        raise RuntimeError(f"Not an SSE Foundry repository: {repo}")
    return repo / "foundry" / "test" / "WP09NGasBench.t.sol", repo / ".local" / "wp09n"


def command(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str]:
    p = subprocess.run(argv, cwd=cwd, env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       encoding="utf-8", errors="replace", check=False)
    return p.returncode, p.stdout


def build_env(runs: int, dest: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["FOUNDRY_OPTIMIZER"] = "true"
    env["FOUNDRY_OPTIMIZER_RUNS"] = str(runs)
    env["FOUNDRY_OUT"] = str((dest / "out").resolve())
    env["FOUNDRY_CACHE_PATH"] = str((dest / "cache").resolve())
    env["FOUNDRY_OFFLINE"] = "true"
    return env


def verify_config(repo: Path, env: dict[str, str], runs: int, out: Path) -> None:
    status, config = command(["forge", "config", "--json"], cwd=repo, env=env)
    if status:
        raise RuntimeError(f"forge config failed: {config[-1600:]}")
    cfg = json.loads(config)
    if int(cfg.get("optimizer_runs", -1)) != runs:
        raise RuntimeError(f"Optimizer override ignored: expected {runs}, got {cfg.get('optimizer_runs')}")
    # Refuse to use the regular 'out' so existing local artifacts aren't overwritten.
    actual_out = Path(str(cfg.get("out", ""))).resolve() if cfg.get("out") else None
    if actual_out != (out / "out").resolve():
        raise RuntimeError(f"Output isolation ignored: {actual_out}, expected {(out/'out').resolve()}")


def byte_length(artifact: Path) -> int:
    data = json.loads(artifact.read_text(encoding="utf-8"))
    bytecode = data.get("deployedBytecode", {})
    obj = bytecode.get("object") if isinstance(bytecode, dict) else bytecode
    if not isinstance(obj, str) or not obj.startswith("0x"):
        raise RuntimeError(f"Missing deployed bytecode in {artifact}")
    blob = obj[2:]
    if len(blob) % 2:
        raise RuntimeError(f"Odd-length deployed bytecode in {artifact}")
    return len(blob) // 2


def sweep(repo: Path, output: Path, runs_list: tuple[int, ...]) -> int:
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for runs in runs_list:
        dest = output / f"optimize_runs_{runs}"
        dest.mkdir(parents=True, exist_ok=True)
        env = build_env(runs, dest)
        verify_config(repo, env, runs, dest)
        rc, txt = command(["forge", "build", "--sizes"], cwd=repo, env=env)
        (dest / "forge_build.log").write_text(txt, encoding="utf-8")
        if rc:
            print(f"FAILED compiler profile optimizer_runs={runs}; see {dest / 'forge_build.log'}")
            results.append({"optimizer_runs": runs, "status": "compile_failed",
                            "runtime_bytes": "", "eip170_headroom": ""})
            continue
        artifact = dest / "out" / "SSESettlement.sol" / (NAME + ".json")
        if not artifact.is_file():
            raise RuntimeError(f"No isolated artifact produced: {artifact}")
        size = byte_length(artifact)
        headroom = EIP170 - size
        status = "too_large" if headroom < 0 else "low_headroom" if headroom < TARGET_HEADROOM else "room_available"
        results.append({"optimizer_runs": runs, "status": status,
                        "runtime_bytes": size, "eip170_headroom": headroom})
        print(f"optimizer_runs={runs:4d} | bytes={size:6,d} | headroom={headroom:5,d} | {status}")
    out_csv = output / "optimizer_sweep.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["optimizer_runs", "status", "runtime_bytes", "eip170_headroom"])
        writer.writeheader()
        writer.writerows(results)
    print("Results:", out_csv)
    return 1 if any(r["status"] in {"compile_failed", "too_large"} for r in results) else 0


def parse_benchmarks(output: str) -> list[dict[str, int | str]]:
    """Read one local forge -vv log. No test gas totals or reverted call averages."""
    rows: list[dict[str, int | str]] = []
    context: dict[str, dict[str, int]] = {}
    for line in output.splitlines():
        m = CASE_PATTERN.search(line)
        if not m:
            continue
        operation, field, value = m.group(1), m.group(2), int(m.group(3))
        context.setdefault(operation, {})[field] = value
        if field == "gas":
            c = context[operation]
            rows.append({"operation": operation, "roster_size": c.get("n_active", ""),
                         "global_mode": c.get("global_mode", ""),
                         "proof_count": c.get("n_proofs", ""), "gasleft_delta": value})
            # The VRF flow emits two gas measurements from the same test.
            if operation != "vrf_purchase":
                context[operation] = {}
    return rows


def benchmark(repo: Path, output: Path) -> int:
    test_file, _ = repo_paths(repo)
    if not test_file.is_file():
        raise RuntimeError(f"Benchmark test not installed: {test_file}; run 'install' first")
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["FOUNDRY_OFFLINE"] = "true"
    rc, stdout = command(["forge", "test", "--match-path", "foundry/test/WP09NGasBench.t.sol", "-vv"],
                         cwd=repo, env=env)
    logfile = output / "wp09n_foundry_bench.log"
    logfile.write_text(stdout, encoding="utf-8")
    print(stdout[-2000:])
    if rc:
        print("BENCHMARK FAILED; no results will be reported. Inspect:", logfile)
        return rc
    rows = parse_benchmarks(stdout)
    # 6 register + 6 create-lease + 1 purchase + 1 apply + 2 finalize = 16 rows.
    if len(rows) != 16:
        raise RuntimeError(f"Expected 16 metrics, got {len(rows)}. Inspect {logfile}")
    with (output / "success_call_gas.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["operation", "roster_size", "global_mode", "proof_count", "gasleft_delta"])
        writer.writeheader()
        writer.writerows(rows)
    print("Saved:", output / "success_call_gas.csv")
    return 0


def install(repo: Path) -> None:
    target, _ = repo_paths(repo)
    for basename in ("WP09NGasBench.t.sol", "WP09NWithdrawalReentrancy.t.sol"):
        dest = target.parent / basename
        source = Path(__file__).resolve().parents[1] / "foundry" / "test" / basename
        if not source.is_file():
            raise RuntimeError(f"Distribution missing {source}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if dest.read_bytes() != source.read_bytes():
                raise RuntimeError(f"Refusing to overwrite an existing different test file: {dest}")
            print("Already installed:", dest)
            continue
        shutil.copy2(source, dest)
        print("Installed test-only file:", dest)


def security(repo: Path, output: Path) -> int:
    test_file = repo / "foundry" / "test" / "WP09NWithdrawalReentrancy.t.sol"
    if not test_file.is_file():
        raise RuntimeError(f"Security regression test not installed: {test_file}")
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["FOUNDRY_OFFLINE"] = "true"
    rc, stdout = command(["forge", "test", "--match-path", "foundry/test/WP09NWithdrawalReentrancy.t.sol", "-vv"],
                         cwd=repo, env=env)
    (output / "wp09n_security_test.log").write_text(stdout, encoding="utf-8")
    print(stdout[-1800:])
    return rc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["install", "sweep", "bench", "security", "all"])
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--runs", default="1,50,200,500", help="Optimizer runs to sweep, default: 1,50,200,500")
    args = p.parse_args(argv)
    repo = args.repo.resolve()
    _, output = repo_paths(repo)
    if args.action in ("install", "all"):
        install(repo)
    result = 0
    if args.action in ("sweep", "all"):
        runs_list = tuple(dict.fromkeys(int(t.strip()) for t in args.runs.split(",")))
        if not runs_list or any(r <= 0 or r > 100_000 for r in runs_list):
            raise ValueError("Invalid optimizer run choices")
        result |= sweep(repo, output, runs_list)
    if args.action in ("bench", "all"):
        result |= benchmark(repo, output)
    if args.action in ("security", "all"):
        result |= security(repo, output)
    return result


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"WP09N ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
