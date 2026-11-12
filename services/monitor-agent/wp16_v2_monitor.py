"""WP-16 independent V2 monitor CLI for laboratory signed HTTP evidence.

The monitor *derives* selected seats and pending epoch from Anvil RPC rather
than trusting the producer's asserted selectedMonitors array. Secrets arrive
only in an environment variable (public Anvil dev key in this experiment).
The monitor never submits on-chain payment/settlement transactions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "services" / "monitor-agent"))

from sse_chain_read import LocalRPC
from sse_evidence_wire_v1 import EvidenceScope
from sse_v2_chain_authority_v1 import V2AuthoritySpec
from sse_v2_provenance_archive_v1 import V2ProvenanceArchive


def run(args):
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if (type(manifest) is not dict or
            manifest.get("schema") != "sse-wp16-anvil-prepared-lease-v1" or
            manifest.get("chainId") != 31337 or
            manifest.get("testOnly") is not True or
            manifest.get("allowUnfinalized") is not True):
        raise ValueError("only explicitly unsafe ephemeral Anvil WP16 manifests are supported")
    if args.rpc_url != "http://127.0.0.1:8545":
        raise ValueError("WP16 accepts only isolated Anvil RPC at 127.0.0.1:8545")
    secret = os.environ.get("SSE_WP16_LAB_MONITOR_KEY")
    if not secret:
        raise ValueError("missing lab monitor key in SSE_WP16_LAB_MONITOR_KEY")
    scope = EvidenceScope(
        manifest["chainId"], manifest["controller"], manifest["leaseId"],
        manifest["epochId"], manifest["slaPolicyHash"],
        manifest["resourceProfileHash"], manifest["requestHash"])
    spec = V2AuthoritySpec(
        scope, manifest["pool"], manifest["serviceRoot"],
        manifest["controllerCodeHash"], manifest["poolCodeHash"],
        block_tag="latest", allow_unfinalized=True)
    archive = V2ProvenanceArchive(args.archive)
    started = time.monotonic()
    try:
        item = archive.capture(LocalRPC(args.rpc_url), spec, secret,
                               nonce=args.nonce, timeout=args.timeout)
    except Exception as exc:
        from sse_http_signed_delivery_v1 import TransportFailure, ProviderResponseInvalid
        from sse_evidence_wire_v1 import EvidenceError, AuthenticationError
        from sse_v2_chain_authority_v1 import V2AuthorityError
        # Unexpected failures should still fail CI, not be silently accepted
        # as an injected network fault.
        if not isinstance(exc, (TransportFailure, ProviderResponseInvalid,
                                EvidenceError, AuthenticationError, V2AuthorityError)):
            raise
        print(json.dumps({
            "status": "REJECTED_RAW_NO_PAYOUT", "errorClass": type(exc).__name__,
            "pid": os.getpid(), "elapsedMs": int((time.monotonic()-started)*1000),
            "archiveCount": archive.count(), "providerPaid": False,
        }, sort_keys=True), flush=True)
        return 2
    print(json.dumps({
        "status": "RAW_OBSERVATION_ARCHIVED_NOT_QUALIFIED",
        "pid": os.getpid(), "entryId": item.entry_id, "evidenceId": item.evidence_id,
        "signer": item.signer, "referenceHash": item.block_hash,
        "referenceCommitment": item.reference_commitment,
        "newRecord": item.new_record, "elapsedMs": int((time.monotonic()-started)*1000),
        "archiveCount": archive.count(), "providerPaid": False,
    }, sort_keys=True), flush=True)
    return 0


def main():
    p = argparse.ArgumentParser(description="WP16 independent monitor/SQLite archive process")
    p.add_argument("--rpc-url", default="http://127.0.0.1:8545")
    p.add_argument("--manifest", required=True)
    p.add_argument("--archive", required=True)
    p.add_argument("--nonce", required=True)
    p.add_argument("--timeout", type=float, default=0.6)
    a = p.parse_args()
    raise SystemExit(run(a))


if __name__ == "__main__":
    main()
