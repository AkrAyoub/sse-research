#!/usr/bin/env python3
"""Read-only public SSE contract wiring check on our research chain 31339.

Source SHA, constructor-address binding, positive monitor bond, mandatory
delayed-block entropy and code existence are observed. This does NOT prove
sufficient entropy, monitor independence, real service delivery, external
validator admission, or source-code/bytecode equivalence (requires build
artifact deployment attestation). No signing or transactions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys

from Crypto.Hash import keccak
from sse_pos_devnet_health import safe_url,HealthError,_request,CHAIN

ADDR=re.compile(r"0x[0-9a-fA-F]{40}\Z")
SHA=re.compile(r"[0-9a-f]{40}\Z")

class AttestError(ValueError):
    pass


def _selector(signature:str)->str:
    h=keccak.new(digest_bits=256)
    h.update(signature.encode())
    return "0x"+h.digest()[:4].hex()


def _address_from(raw):
    if (type(raw) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{64}\Z",raw)
            or int(raw,16)==0):
        raise AttestError("invalid ABI-encoded contract address")
    return "0x"+raw[-40:].lower()


def attest(*,rpc_url:str,committee:str,settlement:str,board:str,
           expected_sha:str,call=None)->dict:
    rpc_url=safe_url(rpc_url)
    args=(committee,settlement,board)
    if (type(expected_sha) is not str or not SHA.fullmatch(expected_sha)
            or any(type(addr) is not str or not ADDR.fullmatch(addr)
                   or int(addr,16)==0 for addr in args)
            or len(set(x.lower() for x in args))!=3):
        raise AttestError("three distinct valid contract addresses and source SHA required")
    call=call or (lambda method,params:_request(rpc_url,method,params))
    if call("eth_chainId",[])!=hex(CHAIN):
        raise AttestError("wrong chain, must be SSE independent PoS 31339")
    codes={}
    for kind,addr in zip(("committee","settlement","board"),args):
        code=call("eth_getCode",[addr,"latest"])
        if (type(code) is not str or not re.fullmatch(r"0x[0-9a-fA-F]+\Z",code)
                or len(code)<=2 or int(code,16)==0):
            raise AttestError("expected on-chain contract missing: "+kind)
        codes[kind]=hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()
    def read(address,signature):
        raw=call("eth_call",[{"to":address,"data":_selector(signature)},"latest"])
        if type(raw) is not str:
            raise AttestError("invalid eth_call data")
        return raw
    if _address_from(read(committee,"settlement()"))!=settlement.lower():
        raise AttestError("monitor pool bound to wrong settlement")
    if _address_from(read(settlement,"committeePool()"))!=committee.lower():
        raise AttestError("settlement bound to wrong committee")
    if _address_from(read(settlement,"resourceBoard()"))!=board.lower():
        raise AttestError("settlement bound to wrong board")
    if _address_from(read(board,"approvedSettlement()"))!=settlement.lower():
        raise AttestError("resource board bound to wrong settlement")
    mode=read(committee,"delayedBlockEntropyEnabled()")
    if (type(mode) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{64}\Z",mode)
            or int(mode,16)!=1):
        raise AttestError("owner may still provide arbitrary randomness")
    minbond=read(committee,"minimumBond()")
    if (type(minbond) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{64}\Z",minbond)
            or int(minbond,16)<=0):
        raise AttestError("monitor participation lacks positive bond")
    global_mode=read(committee,"globalMerkleElectionEnabled()")
    batched_mode=read(committee,"globalBatchedRecoveryEnabled()")
    if (any(type(v) is not str or not re.fullmatch(
            r"0x[0-9a-fA-F]{64}\Z",v) or int(v,16) not in (0,1)
            for v in (global_mode,batched_mode))):
        raise AttestError("invalid global election or batched-recovery mode")
    if global_mode!=batched_mode:
        raise AttestError("global Merkle election and batched recovery not paired")
    return {
        "schema":"SSE_OWN_POS_CONTRACT_WIRING_OBSERVED_V1",
        "chainId":CHAIN,
        "gitCommitClaim":expected_sha,
        "onChainBytecodeSha256":codes,
        "committee":committee.lower(),
        "settlement":settlement.lower(),
        "resourceBoard":board.lower(),
        "minimumMonitorBondTestWei":int(minbond,16),
        "delayedBlockEntropyEnabled":True,
        "globalMerkleElectionEnabled":bool(int(global_mode,16)),
        "globalBatchedRecoveryEnabled":bool(int(batched_mode,16)),
        "bindingsVerified":True,
        "sourceBytecodeEquivalenceVerified":False,
        "contractAdministratorRoleGrantRequired":False,
        "consensusValidatorStakingVerified":False,
        "physicalSLAExecutionVerified":False,
        "EthereumMainnetUsed":False,
        "ethereumTransactionsSent":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Read-only SSE PoS chain31339 contract link attestation")
    p.add_argument("--rpc-url",required=True)
    p.add_argument("--committee",required=True)
    p.add_argument("--settlement",required=True)
    p.add_argument("--board",required=True)
    p.add_argument("--source-commit",required=True)
    a=p.parse_args(argv)
    try:
        result=attest(rpc_url=a.rpc_url,committee=a.committee,
                      settlement=a.settlement,board=a.board,
                      expected_sha=a.source_commit)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (HealthError,AttestError,TypeError,OSError,ValueError) as exc:
        print("SSE_POS_CONTRACT_ATTEST_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
