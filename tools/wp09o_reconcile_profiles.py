#!/usr/bin/env python3
"""WP09O offline, read-only compiler-size reconciliation and benchmark analysis.

This script never uses git, remote RPCs, deployments, npm, curl, or GitHub Actions.
It writes only to .local/wp09o/ and uses isolated Foundry out/cache paths.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

EIP170 = 24576
TARGET = 2048
WP09M_PREVIOUS_BYTES = 23661
MAIN_SETTLEMENT_BLOB = "5fb2380ad36327fa9b3feef2bd0d2adff73a53d5"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def validate_sweep(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    if not rows:
        raise ValueError("Empty optimizer sweep")
    out = []
    seen = set()
    for r in rows:
        run = int(r["optimizer_runs"])
        size = int(r["runtime_bytes"])
        headroom = int(r["eip170_headroom"])
        if run in seen or run <= 0 or headroom != EIP170 - size or size <= 0:
            raise ValueError("Inconsistent or duplicate optimizer measurement")
        seen.add(run)
        expected = "too_large" if headroom < 0 else "low_headroom" if headroom < TARGET else "room_available"
        if r["status"] != expected:
            raise ValueError(f"Inconsistent status for {run}: expected {expected}")
        out.append({"optimizer_runs": run, "runtime_bytes": size, "headroom": headroom, "status": expected})
    return sorted(out, key=lambda a: a["optimizer_runs"])


def validate_gas(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], int]:
    if len(rows) != 16:
        raise ValueError(f"Expected 16 measurements; found {len(rows)}")
    result = {}
    for r in rows:
        key = (r["operation"], r["roster_size"], r["global_mode"])
        gas = int(r["gasleft_delta"])
        if gas <= 0 or key in result:
            raise ValueError(f"Invalid or duplicate gas sample: {key}")
        result[key] = gas
    required = [("create_lease", n, mode) for n in ("16", "160") for mode in ("0", "1")]
    required += [("global_finalize", n, "") for n in ("16", "160")]
    required += [("register", n, mode) for n in ("16", "160") for mode in ("0", "1")]
    required += [("vrf_purchase", "16", ""), ("vrf_apply", "", "")]
    missing = [k for k in required if k not in result]
    if missing:
        raise ValueError(f"Missing required gas samples: {missing}")
    return result


def analyze(sweep: list[dict[str,str]], gas: list[dict[str,str]]) -> dict:
    profiles = validate_sweep(sweep)
    g = validate_gas(gas)
    modes = {}
    for n in ("16", "160"):
        legacy = g[("create_lease", n, "0")]
        global_ = g[("create_lease", n, "1")]
        finalize = g[("global_finalize", n, "")]
        modes[n] = {
            "legacy_create_gas": legacy,
            "global_create_gas": global_,
            "global_create_reduction_pct": round(100*(1-global_/legacy),2),
            "global_finalize_10_proofs_gas": finalize,
            "global_create_plus_finalize_gas": global_ + finalize,
            "global_register_gas": g[("register", n, "1")],
            "legacy_register_gas": g[("register", n, "0")],
        }
    p200 = next((p for p in profiles if p["optimizer_runs"] == 200), None)
    return {
        "source": "user-uploaded WP09N optimizer_sweep.csv and success_call_gas.csv",
        "eip170_limit": EIP170,
        "recommended_discretionary_headroom": TARGET,
        "historical_wp09m_default_report_runtime_bytes": WP09M_PREVIOUS_BYTES,
        "optimizer_profiles": profiles,
        "default_200_profile": p200,
        "historical_vs_200_discrepancy_bytes": WP09M_PREVIOUS_BYTES-int(p200["runtime_bytes"]) if p200 else None,
        "comparison_by_roster": modes,
        "global_create_growth_16_to_160_pct": round(100*(g[("create_lease","160","1")]/g[("create_lease","16","1")]-1),4),
        "legacy_create_growth_16_to_160_pct": round(100*(g[("create_lease","160","0")]/g[("create_lease","16","0")]-1),2),
        "vrf_purchase_16_gas": g[("vrf_purchase","16","")],
        "vrf_apply_gas": g[("vrf_apply","","")],
        "metric_scope": "gasleft delta around successful internal contract calls, not full transaction gas; one sample per case; mock coordinator",
        "recommendation": "retain optimizer_runs=200 until identical-profile full-suite and bytecode/report reconciliation; prefer global Merkle for large rosters but measure end-to-end gas",
    }


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def runtime_size(artifact: Path) -> int:
    obj = json.loads(artifact.read_text(encoding="utf-8"))["deployedBytecode"]["object"]
    if not isinstance(obj,str) or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+",obj):
        raise ValueError(f"Invalid deployed bytecode in {artifact}")
    return (len(obj)-2)//2


def parse_gas_report_size(text: str) -> int | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "contracts/SSESettlement.sol:SSESettlement Contract" not in line:
            continue
        for nextline in lines[i+1:i+18]:
            m = re.match(r"\s*[│|]\s*([\d,]+)\s*[│|]\s*([\d,]+)\s*[│|]", nextline)
            if m:
                return int(m.group(2).replace(',',''))
    return None


def run(args: list[str], cwd: Path, env: dict | None = None) -> tuple[int,str]:
    r = subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                       text=True,encoding="utf-8",errors="replace",check=False)
    return r.returncode,r.stdout


def verify(repo:Path, profile:int, *, without_bench:bool=False) -> dict:
    if not (repo/"foundry.toml").is_file() or not (repo/"contracts/SSESettlement.sol").is_file():
        raise ValueError("Run at SSE repository root, containing foundry.toml and contracts/SSESettlement.sol")
    if profile <= 0 or profile > 100000:
        raise ValueError("Invalid optimizer runs")
    base=repo/".local"/"wp09o"/f"runs_{profile}"
    base.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update({"FOUNDRY_PROFILE":"default","FOUNDRY_OPTIMIZER":"true",
                "FOUNDRY_OPTIMIZER_RUNS":str(profile),"FOUNDRY_OFFLINE":"true",
                "FOUNDRY_OUT":str((base/"out").resolve()),
                "FOUNDRY_CACHE_PATH":str((base/"cache").resolve())})
    rc, txt=run(["forge","config","--json"],repo,env)
    if rc:raise RuntimeError(f"forge config failed: {txt[-700:]}")
    cfg=json.loads(txt)
    if int(cfg.get("optimizer_runs",-1))!=profile or not cfg.get("optimizer"):
        raise RuntimeError("Foundry ignored optimizer settings; refusing profile comparison")
    if Path(str(cfg.get("out",""))).resolve()!=(base/"out").resolve():
        raise RuntimeError("Foundry ignored isolated output directory")
    rc, output=run(["forge","build","--sizes"],repo,env)
    (base/"forge_build.log").write_text(output,encoding="utf-8")
    if rc:raise RuntimeError(f"Forge build failed; see {base/'forge_build.log'}")
    artifact=base/"out"/"SSESettlement.sol"/"SSESettlement.json"
    size=runtime_size(artifact)
    source=repo/"contracts"/"SSESettlement.sol"
    source_bytes=source.read_bytes()
    raw_blob=git_blob_sha(source_bytes)
    lf_blob=git_blob_sha(source_bytes.replace(b"\r\n", b"\n"))
    result={"optimizer_runs":profile,"forge_runtime_bytes":size,
            "eip170_headroom":EIP170-size,"wp09m_prior_bytes":WP09M_PREVIOUS_BYTES,
            "diff_vs_wp09m_bytes":size-WP09M_PREVIOUS_BYTES,
            "settlement_blob_sha_raw":raw_blob,
            "settlement_blob_sha_lf_normalized":lf_blob,
            "equals_previous_github_main_source":MAIN_SETTLEMENT_BLOB in (raw_blob,lf_blob),
            "optimizer":bool(cfg.get("optimizer")),"via_ir":cfg.get("via_ir",None),
            "solc_version_config":cfg.get("solc_version",cfg.get("solc")),
            "evm_version":cfg.get("evm_version")}
    rc,txt=run(["forge","--version"],repo,env)
    result["forge_version"]=txt.strip() if rc==0 else "unknown"
    if not without_bench:
        if not (repo/"foundry/test/WP09NGasBench.t.sol").is_file():
            raise ValueError("WP09N gas benchmark test missing; use --without-bench or install WP09N")
        rc,out=run(["forge","test","--match-path","foundry/test/WP09NGasBench.t.sol","--gas-report","-vv"],repo,env)
        (base/"forge_benchmark_gas_report.log").write_text(out,encoding="utf-8")
        if rc:raise RuntimeError(f"Foundry benchmark failed; see {base/'forge_benchmark_gas_report.log'}")
        reported=parse_gas_report_size(out)
        if reported is None:raise RuntimeError("SSESettlement gas-report size not found; inspect benchmark log")
        result["forge_gas_report_runtime_bytes"]=reported
        result["bytecode_and_gas_report_agree"]=(reported==size)
    path=base/"reconciliation.json"
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))
    if not without_bench and not result["bytecode_and_gas_report_agree"]:
        print("WARNING: same-profile Foundry artifact and gas report sizes disagree",file=sys.stderr)
        return result
    return result


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=["analyze","verify"])
    p.add_argument("--repo",type=Path,default=Path.cwd())
    p.add_argument("--sweep",type=Path,default=Path(".local/wp09n/optimizer_sweep.csv"))
    p.add_argument("--gas",type=Path,default=Path(".local/wp09n/success_call_gas.csv"))
    p.add_argument("--runs",type=int,default=200)
    p.add_argument("--without-bench",action="store_true")
    args=p.parse_args(argv)
    repo=args.repo.resolve()
    if args.action=="analyze":
        s=(args.sweep if args.sweep.is_absolute() else repo/args.sweep)
        g=(args.gas if args.gas.is_absolute() else repo/args.gas)
        result=analyze(read_csv(s),read_csv(g))
        out=repo/".local"/"wp09o"/"wp09n_analysis.json"
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,indent=2))
        print("Saved:",out)
        return 0
    result=verify(repo,args.runs,without_bench=args.without_bench)
    return 1 if result.get("bytecode_and_gas_report_agree") is False else 0


if __name__=="__main__":
    try:sys.exit(main())
    except (OSError,ValueError,KeyError,RuntimeError) as e:
        print("WP09O ERROR:",str(e),file=sys.stderr);sys.exit(2)
