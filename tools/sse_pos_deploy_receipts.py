#!/usr/bin/env python3
"""R17 read-only on-chain proof of the real SSE PoS deployment.

7 *actual* VM4705 deployment tx hashes are independently checked against
the live Besu JSON-RPC, the recorded original genesis, the deploying
faucet address, exact zero-based nonces, canonical block hashes, and
all three mutually wired contract addresses. Beacon finality is
separate from a finalized-execution-block check: do not conflate
receipt inclusion with settlement finality.

No keystore/decrypted private key, mnemonics, signing, broadcast, Docker
or Kurtosis mutations. The upstream boot validator keys were exposed;
this is ONLY a disposable, isolated, unvalued test ETH chain.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from Crypto.Hash import keccak
from sse_pos_devnet_health import CHAIN, HealthError, observe, safe_url, _request
from sse_pos_contract_attest import attest, AttestError

SOURCE_COMMIT="cd2fe67e3031d4f25c41bfc714c6539b7ca1ebef"
GENESIS="0x2aab680cd1b5fe856566eb81eae181b8f15b0cdfb6bdd218180f793371df97f5"
FAUCET="0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7"
COMMITTEE="0x9965bAC16C5Df538df0373a906e42eA0E0C327d9"
SETTLEMENT="0x879878f7561F5a0a1f6dd22348FfdE81cD5fEe7F"
BOARD="0xF1147CA8aC9e28F845529A6Ae5837873806C7788"
# (name, hash, block, deployed_target, direct_call_to, selector_signature,
#  address_arg), where only a creation tx has deployed_target non-None.
STEPS=(
 ("deployCommittee","0xb3d144f1a627ccd7ee46b30fb814fea6ee720263d302d4dfe2fbc62efc010294",953,COMMITTEE,None,None,None),
 ("enableDelayedEntropy","0x9489d36d0cdb8688f23cb859144e7643aab62e7d68e521785d5d343425c2308e",954,None,COMMITTEE,"enableDelayedBlockEntropy()",None),
 ("deploySettlement","0x39d6879d3a099bd1923df7336d9c3cb5fa247ea4ee204ba57fcc93d533c497af",955,SETTLEMENT,None,None,None),
 ("deployBoard","0x832b21b4d84581e6c8ca35e60117feb8354d20a0d5716b033fa598705dbba00d",956,BOARD,None,None,None),
 ("bindCommitteeSettlement","0xcbb5bd988a7ec719624ba03eec9d166231980ac2bf2a6afb4fa57c7600c9ac78",957,None,COMMITTEE,"bindSettlement(address)",SETTLEMENT),
 ("bindSettlementBoard","0x9f94a3b4ecef4dcaa27612e045342bd1dba81db4be69ce0571cac24129404ded",958,None,SETTLEMENT,"bindResourceBoard(address)",BOARD),
 ("bindBoardSettlement","0xfe316af856b79694c58b4a3fb1195da1eb979a7c2ea04f33e81063a99786a468",959,None,BOARD,"bindSettlement(address)",SETTLEMENT),
)
HASH=re.compile(r"0x[0-9a-fA-F]{64}\Z")
SHA=re.compile(r"[0-9a-f]{40}\Z")


class DeploymentAuditError(ValueError):
    pass


def _to_hex_hash(x):
    if type(x) is not str or not HASH.fullmatch(x):
        raise DeploymentAuditError("missing or malformed block/transaction hash")
    return x.lower()


def _hex_num(x):
    if type(x) is not str or not re.fullmatch(r"0x[0-9a-fA-F]+\Z",x):
        raise DeploymentAuditError("bad nonnegative quantity")
    return int(x,16)


def _selector(sig):
    h=keccak.new(digest_bits=256)
    h.update(sig.encode("ascii"))
    return "0x"+h.digest()[:4].hex()


def audit(*,rpc_url:str,beacon_url:str,require_tx_finality:bool=False,
          rpc=None,health=None,attestation=None,beacon_get=None)->dict:
    if type(require_tx_finality) is not bool:
        raise DeploymentAuditError("invalid finality policy")
    rpc_url=safe_url(rpc_url)
    beacon_url=safe_url(beacon_url)
    actual_rpc=rpc is None
    rpc=rpc or (lambda method,params:_request(rpc_url,method,params))
    health=health or observe(
        execution_url=rpc_url,beacon_url=beacon_url,
        expected_genesis=GENESIS,require_finality=True,
    )
    if (type(health) is not dict
            or health.get("chainId")!=CHAIN
            or health.get("executionGenesisHash")!=GENESIS
            or health.get("executionGenesisPinned") is not True
            or health.get("finalityObserved") is not True):
        raise DeploymentAuditError("not the observed original finalized SSE PoS chain")
    if rpc("eth_chainId",[])!=hex(CHAIN):
        raise DeploymentAuditError("wrong execution RPC chain")
    genesis=rpc("eth_getBlockByNumber",["0x0",False])
    if type(genesis) is not dict or _to_hex_hash(genesis.get("hash"))!=GENESIS:
        raise DeploymentAuditError("execution genesis mismatch")

    records=[]
    total_gas=0
    for nonce,(kind,txid,height,created,to,signature,argument) in enumerate(STEPS):
        receipt=rpc("eth_getTransactionReceipt",[txid])
        transaction=rpc("eth_getTransactionByHash",[txid])
        canonical=rpc("eth_getBlockByNumber",[hex(height),False])
        if any(type(x) is not dict for x in (receipt,transaction,canonical)):
            raise DeploymentAuditError(kind+": absent on-chain transaction/block")
        b_hash=_to_hex_hash(receipt.get("blockHash"))
        if (_to_hex_hash(canonical.get("hash"))!=b_hash
                or _to_hex_hash(transaction.get("hash"))!=txid.lower()
                or _to_hex_hash(receipt.get("transactionHash"))!=txid.lower()):
            raise DeploymentAuditError(kind+": transaction no longer in canonical chain")
        if (receipt.get("status")!="0x1"
                or _hex_num(receipt.get("blockNumber"))!=height
                or _hex_num(transaction.get("blockNumber"))!=height
                or _hex_num(transaction.get("nonce"))!=nonce
                or _hex_num(transaction.get("value"))!=0
                or type(transaction.get("from")) is not str
                or transaction["from"].lower()!=FAUCET.lower()
                or _hex_num(receipt.get("gasUsed"))<21000):
            raise DeploymentAuditError(kind+": receipt, sender, nonce, status or value incorrect")
        if "chainId" in transaction and _hex_num(transaction["chainId"])!=CHAIN:
            raise DeploymentAuditError(kind+": wrong EIP-155 signer chain")
        to_actual=transaction.get("to")
        deployed=receipt.get("contractAddress")
        if created:
            if (to_actual is not None or type(deployed) is not str
                    or deployed.lower()!=created.lower()):
                raise DeploymentAuditError(kind+": wrong deployed contract address")
        else:
            if (type(to_actual) is not str or to_actual.lower()!=to.lower()
                    or deployed is not None):
                raise DeploymentAuditError(kind+": wrong contract call target")
            payload=transaction.get("input")
            if type(payload) is not str or not payload.lower().startswith(_selector(signature)):
                raise DeploymentAuditError(kind+": unexpected executable method")
            if argument is None:
                if len(payload)!=10:
                    raise DeploymentAuditError(kind+": malformed argument-free calldata")
            else:
                if (len(payload)!=74 or
                        payload[10:34].lower()!="0"*24 or
                        payload[-40:].lower()!=argument.lower()[2:]):
                    raise DeploymentAuditError(kind+": wrong binding argument")
        gas=_hex_num(receipt["gasUsed"])
        total_gas+=gas
        records.append({
            "step":kind,"transactionHash":txid,
            "block":height,"gasUsed":gas,
            "receiptSuccessful":True,"canonicalBlockVerified":True,
        })
    if total_gas!=10_947_092:
        raise DeploymentAuditError("recorded seven-transaction gas total changed")

    result=attestation or attest(
        rpc_url=rpc_url,committee=COMMITTEE,settlement=SETTLEMENT,
        board=BOARD,expected_sha=SOURCE_COMMIT,
    )
    if (type(result) is not dict or result.get("bindingsVerified") is not True
            or result.get("delayedBlockEntropyEnabled") is not True
            or result.get("globalMerkleElectionEnabled") is not False
            or result.get("globalBatchedRecoveryEnabled") is not False
            or result.get("chainId")!=CHAIN):
        raise DeploymentAuditError("live contract binding attestation failed")

    finalized_height=None
    # An execution 'finalized' tag is needed to prove deployment TXs
    # finalized, not just some earlier consensus epoch.
    try:
        block=rpc("eth_getBlockByNumber",["finalized",False])
        if type(block) is dict:
            finalized_height=_hex_num(block.get("number"))
    except (HealthError,DeploymentAuditError,ValueError,TypeError):
        # This EL RPC may not expose the 'finalized' tag. In that case
        # we REFUSE to claim that the seven txs were finalized.
        pass
    tx_finalized=finalized_height is not None and finalized_height>=STEPS[-1][2]
    finality_source="execution_finalized_tag" if tx_finalized else None
    beacon_finalized_execution_block=None
    beacon_payload_verified=False
    # Besu can lag (or not implement) the EL JSON-RPC 'finalized'
    # block tag. Lighthouse's FINALIZED non-optimistic Beacon BLOCK
    # carries a canonical execution payload; independently cross-check
    # its block number AND block hash against Besu. This is stronger
    # than merely observing some earlier Beacon finalized epoch.
    # Mocked RPC callers do not make unexpected real network requests:
    # they must provide a beacon_get callback to exercise this branch.
    if not tx_finalized and (beacon_get is not None or actual_rpc):
        try:
            payload_response=(
                beacon_get("/eth/v2/beacon/blocks/finalized")
                if beacon_get is not None
                else _request(beacon_url+"/eth/v2/beacon/blocks/finalized")
            )
            if (type(payload_response) is dict
                    and payload_response.get("finalized") is True
                    and payload_response.get("execution_optimistic") is False):
                data=payload_response.get("data")
                message=data.get("message") if type(data) is dict else None
                body=message.get("body") if type(message) is dict else None
                payload=body.get("execution_payload") if type(body) is dict else None
                if type(payload) is dict:
                    block_number=payload.get("block_number")
                    execution_hash=payload.get("block_hash")
                    if (type(block_number) is str and block_number.isdecimal()
                            and type(execution_hash) is str
                            and HASH.fullmatch(execution_hash)):
                        n=int(block_number)
                        execution_block=rpc("eth_getBlockByNumber",[hex(n),False])
                        if (type(execution_block) is dict
                                and _to_hex_hash(execution_block.get("hash"))
                                ==execution_hash.lower()):
                            beacon_finalized_execution_block=n
                            beacon_payload_verified=True
                            if n>=STEPS[-1][2]:
                                tx_finalized=True
                                finality_source="beacon_finalized_execution_payload"
        except (HealthError,DeploymentAuditError,ValueError,TypeError,OSError):
            # Unavailable/malformed Beacon payload: do not mark TX
            # finality proved on a mere finalized epoch header.
            pass
    if require_tx_finality and not tx_finalized:
        raise DeploymentAuditError(
            "deployment receipts canonical but tx finality not yet proven by EL tag "
            "or cross-checked finalized Beacon execution payload"
        )
    return {
        "schema":"SSE_R17_LIVE_POS_DEPLOYMENT_RECEIPTS_V1",
        "chainId":CHAIN,"executionGenesisHash":GENESIS,
        "beaconFinalityObserved":True,
        "deploymentTxFinalityProved":tx_finalized,
        "deploymentTxFinalityEvidenceSource":finality_source,
        "finalizedExecutionBlock":finalized_height,
        "beaconFinalizedExecutionBlock":beacon_finalized_execution_block,
        "beaconFinalizedExecutionPayloadMatchedCanonicalEL":beacon_payload_verified,
        "sourceGitCommitAtOriginalDeployment":SOURCE_COMMIT,
        "sourceBytecodeEquivalenceVerified":False,
        "faucetPublicAddress":FAUCET,"committee":COMMITTEE,
        "settlement":SETTLEMENT,"resourceBoard":BOARD,
        "receiptCount":len(records),"totalGasUsed":total_gas,
        "sevenReceiptsCanonicalAndSuccessful":True,
        "wiringVerifiedOnChain":True,
        "transactions":records,
        "privateKeyOrMnemonicLoaded":False,
        "realEthereumSpent":False,
        "publicValidatorAdmissionVerified":False,
        "firstBootstrapValidatorKeysTainted":True,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Strict read-only audit of VM4705 SSE PoS deployment")
    p.add_argument("--rpc-url",required=True)
    p.add_argument("--beacon-url",required=True)
    p.add_argument("--require-tx-finality",action="store_true")
    args=p.parse_args(argv)
    try:
        result=audit(rpc_url=args.rpc_url,beacon_url=args.beacon_url,
                     require_tx_finality=args.require_tx_finality)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (HealthError,AttestError,DeploymentAuditError,OSError,ValueError,TypeError) as exc:
        print("SSE_R17_DEPLOYMENT_AUDIT_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
