#!/usr/bin/env python3
"""Owner-run isolated V4 transaction rehearsal, never live evidence.
Starts and stops its own fresh loopback-only Anvil. Uses public disposable
development keys; no live RPC parameter, existing keystore or state directory.
Fixture votes and accelerated deadlines test contractual mechanics, not SLA truth.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

from eth_account import Account
from eth_utils import keccak
import rlp

import sse_v4_abi as a
import sse_v4_terms as t

ORIGINAL = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
MNEMONIC = "test test test test test test test test test test test junk"
FEE = 10**15
BOND = 10**15
REWARD = 10**14


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


class RpcError(RuntimeError):
    pass


def run(bindir, logdir, port):
    require(1024 <= port <= 65535 and port not in (18545, 28545, 8545), "unsafe rehearsal port")
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
    logdir.mkdir(mode=0o700, parents=True, exist_ok=False)
    logdir = logdir.resolve()
    url = "http://127.0.0.1:" + str(port)
    Account.enable_unaudited_hdwallet_features()
    accounts = [Account.from_mnemonic(MNEMONIC, account_path=f"m/44'/60'/0'/0/{i}") for i in range(12)]
    by_address = {x.address.lower(): x for x in accounts}
    deployer, consumer, provider = [x.address.lower() for x in accounts[:3]]
    monitors = [x.address.lower() for x in accounts[3:11]]
    with (logdir / "anvil.log").open("w") as alog:
        proc = subprocess.Popen([str(bindir / "anvil"), "--host", "127.0.0.1",
            "--port", str(port), "--chain-id", "31340", "--accounts", "12",
            "--mnemonic", MNEMONIC], stdout=alog, stderr=subprocess.STDOUT)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def rpc(method, params):
                require(proc.poll() is None, "owned Anvil exited")
                req = urllib.request.Request(url, json.dumps({"jsonrpc": "2.0", "id": 1,
                    "method": method, "params": params}).encode(), {"Content-Type": "application/json"})
                with opener.open(req, timeout=10) as res:
                    obj = json.load(res)
                if "error" in obj:
                    raise RpcError(json.dumps(obj["error"], sort_keys=True))
                return obj["result"]

            for _ in range(50):
                try:
                    if rpc("eth_chainId", []) == hex(31340):
                        break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError("Anvil not ready")
            require("anvil" in rpc("web3_clientVersion", []).lower(), "not Anvil")
            genesis = rpc("eth_getBlockByNumber", ["0x0", False])["hash"].lower()
            require(genesis != ORIGINAL and int(rpc("eth_blockNumber", []), 16) == 0, "not a fresh isolated chain")
            require([x.lower() for x in rpc("eth_accounts", [])] == [x.address.lower() for x in accounts],
                    "unexpected disposable account set")
            require(rpc("eth_getTransactionCount", [deployer, "latest"]) == "0x0", "deployer nonce not zero")
            print("ISOLATED_GENESIS=" + genesis, flush=True)
            env = dict(os.environ, SSE_V4_DEPLOYER=accounts[0].address,
                       SSE_V4_PER_SEAT_BOND_WEI=str(BOND), FOUNDRY_BROADCAST=str(logdir / "broadcast"))
            with (logdir / "deploy.log").open("w") as f:
                subprocess.run([str(bindir / "forge"), "script",
                    "script/DeploySSEV4Candidate31340.s.sol:DeploySSEV4Candidate31340",
                    "--rpc-url", url, "--private-key", "0x" + accounts[0].key.hex(),
                    "--broadcast", "--slow", "-vv"], env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
            require(int(rpc("eth_getTransactionCount", [deployer, "latest"]), 16) == 5, "expected five CREATEs")
            modules = {m: "0x" + keccak(rlp.encode([bytes.fromhex(deployer[2:]), i]))[-20:].hex()
                       for i, m in enumerate(("board", "registry", "ledger", "standby", "market"))}
            def view(m, sig, types=(), args=(), out=("uint256",)):
                return a.view(rpc, modules[m], sig, types, args, out, tag="latest")
            def struct(m, sig, types, args, fields):
                return a.read_struct(rpc, modules[m], sig, types, args, fields, tag="latest")
            for m, addr in modules.items():
                require(rpc("eth_getCode", [addr, "latest"]) != "0x", "missing " + m)
            for m, getter in (("board", "board"), ("registry", "registry"), ("standby", "standby"), ("ledger", "votes")):
                require(view("market", getter + "()", out=("address",))[0].lower() == modules[m], "wrong market wiring")
                reverse = "settlement()" if m == "ledger" else "market()"
                require(view(m, reverse, out=("address",))[0].lower() == modules["market"], "wrong reverse wiring")
            print("ISOLATED_FIVE_MODULE_WIRING_PASSED", flush=True)
            with (logdir / "modules.json").open("w") as f:
                json.dump({"genesisHash": genesis, "modules": modules, "fixtureOnly": True}, f, indent=2)

            def tx(sender, action, label):
                m, data, value = action
                require(sender in by_address, "not a disposable sender")
                req = {"from": sender, "to": modules[m], "data": data, "value": hex(value)}
                gas = int(rpc("eth_estimateGas", [req]), 16)
                req["gas"] = hex(gas * 2 + 50000)
                h = rpc("eth_sendTransaction", [req])
                for _ in range(50):
                    receipt = rpc("eth_getTransactionReceipt", [h])
                    if receipt is not None:
                        break
                    time.sleep(.1)
                else:
                    raise RuntimeError("receipt timeout " + h)
                with (logdir / "receipts.jsonl").open("a") as f:
                    f.write(json.dumps({"label": label, "receipt": receipt}) + "\n")
                require(receipt["status"] == "0x1", "reverted " + label)
                print(label, h, "gas", int(receipt["gasUsed"], 16), flush=True)

            def expect_revert(sender, action, error):
                m, data, value = action
                try:
                    rpc("eth_call", [{"from": sender, "to": modules[m], "data": data, "value": hex(value)}, "latest"])
                except RpcError as exc:
                    require(a.selector(error).hex() in str(exc).lower(), "wrong revert: " + str(exc))
                    print("EXPECTED_REVERT", error, flush=True)
                    return
                raise RuntimeError("expected revert " + error)

            def now():
                return int(rpc("eth_getBlockByNumber", ["latest", False])["timestamp"], 16)
            def after(deadline):
                rpc("evm_setNextBlockTimestamp", [max(now()+1, deadline+1)])
                rpc("evm_mine", [])
            def h(s):
                return "0x" + keccak(text=s).hex()
            def sign(sender, digest):
                return bytes(by_address[sender].unsafe_sign_hash(digest).signature)

            for monitor in monitors:
                tx(monitor, a.register_monitor(2, 2*BOND), "register monitor")
            rid = view("board", "nextRequestId()")[0]
            lid = view("market", "nextLeaseId()")[0]
            q = dict(profileHash=h("fixture profile"), policyHash=h("fixture policy"),
                artifactCommitment=h("fixture artifact"), maxEpochFee=FEE,
                biddingClose=now()+3600, fixedEpochs=4, maxEpochs=4, seats=4, standbys=2,
                faultTolerance=1, perReportReward=REWARD)
            terms = dict(acceptSeconds=86400, confirmationRoundSeconds=600,
                responseSeconds=180, monitoringSeconds=300, evidenceSeconds=600,
                idleSeconds=86400, reservationFee=FEE//5, exposureBudget=FEE*3//2,
                conditionalQuorumPolicy=True, responseAdmitsReceipt=False)
            tx(consumer, a.create_request(q), "create request")
            tx(provider, a.place_bid(rid, FEE, 4, now()+3600, h("fixture endpoint"), h("fixture offer")), "place bid")
            tx(consumer, a.award_and_fund(rid, 0, terms, q, dict(epochFee=FEE, epochs=4)), "award and fund")
            def lease():
                return struct("market", "lease(uint256)", ("uint256",), (lid,), a.LEASE_FIELDS)
            def assignment():
                return struct("standby", "assignment(uint256)", ("uint256",), (lid,), a.ASSIGNMENT_FIELDS)
            def epoch(eid):
                return struct("ledger", "epoch(uint256,uint256)", ("uint256","uint256"), (lid,eid), a.LEDGER_EPOCH_FIELDS)
            def sci(eid):
                return struct("market", "scientificEpoch(uint256,uint256)", ("uint256","uint256"), (lid,eid), a.SCIENTIFIC_EPOCH_FIELDS)
            def accounting():
                return view("market","scientificAccounting(uint256)",("uint256",),(lid,),("uint256",)*6+("bool",))
            l = lease()
            request = struct("board", "request(uint256)", ("uint256",), (rid,), a.REQUEST_FIELDS)
            bid = struct("board", "bidAt(uint256,uint256)", ("uint256","uint256"), (rid,0), a.BID_FIELDS)
            require("0x"+t.terms_hash(31340, modules["market"], lid, 0, request, bid, terms).hex() == l["termsHash"],
                    "actual deployed terms hash mismatch")
            while int(rpc("eth_blockNumber", []), 16) <= l["entropyBlock"]:
                rpc("evm_mine", [])
            tx(deployer, a.lease_call("drawCommittee", lid), "draw committee")
            aa = assignment()
            require(len(aa["primary"]) == 4 and len(aa["standby"]) == 2, "sample unavailable; no silent retry")
            omitted = aa["primary"][0]
            for m in aa["primary"][1:]:
                tx(m, a.standby_call("confirm", lid), "confirm primary")
            after(aa["deadline"])
            tx(deployer, a.standby_call("advance", lid), "promote standby")
            aa2 = assignment()
            require(omitted not in aa2["primary"] and aa["standby"][0] in aa2["primary"], "wrong standby promotion")
            tx(aa["standby"][0], a.standby_call("confirm", lid), "confirm promoted standby")
            tx(deployer, a.lease_call("activateCommittee", lid), "activate committee")
            tx(provider, a.accept_lease(lid, l["termsHash"]), "accept lease")
            selected = [x.lower() for x in view("ledger","selected(uint256)",("uint256",),(lid,),("address[]",))[0]]
            require(set(selected) == set(aa2["primary"]) and len(selected) == 4, "wrong frozen committee")
            md = t.domain_separator(t.MARKET_NAME,31340,modules["market"])
            ld = t.domain_separator(t.LEDGER_NAME,31340,modules["ledger"])
            for eid, verdict in enumerate((1,2,0)):
                request_hash = h(f"fixture epoch {eid}")
                tx(consumer,a.start_epoch(lid,request_hash),f"start epoch {eid}")
                if verdict:
                    response = h(f"fixture response {eid}")
                    tx(deployer,a.authenticate_response(lid,eid,response,sign(provider,
                        t.response_digest(md,lid,eid,request_hash,response))),f"authenticate response {eid}")
                    if verdict == 2:
                        after(epoch(eid)["responseDeadline"])
                    for monitor in selected[:3]:
                        evidence = h(f"FIXTURE evidence {eid} {monitor}")
                        sig = sign(monitor,t.vote_digest(ld,lid,eid,request_hash,verdict,response,evidence))
                        action = ("ledger",a.calldata("submitSignedVote(uint256,uint256,uint8,bytes32,bytes)",
                            ("uint256","uint256","uint8","bytes32","bytes"),(lid,eid,verdict,a.b32(evidence),sig)),0)
                        tx(deployer,action,f"relay signed vote {eid}")
                else:
                    after(epoch(eid)["responseDeadline"])
                    expect_revert(selected[0],a.submit_vote_direct(lid,eid,2,h("fixture timeout")), "InvalidPhase()")
                after(epoch(eid)["monitoringClose"])
                tx(deployer,a.epoch_call("finalizeEpoch",lid,eid),f"finalize epoch {eid}")
                s = sci(eid)
                require((s["mask"],s["providerCredit"],s["consumerCredit"],s["unresolved"]) ==
                        ((4,FEE,0,0),(3,0,FEE*4//5,FEE//5),(7,0,0,FEE))[eid], "unexpected scientific epoch")
                require(accounting()[-1], "conservation failed")
                print("SCIENTIFIC_EPOCH",eid,json.dumps(s,sort_keys=True),flush=True)
            require(accounting()[:4] == (4*FEE,FEE,6*FEE//5,3*FEE//2), "unexpected exposure")
            expect_revert(consumer,a.start_epoch(lid,h("blocked fourth epoch")),"ExposureExceeded()")
            tx(consumer,a.lease_call("closeLease",lid),"close lease")
            for eid in range(3):
                me = struct("market","epoch(uint256,uint256)",("uint256","uint256"),(lid,eid),a.MARKET_EPOCH_FIELDS)
                after(me["evidenceClose"])
                tx(deployer,a.epoch_call("closeEpochEvidence",lid,eid),f"close evidence {eid}")
                s = sci(eid)
                if s["unresolved"]:
                    val = s["unresolved"]
                    alloc = dict(unresolvedAmount=val, providerShare=val//2, consumerShare=val-val//2,
                                 nonce=me["nonce"], expiry=now()+3600)
                    d = t.allocation_digest(md,lid,eid,s["requestHash"],alloc)
                    tx(deployer,a.resolve_residual(lid,eid,alloc,sign(consumer,d),sign(provider,d)),
                       f"bilateral residual {eid}")
                    require(sci(eid)["mask"] == s["mask"] and sci(eid)["unresolved"] == 0, "consent changed history")
            require(accounting() == (4*FEE,0,0,3*FEE//2,8*FEE//5,12*FEE//5,True), "unexpected final accounting")
            for m, senders in (("market",[consumer,provider]),("ledger",[consumer]+selected)):
                for sender in senders:
                    if view(m,"withdrawable(address)",("address",),(sender,))[0]:
                        tx(sender,a.withdraw(m),"withdraw "+m)
            require(view("market","escrowAccounting()",out=("uint256","uint256","bool")) == (0,0,True),
                    "market not cleared")
            require(int(rpc("eth_getBalance",[modules["ledger"],"latest"]),16) == 0, "ledger not cleared")
            print("ISOLATED_V4_CONTRACT_LIFECYCLE_PASSED=true",flush=True)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--foundry-bin",type=Path,required=True)
    p.add_argument("--log-dir",type=Path,required=True)
    p.add_argument("--port",type=int,default=38545)
    args = p.parse_args()
    run(args.foundry_bin.resolve(),args.log_dir,args.port)


if __name__ == "__main__":
    main()
