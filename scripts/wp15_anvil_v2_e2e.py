#!/usr/bin/env python3
"""WP-15: real Anvil JSON-RPC -> deployed V2 contracts -> signed HTTP -> V2 archive.

LAB ONLY: uses Anvil's publicly known mnemonic/unlocked development accounts,
an INSECURE fake VRF coordinator, and short artificial deadlines.
Never point at a real chain or a funded production RPC.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
for relative in ("tools", "services/provider-agent", "services/monitor-agent"):
    sys.path.insert(0, str(ROOT / relative))

from eth_account import Account
from eth_abi import encode

from sse_challenge import keccak256
from sse_chain_read import LocalRPC, _call, _words, decode_struct
from sse_evidence_wire_v1 import EvidenceScope
from sse_v2_chain_authority_v1 import (
    V2AuthoritySpec, V2AuthorityError, V2_LEASE_FIELDS,
    V2_EPOCH_FIELDS, read_v2_authority,
)
from sse_v2_provenance_archive_v1 import V2ProvenanceArchive
from signed_http_service import make_server
from typed_evidence import Domain

MNEMONIC = "test test test test test test test test test test test junk"
CHAIN_ID = 31337
FEE = 10**16
PROFILE = "0x" + keccak256(b"WP15 signed HTTP resource profile").hex()
SLA = "0x" + keccak256(b"WP15 local challenge SLA - experiment only").hex()
REQUEST = "0x" + keccak256(b"WP15 admitted EVM epoch request").hex()
TX_GAS = hex(8_000_000)


def _bytes32(value: str) -> bytes:
    if not isinstance(value, str) or len(value) != 66:
        raise ValueError("expected exact bytes32")
    return bytes.fromhex(value[2:])


class LiveAnvil:
    def __init__(self, url: str):
        self.rpc = LocalRPC(url, timeout=8.0)
        self.receipts = []
        Account.enable_unaudited_hdwallet_features()
        self.accounts = [
            Account.from_mnemonic(MNEMONIC, account_path=f"m/44'/60'/0'/0/{i}")
            for i in range(12)
        ]
        self.addresses = [a.address.lower() for a in self.accounts]

    def require_lab(self):
        chain = int(self.rpc.request("eth_chainId", []), 16)
        if chain != CHAIN_ID:
            raise RuntimeError(f"refuse non-lab chain ID {chain}")
        unlocked = {a.lower() for a in self.rpc.request("eth_accounts", [])}
        if any(a not in unlocked for a in self.addresses[:10]):
            raise RuntimeError("Anvil must expose the 12 deterministic default mnemonic accounts")
        if int(self.rpc.request("eth_blockNumber", []), 16) != 0:
            raise RuntimeError("WP15 requires a fresh EMPTY Anvil chain; refusing persistent chain")

    def tx(self, signer: int, *, to: str | None = None,
           data: str = "0x", value: int = 0, name: str = "tx") -> dict:
        request = {
            "from": self.addresses[signer], "gas": TX_GAS,
            "value": hex(value), "data": data,
        }
        if to is not None:
            request["to"] = to
        hash_ = self.rpc.request("eth_sendTransaction", [request])
        for _ in range(40):
            receipt = self.rpc.request("eth_getTransactionReceipt", [hash_])
            if receipt is not None:
                if int(receipt["status"], 16) != 1:
                    raise RuntimeError(f"Anvil transaction reverted: {name} {hash_}")
                item = {
                    "name": name, "transactionHash": hash_,
                    "blockNumber": int(receipt["blockNumber"], 16),
                    "gasUsed": int(receipt["gasUsed"], 16),
                }
                self.receipts.append(item)
                return receipt
            time.sleep(0.1)
        raise RuntimeError(f"Anvil did not mine {name}")

    def deploy(self, name: str, *, types: list[str] | None = None,
               values: list | tuple = ()) -> str:
        path = ROOT / "out" / f"{name}.sol" / f"{name}.json"
        if not path.is_file():
            raise RuntimeError(f"missing Foundry artifact {path}; run forge build")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        bytecode = artifact["bytecode"]["object"]
        if not isinstance(bytecode, str) or not bytecode.startswith("0x"):
            raise RuntimeError(f"invalid bytecode artifact for {name}")
        args = encode(types or [], list(values)).hex()
        receipt = self.tx(0, data=bytecode + args, name=f"deploy:{name}")
        address = receipt.get("contractAddress")
        if not address:
            raise RuntimeError(f"no contract address for {name}")
        return address.lower()

    def send(self, signer: int, to: str, signature: str,
             types: list[str] | None = None, values: list | tuple = (),
             *, value: int = 0):
        selector = keccak256(signature.encode("ascii"))[:4]
        args = encode(types or [], list(values))
        self.tx(signer, to=to, data="0x" + (selector + args).hex(),
                value=value, name=signature)

    def read_uint(self, address: str, signature: str, args: tuple[int, ...] = ()) -> int:
        return int(_words(_call(self.rpc, address, signature, args, "latest"), 1)[0], 16)

    def read_address(self, address: str, signature: str, args: tuple[int, ...] = ()) -> str:
        word = _words(_call(self.rpc, address, signature, args, "latest"), 1)[0]
        if int(word, 16) >> 160:
            raise RuntimeError("noncanonical on-chain address")
        return "0x" + word[-40:]

    def runtime_hash(self, address: str) -> str:
        runtime = self.rpc.request("eth_getCode", [address, "latest"])
        if not runtime or runtime == "0x":
            raise RuntimeError("empty deployed runtime code")
        return "0x" + keccak256(bytes.fromhex(runtime[2:])).hex()

    def warp_after(self, unix_seconds: int):
        now = int(self.rpc.request("eth_getBlockByNumber", ["latest", False])["timestamp"], 16)
        self.rpc.request("evm_increaseTime", [max(1, unix_seconds - now + 1)])
        self.rpc.request("evm_mine", [])

    def time(self) -> int:
        return int(self.rpc.request("eth_getBlockByNumber", ["latest", False])["timestamp"], 16)


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run(url: str, out: Path) -> dict:
    anvil = LiveAnvil(url)
    anvil.require_lab()
    consumer, provider = anvil.addresses[:2]
    port = _unused_port()
    root = f"http://127.0.0.1:{port}"

    coordinator = anvil.deploy("WP15LabCoordinator")
    adapter = anvil.deploy("SSEVRFV25Adapter",
        types=["address", "address", "bytes32", "uint256", "uint16", "uint32", "bool"],
        values=[coordinator, consumer, keccak256(b"WP15 lab lane"), 777, 3, 300_000, False])
    pool = anvil.deploy("ScalableMonitorCommitteeV2",
        types=["address", "address", "uint256", "uint256", "uint64"],
        values=[adapter, adapter, 10**18, 10**17, 86400])
    controller = anvil.deploy("SSELeaseControllerV2", types=["address"], values=[pool])
    anvil.send(0, adapter, "bindPool(address)", ["address"], [pool])
    anvil.send(0, pool, "bindController(address)", ["address"], [controller])

    lease_types = "(address,bytes32,bytes32,bytes32,uint256,uint256,uint256,uint64,uint64)"
    committee_types = "(address,address,uint8,uint8,uint8,uint64,uint64,uint64,uint64,uint64)"
    lease_terms = (
        provider, keccak256(root.encode("utf-8")), _bytes32(PROFILE),
        _bytes32(SLA), FEE, 3, FEE, 300, 60)
    # On real Anvil each eth_sendTransaction mines a block, unlike a Foundry
    # unit test's internal calls. Give 16+ enrollment transactions ample time.
    committee_terms = (
        consumer, provider, 4, 3, 2,
        120, 120, 120, 120, 1800)
    anvil.send(0, controller,
        f"createLease({lease_types},{committee_types})",
        [lease_types, committee_types], [lease_terms, committee_terms],
        value=3 * FEE)
    lease_id = anvil.read_uint(controller, "nextLeaseId()") - 1
    lease = decode_struct(
        _call(anvil.rpc, controller, "getLease(uint256)", (lease_id,), "latest"),
        V2_LEASE_FIELDS)
    assignment = lease["assignmentId"]
    if (lease_id != 1 or assignment != 1 or lease["escrow"] != 3 * FEE):
        raise AssertionError("unexpected funded lease identity or amount")
    anvil.send(1, controller, "acceptLease(uint256)", ["uint256"], [lease_id])

    for index in range(2, 10):
        anvil.send(index, pool, "register()", value=10**18)
        anvil.send(index, pool, "join(uint256)", ["uint256"], [assignment],
                   value=10**17)

    enrollment_end = anvil.read_uint(pool, "enrollmentDeadline(uint256)", (assignment,))
    anvil.warp_after(enrollment_end)
    anvil.send(0, pool, "sealEnrollment(uint256)", ["uint256"], [assignment])
    anvil.send(0, adapter, "requestRandomness(uint256)", ["uint256"], [assignment])
    request_id = anvil.read_uint(adapter, "requestForAssignment(uint256)", (assignment,))
    anvil.send(0, coordinator, "deliver(uint256,uint256)",
               ["uint256", "uint256"], [request_id, 123456])
    anvil.send(0, adapter, "finalizeRandomness(uint256)",
               ["uint256"], [assignment])
    anvil.send(0, pool, "processSelection(uint256,uint8)",
               ["uint256", "uint8"], [assignment, 16])
    anvil.send(0, pool, "finalizeSelection(uint256)", ["uint256"], [assignment])

    selected = [anvil.read_address(
        pool, "seatAt(uint256,uint256)", (assignment, i)) for i in range(4)]
    if len(set(selected)) != 4 or not set(selected).issubset(set(anvil.addresses[2:10])):
        raise AssertionError("selected monitors not among the registered lab accounts")
    for monitor in selected:
        anvil.send(anvil.addresses.index(monitor), pool, "confirm(uint256)",
                   ["uint256"], [assignment])
    anvil.send(0, controller, "activateLease(uint256)", ["uint256"], [lease_id])
    anvil.send(0, controller, "admitEpoch(uint256,bytes32)",
               ["uint256", "bytes32"], [lease_id, _bytes32(REQUEST)])
    epoch = decode_struct(
        _call(anvil.rpc, controller, "getEpoch(uint256,uint256)",
              (lease_id, 0), "latest"), V2_EPOCH_FIELDS)
    if epoch["requestHash"] != REQUEST or not epoch["admitted"] or epoch["allocated"]:
        raise AssertionError("expected a Live unresolved V2 epoch")

    scope = EvidenceScope(CHAIN_ID, controller, lease_id, 0, SLA, PROFILE, REQUEST)
    spec = V2AuthoritySpec(
        scope, pool, root, anvil.runtime_hash(controller), anvil.runtime_hash(pool),
        block_tag="latest", allow_unfinalized=True)
    snapshot = read_v2_authority(anvil.rpc, spec)
    if snapshot.monitors != tuple(selected):
        raise AssertionError("actual EIP-1898 seat reconstruction mismatch")
    if anvil.read_uint(controller, "withdrawable(address)", (int(provider, 16),)) != 0:
        raise AssertionError("provider unexpectedly paid before consent")

    # bytes(...).hex() never carries a HexBytes 0x prefix.
    provider_key = "0x" + bytes(anvil.accounts[1].key).hex()
    monitor_key = "0x" + bytes(anvil.accounts[anvil.addresses.index(selected[0])].key).hex()
    server = make_server(port, provider_key, Domain(CHAIN_ID, controller),
                         lease_id, 0, REQUEST)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as directory:
            archive = V2ProvenanceArchive(Path(directory) / "provenance.sqlite")
            saved = archive.capture(anvil.rpc, spec, monitor_key)
            if not saved.new_record or saved.signer != selected[0] or archive.count() != 1:
                raise AssertionError("HTTP observation not archived once")
            if saved.block_hash != snapshot.block_hash:
                raise AssertionError("archive anchor differs from actual pinned block")
            verified = archive.load_verified(anvil.rpc, spec, saved.entry_id)
            if verified.provider_bytes != saved.provider_bytes:
                raise AssertionError("provider payload changed on retrieval")

            # Current-epoch provenance stops being admissible after the chain
            # state changes, but the ORIGINAL block remains verifiable.
            deadline = anvil.read_uint(pool, "serviceDeadline(uint256)", (assignment,))
            anvil.warp_after(deadline)
            anvil.send(0, pool, "expire(uint256)", ["uint256"], [assignment])
            anvil.send(0, controller, "endAdmissions(uint256)", ["uint256"], [lease_id])
            try:
                read_v2_authority(anvil.rpc, spec)
            except V2AuthorityError:
                pass
            else:
                raise AssertionError("current-block authorization accepted expired lease")
            historic = archive.load_verified(anvil.rpc, spec, saved.entry_id)
            if historic.block_hash != saved.block_hash:
                raise AssertionError("historical authenticated reference did not survive closure")
            if anvil.read_uint(controller, "withdrawable(address)",
                               (int(provider, 16),)) != 0:
                raise AssertionError("raw evidence caused an unauthorized provider payout")
            if anvil.read_uint(pool, "status(uint256)", (assignment,)) != 7:
                raise AssertionError("monitor assignment was not Released")
            fields = historic.monitor_envelope
            report = {
                "schema": "sse-wp15-real-anvil-evidence-v1",
                "chainId": CHAIN_ID, "rpcMode": "latest-explicitly-unfinalized",
                "consensusProofVerified": False, "vrfProofVerified": False,
                "mockCoordinator": True, "consumerDeliveryProven": False,
                "automaticPayoutAuthorized": False,
                "controller": controller, "pool": pool,
                "vrfAdapter": adapter, "labCoordinator": coordinator,
                "leaseId": lease_id, "assignmentId": assignment,
                "vrfRequestId": request_id, "selectedMonitors": selected,
                "evidenceEntryId": saved.entry_id,
                "evidenceId": saved.evidence_id,
                "authorityBlockNumber": historic.block_number,
                "authorityBlockHash": historic.block_hash,
                "authorityCommitment": historic.reference_commitment,
                "providerCreditFromRawEvidence": 0,
                "providerSignatureBytes": len(saved.provider_bytes),
                "receiptCount": len(anvil.receipts), "txReceipts": anvil.receipts,
                "testNotice": "isolated Anvil, public lab mnemonic, mock VRF; no physical SLA conclusion",
            }
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return report
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description="Run WP-15 real Anvil V2 evidence integration")
    parser.add_argument("--rpc-url", default="http://127.0.0.1:8545")
    parser.add_argument("--output", default="artifacts/wp15-anvil-v2-trace.json")
    args = parser.parse_args()
    result = run(args.rpc_url, Path(args.output))
    print(json.dumps({
        "status": "PASSED_REAL_ANVIL_RPC_LAB_ONLY",
        "leaseId": result["leaseId"],
        "registered": 8, "selected": len(result["selectedMonitors"]),
        "receiptCount": result["receiptCount"],
        "historicalEvidenceReverified": True,
        "realVRFProof": False, "physicalDeliveryProven": False,
        "payoutFromEvidence": False, "trace": args.output,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
