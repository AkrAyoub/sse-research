#!/usr/bin/env python3
"""R18: fund and bond independent SSE EOA role keys on LIVE private PoS31339.

A SAFE, separate-wallet transition from verified SSE contract deployment
toward a real on-chain marketplace lease. No unlocked eth_accounts,
Anvil, VM snapshots, old R11 validator genesis, Tailscale, seed output,
secret CLI args, GitHub Actions, or public-chain transactions.

Read-only --plan does NOT require passwords. --fund and --register use
owner-only encrypted eth_account keystores; passwords are prompted
INTERACTIVELY and never printed, stored, or passed in process arguments.
All 7 role wallets must exist. The first launch validator mnemonic was
exposed, so this is ONLY a deliberately isolated lab chain.

This tool intentionally stops before lease creation. A separate live
marketplace runner must record actual receipt provenance, deadlines,
human/agent service evidence, and independent EIP-712 monitor votes.
"""
from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

from Crypto.Hash import keccak
from eth_utils import to_checksum_address
from sse_pos_devnet_health import CHAIN, HealthError, safe_url, _request
from sse_pos_contract_attest import attest, AttestError
from sse_pos_deploy_receipts import FAUCET, GENESIS, COMMITTEE, SETTLEMENT, BOARD, SOURCE_COMMIT

ROLES=("consumer","provider","monitor01","monitor02","monitor03","monitor04","monitor05")
MONITORS=ROLES[2:]
FUND_WEI={
    "consumer":10**18,
    "provider":10**18,
    **{r:10**17 for r in MONITORS},
}
EXPECTED_MIN_BOND=10**15
HASH=re.compile(r"0x[0-9a-fA-F]{64}\Z")
ADDRESS=re.compile(r"(?:0x)?[0-9a-fA-F]{40}\Z")
HEXQ=re.compile(r"0x[0-9a-fA-F]+\Z")
GAS_PRICE_CAP=5_000_000_000
GAS_LIMIT_CAP=2_000_000


class RoleError(ValueError):
    pass


def _quantity(x):
    if type(x) is not str or not HEXQ.fullmatch(x):
        raise RoleError("invalid chain quantity")
    return int(x,16)


def _owner_file(p:Path)->None:
    if (p.is_symlink() or not p.is_file() or
        p.stat().st_uid!=os.geteuid() or
        stat.S_IMODE(p.stat().st_mode)!=0o600 or
        not 50<=p.stat().st_size<=16384):
        raise RoleError("encrypted role wallet not owner-only 0600: "+p.name)


def read_wallets(directory:Path)->dict:
    if (os.name!="posix" or os.geteuid()==0 or
        not directory.is_absolute() or not directory.is_dir() or
        directory.is_symlink() or
        directory.stat().st_uid!=os.geteuid() or
        stat.S_IMODE(directory.stat().st_mode)!=0o700):
        raise RoleError("role wallet directory must exist and belong to nonroot owner 0700")
    wallets={}
    for role in ("faucet",)+ROLES:
        p=directory/(role+".keystore.json")
        _owner_file(p)
        try:
            blob=json.loads(p.read_text("utf-8"))
        except (OSError,UnicodeError,ValueError) as exc:
            raise RoleError("encrypted keystore file unreadable: "+role) from exc
        if (type(blob) is not dict or
            not all(k in blob for k in ("crypto","version","address")) and
            not all(k in blob for k in ("Crypto","version","address"))):
            raise RoleError("not an encrypted Ethereum keystore: "+role)
        raw_address=blob["address"]
        if type(raw_address) is not str or not ADDRESS.fullmatch(raw_address):
            raise RoleError("encrypted wallet has bad public address: "+role)
        addr="0x"+raw_address.removeprefix("0x").lower()
        wallets[role]={"address":addr,"path":p}
    if wallets["faucet"]["address"]!=FAUCET.lower():
        raise RoleError("wrong genesis-funded faucet keystore")
    if len(set(x["address"] for x in wallets.values()))!=len(wallets):
        raise RoleError("roles must have distinct EOA keys")
    if any(w["address"] in (COMMITTEE.lower(),SETTLEMENT.lower(),BOARD.lower())
           for w in wallets.values()):
        raise RoleError("contract address was supplied as an EOA")
    return wallets


def _selector(signature:str)->str:
    h=keccak.new(digest_bits=256)
    h.update(signature.encode("ascii"))
    return "0x"+h.digest()[:4].hex()


def _word(value:str)->str:
    if type(value) is not str or not ADDRESS.fullmatch(value):
        raise RoleError("invalid public address")
    return value.removeprefix("0x").lower().rjust(64,"0")


def _candidate(rpc,addr):
    raw=rpc("eth_call",[{"to":COMMITTEE,
                         "data":_selector("candidates(address)")+_word(addr)},"latest"])
    if type(raw) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{384}\Z",raw):
        raise RoleError("malformed on-chain candidate struct")
    w=[int(raw[2+i*64:2+(i+1)*64],16) for i in range(6)]
    if w[4] not in (0,1) or w[5] not in (0,1):
        raise RoleError("malformed on-chain candidate flags")
    return {"bondWei":w[0],"pendingSelections":w[2],
            "activeAssignments":w[3],"active":bool(w[4]),
            "everRegistered":bool(w[5])}


def _attest(rpc_url):
    evidence=attest(rpc_url=rpc_url,committee=COMMITTEE,
                    settlement=SETTLEMENT,board=BOARD,
                    expected_sha=SOURCE_COMMIT)
    if (not evidence.get("bindingsVerified") or
        not evidence.get("delayedBlockEntropyEnabled") or
        evidence.get("globalMerkleElectionEnabled") or
        evidence.get("globalBatchedRecoveryEnabled")):
        raise RoleError("SSE actual deployment is not the reviewed R16 baseline")


def chain_check(rpc, rpc_url:str,*,verify_attestation=True):
    if rpc("eth_chainId",[])!=hex(CHAIN):
        raise RoleError("must operate ONLY on own PoS chain31339")
    genesis=rpc("eth_getBlockByNumber",["0x0",False])
    if (type(genesis) is not dict or
        type(genesis.get("hash")) is not str or
        genesis["hash"].lower()!=GENESIS):
        raise RoleError("execution genesis differs: no wallet action permitted")
    if verify_attestation:
        _attest(rpc_url)
    bond=_quantity(rpc("eth_call",[{"to":COMMITTEE,
                          "data":_selector("minimumBond()")},"latest"]))
    if bond!=EXPECTED_MIN_BOND:
        raise RoleError("actual on-chain minimum monitor bond differs from intended")
    return bond


def observe_roles(rpc_url:str,wallet_dir:Path,*,rpc=None,verify_attestation=True):
    rpc_url=safe_url(rpc_url)
    rpc=rpc or (lambda method,params:_request(rpc_url,method,params))
    wallets=read_wallets(wallet_dir)
    bond=chain_check(rpc,rpc_url,verify_attestation=verify_attestation)
    observed={}
    for role in ("faucet",)+ROLES:
        addr=wallets[role]["address"]
        balance=_quantity(rpc("eth_getBalance",[addr,"latest"]))
        record={"address":addr,"balanceWei":balance}
        if role in MONITORS:
            record.update(_candidate(rpc,addr))
        observed[role]=record
    count=_quantity(rpc("eth_call",[{"to":COMMITTEE,
                         "data":_selector("candidateCount()")},"latest"]))
    return {
        "schema":"SSE_R18_TEST_ETH_ROLES_OBSERVED_V1",
        "chainId":CHAIN,
        "genesisHash":GENESIS,
        "liveCommitteeAddress":COMMITTEE,
        "liveSettlementAddress":SETTLEMENT,
        "liveResourceBoardAddress":BOARD,
        "faucet":observed["faucet"],
        "roles":{r:observed[r] for r in ROLES},
        "fundingAmountsWei":FUND_WEI,
        "minimumMonitorBondWei":bond,
        "registeredActiveCandidateCount":count,
        "allFiveDemoMonitorsRegistered":all(
            observed[r]["active"] and observed[r]["bondWei"]>=bond for r in MONITORS
        ),
        "stakeConsensusValidatorKeysUsed":False,
        "privateKeysOrPasswordsPrinted":False,
        "realEthereumUsed":False,
        "transactionsSentByObservation":False,
        "externalSLAEvidenceProved":False,
        "externalValidatorP2PAdmissionProved":False,
    }


def _unlock(role,wallet):
    try:
        from eth_account import Account
    except ImportError as exc:
        raise RoleError("eth-account==0.14.0 required") from exc
    password=getpass("Encryption password for "+role+" (never printed): ")
    if not password:
        raise RoleError("empty encryption password")
    try:
        secret=Account.decrypt(wallet["path"].read_text("utf-8"),password)
        acc=Account.from_key(secret)
    except (ValueError,KeyError) as exc:
        raise RoleError("cannot decrypt encrypted wallet: "+role) from exc
    del password
    if acc.address.lower()!=wallet["address"]:
        raise RoleError("keystore public address mismatch after decryption")
    return acc


def _send(rpc,account,to:str,value:int,data:str="0x")->dict:
    if (type(value) is not int or value<0 or
        type(to) is not str or not ADDRESS.fullmatch(to) or
        type(data) is not str or not re.fullmatch(r"0x[0-9a-fA-F]*\Z",data) or
        len(data)%2):
        raise RoleError("invalid bounded transfer/call")
    nonce=_quantity(rpc("eth_getTransactionCount",[account.address,"pending"]))
    balance=_quantity(rpc("eth_getBalance",[account.address,"pending"]))
    price=_quantity(rpc("eth_gasPrice",[]))
    latest=rpc("eth_getBlockByNumber",["latest",False])
    if type(latest) is not dict or latest.get("baseFeePerGas") is None:
        raise RoleError("an EIP-1559 execution block is required")
    base=_quantity(latest["baseFeePerGas"])
    tip=max(1,price//8)
    maxfee=max(price*2,base*2+tip)
    if maxfee>GAS_PRICE_CAP or tip>GAS_PRICE_CAP:
        raise RoleError("gas price exceeds isolated-test-chain cost ceiling")
    transaction={
        "chainId":CHAIN,
        "type":2,
        # eth-account rejects lower-case recipient hex addresses unless
        # they happen to match EIP-55 checksum. Wallet inventory deliberately
        # normalizes addresses to lower-case; checksum them ONLY at the
        # signing boundary (same treatment for faucet and register() calls).
        "to":to_checksum_address("0x"+to.removeprefix("0x")),
        "value":value,"data":data,
        "nonce":nonce,
        "maxFeePerGas":maxfee,
        "maxPriorityFeePerGas":tip,
    }
    estimate=_quantity(rpc("eth_estimateGas",[{
        "from":account.address, "to":transaction["to"],
        "value":hex(value),"data":data
    }]))
    if not 21000<=estimate<=GAS_LIMIT_CAP:
        raise RoleError("gas estimate outside safe bounded limits")
    limit=min(GAS_LIMIT_CAP,max(21000,(estimate*125+99)//100))
    if balance<value+limit*maxfee:
        raise RoleError("insufficient funder test ETH plus bounded gas fee")
    transaction["gas"]=limit
    signed=account.sign_transaction(transaction)
    txid="0x"+signed.hash.hex().removeprefix("0x")
    raw="0x"+signed.raw_transaction.hex().removeprefix("0x")
    print("SSE_R18_SIGNED_TX_HASH="+txid,flush=True)
    # If this RPC errors/times out AFTER submission, the transaction
    # may still be included. NEVER automatically resend or change nonce.
    try:
        submitted=rpc("eth_sendRawTransaction",[raw])
    except (HealthError,ValueError,OSError) as exc:
        raise RoleError("uncertain broadcast; check hash "+txid+
                        " on-chain before any retry") from exc
    if type(submitted) is not str or submitted.lower()!=txid.lower():
        raise RoleError("RPC returned unexpected signed hash; inspect on-chain "+txid)
    receipt=None
    for _ in range(90):
        receipt=rpc("eth_getTransactionReceipt",[txid])
        if receipt is not None:
            break
        time.sleep(1)
    if type(receipt) is not dict:
        raise RoleError("pending inclusion, inspect "+txid+" before retry")
    if receipt.get("status")!="0x1":
        raise RoleError("transaction failed, inspect "+txid)
    if (type(receipt.get("transactionHash")) is not str or
        receipt["transactionHash"].lower()!=txid.lower()):
        raise RoleError("receipt hash mismatch "+txid)
    return {
        "transactionHash":txid,
        "blockNumber":_quantity(receipt["blockNumber"]),
        "gasUsed":_quantity(receipt["gasUsed"]),
        "from":account.address,
        "to":transaction["to"],
        "valueWei":value,
        "receiptSuccessful":True,
    }


def _confirm(action:str):
    expected="EXECUTE "+action+" ON 31339"
    answer=input("Type "+expected+" to submit REAL PoS test-ETH txs: ").strip()
    if answer!=expected:
        raise RoleError("operator did not explicitly confirm phase")


def execute_funding(rpc_url,wallet_dir,*,rpc=None,signer=None,confirm=True):
    rpc_url=safe_url(rpc_url)
    rpc=rpc or (lambda method,params:_request(rpc_url,method,params))
    observed=observe_roles(rpc_url,wallet_dir,rpc=rpc)
    if confirm:_confirm("FUND")
    wallets=read_wallets(wallet_dir)
    if any(observed["roles"][r]["balanceWei"]!=0 and
           observed["roles"][r]["balanceWei"]<FUND_WEI[r]//2 for r in ROLES):
        raise RoleError("partially funded role needs manual investigation; no automatic refill")
    jobs=[r for r in ROLES if observed["roles"][r]["balanceWei"]==0]
    if not jobs:
        return {"phase":"fund","transactions":[],"rolesAlreadyFunded":list(ROLES)}
    faucet=(signer or _unlock)("faucet",wallets["faucet"])
    results=[]
    for role in jobs:
        # Every funded address is a verified, locally generated encrypted
        # EOA; no user-provided arbitrary destination is accepted.
        tx=_send(rpc,faucet,wallets[role]["address"],FUND_WEI[role])
        results.append({"role":role,**tx})
    return {"phase":"fund","transactions":results,
            "transactionCount":len(results),"privateKeysPrinted":False}


def execute_registration(rpc_url,wallet_dir,*,rpc=None,signer=None,confirm=True):
    rpc_url=safe_url(rpc_url)
    rpc=rpc or (lambda method,params:_request(rpc_url,method,params))
    observed=observe_roles(rpc_url,wallet_dir,rpc=rpc)
    wallets=read_wallets(wallet_dir)
    if confirm:_confirm("REGISTER")
    bond=observed["minimumMonitorBondWei"]
    jobs=[]
    for role in MONITORS:
        state=observed["roles"][role]
        if state["active"] and state["bondWei"]>=bond:
            continue
        if state["bondWei"]!=0 or state["everRegistered"]:
            raise RoleError("non-new monitor state; refusing uncertain re-registration: "+role)
        if state["balanceWei"]<2*bond:
            raise RoleError("monitor lacks test-ETH bond and gas funding: "+role)
        jobs.append(role)
    results=[]
    for role in jobs:
        account=(signer or _unlock)(role,wallets[role])
        tx=_send(rpc,account,COMMITTEE,bond,_selector("register()"))
        results.append({"role":role,**tx})
    return {"phase":"register","transactions":results,
            "transactionCount":len(results),"minimumBondWei":bond,
            "privateKeysPrinted":False}


def main(argv=None):
    p=argparse.ArgumentParser(description="Live isolated PoS testETH role funding and bonding, no secret logs")
    p.add_argument("--rpc-url",required=True)
    p.add_argument("--wallet-dir",type=Path,required=True)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--plan",action="store_true")
    modes.add_argument("--fund",action="store_true")
    modes.add_argument("--register",action="store_true")
    args=p.parse_args(argv)
    try:
        if args.plan:
            result=observe_roles(args.rpc_url,args.wallet_dir)
        elif args.fund:
            result=execute_funding(args.rpc_url,args.wallet_dir)
        else:
            result=execute_registration(args.rpc_url,args.wallet_dir)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (RoleError,HealthError,AttestError,OSError,
            ValueError,TypeError,KeyError) as exc:
        print("SSE_R18_LIVE_ROLES_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
