"""R17 read-only receipt provenance for the REAL seven chain31339 SSE txs."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_pos_deploy_receipts import (
    audit,STEPS,SOURCE_COMMIT,FAUCET,GENESIS,COMMITTEE,
    SETTLEMENT,BOARD,DeploymentAuditError,_selector
)

GAS=(4965328,46707,4904459,883585,48000,48042,50971)
RPC="http://127.0.0.1:32770"
BEACON="http://127.0.0.1:32774"


def health():
    return {
        "chainId":31339,
        "executionGenesisHash":GENESIS,
        "executionGenesisPinned":True,
        "finalityObserved":True,
    }


def binding():
    return {
        "chainId":31339,"bindingsVerified":True,
        "delayedBlockEntropyEnabled":True,
        "globalMerkleElectionEnabled":False,
        "globalBatchedRecoveryEnabled":False,
    }


def fixtures():
    txs,receipts,blocks={}, {}, {}
    for i,(kind,txid,height,created,to,signature,argument) in enumerate(STEPS):
        bh="0x"+f"{height:064x}"
        payload="0x1234" if created else _selector(signature)
        if argument:
            payload+="0"*24+argument[2:].lower()
        txs[txid]={
            "hash":txid, "blockNumber":hex(height),
            "nonce":hex(i),"value":"0x0",
            "chainId":hex(31339),"from":FAUCET,"to":to,
            "input":payload,
        }
        receipts[txid]={
            "status":"0x1","blockNumber":hex(height),
            "blockHash":bh,"transactionHash":txid,
            "contractAddress":created,"gasUsed":hex(GAS[i]),
        }
        blocks[hex(height)]={"hash":bh,"number":hex(height)}
    blocks["0x0"]={"hash":GENESIS}
    blocks["finalized"]={"hash":"0x"+"ff"*32,"number":hex(970)}
    def rpc(method,params):
        if method=="eth_chainId":return hex(31339)
        if method=="eth_getTransactionReceipt":return receipts.get(params[0])
        if method=="eth_getTransactionByHash":return txs.get(params[0])
        if method=="eth_getBlockByNumber":return blocks.get(params[0])
        raise AssertionError("unexpected read-only RPC method "+method)
    return rpc,txs,receipts,blocks


class R17ReceiptsTests(unittest.TestCase):
    def call(self,rpc,**options):
        return audit(rpc_url=RPC,beacon_url=BEACON,
                     rpc=rpc,health=health(),attestation=binding(),
                     **options)

    def test_actual_observed_seven_transactions_have_correct_provenance(self):
        rpc,_,_,_=fixtures()
        record=self.call(rpc,require_tx_finality=True)
        self.assertTrue(record["wiringVerifiedOnChain"])
        self.assertTrue(record["sevenReceiptsCanonicalAndSuccessful"])
        self.assertTrue(record["deploymentTxFinalityProved"])
        self.assertEqual(record["receiptCount"],7)
        self.assertEqual(record["totalGasUsed"],10947092)
        self.assertEqual(record["finalizedExecutionBlock"],970)
        self.assertEqual(record["sourceGitCommitAtOriginalDeployment"],SOURCE_COMMIT)
        self.assertFalse(record["privateKeyOrMnemonicLoaded"])
        self.assertFalse(record["publicValidatorAdmissionVerified"])
        self.assertEqual([t["block"] for t in record["transactions"]],
                         list(range(953,960)))

    def test_tamper_any_nonce_or_receipt_or_target_fails_closed(self):
        for field,bad in (("nonce","0x21"),("from","0x"+"12"*20),
                          ("value","0x1"),("to","0x"+"13"*20),
                          ("chainId","0x1")):
            rpc,txs,_,_=fixtures()
            txs[STEPS[4][1]][field]=bad
            with self.subTest(field=field),self.assertRaises(DeploymentAuditError):
                self.call(rpc)
        rpc,_,receipt,_=fixtures()
        receipt[STEPS[2][1]]["status"]="0x0"
        with self.assertRaises(DeploymentAuditError):
            self.call(rpc)

    def test_noncanonical_or_wrong_selector_or_argument_refused(self):
        rpc,txs,receipts,blocks=fixtures()
        txs[STEPS[4][1]]["input"]=_selector("enableGlobalMerkleElection()")
        with self.assertRaises(DeploymentAuditError):
            self.call(rpc)
        rpc,txs,receipts,blocks=fixtures()
        txs[STEPS[4][1]]["input"]=_selector("bindSettlement(address)")+"0"*24+FAUCET[2:].lower()
        with self.assertRaises(DeploymentAuditError):
            self.call(rpc)
        rpc,txs,receipts,blocks=fixtures()
        blocks[hex(953)]["hash"]="0x"+"88"*32
        with self.assertRaises(DeploymentAuditError):
            self.call(rpc)

    def test_receipt_inclusion_not_equal_to_finality(self):
        rpc,txs,receipts,blocks=fixtures()
        blocks["finalized"]["number"]=hex(958)
        record=self.call(rpc)
        self.assertFalse(record["deploymentTxFinalityProved"])
        with self.assertRaises(DeploymentAuditError):
            self.call(rpc,require_tx_finality=True)

    def test_no_finalized_execution_tag_does_not_invent_finality(self):
        rpc,txs,receipts,blocks=fixtures()
        del blocks["finalized"]
        record=self.call(rpc)
        self.assertIsNone(record["finalizedExecutionBlock"])
        self.assertFalse(record["deploymentTxFinalityProved"])

    def test_finalized_lighthouse_execution_payload_proves_tx_finality(self):
        rpc,txs,receipts,blocks=fixtures()
        blocks["finalized"]["number"]=hex(958)  # EL tag is stale
        final_bh="0x"+"a5"*32
        blocks[hex(975)]={"number":hex(975),"hash":final_bh}
        beacon=lambda path:{
            "finalized":True,"execution_optimistic":False,
            "data":{"message":{"body":{"execution_payload":{
                "block_number":"975","block_hash":final_bh
            }}}},
        }
        record=self.call(rpc,beacon_get=beacon,require_tx_finality=True)
        self.assertTrue(record["deploymentTxFinalityProved"])
        self.assertTrue(record["beaconFinalizedExecutionPayloadMatchedCanonicalEL"])
        self.assertEqual(record["beaconFinalizedExecutionBlock"],975)
        self.assertEqual(record["finalizedExecutionBlock"],958)
        self.assertEqual(record["deploymentTxFinalityEvidenceSource"],
                         "beacon_finalized_execution_payload")

    def test_optimistic_or_noncanonical_beacon_payload_not_finality(self):
        for optimistic,wrong_hash,flag in (
            (True,False,True),(False,True,True),(False,False,False)
        ):
            rpc,txs,receipts,blocks=fixtures()
            blocks["finalized"]["number"]=hex(958)
            final_bh="0x"+"a5"*32
            blocks[hex(975)]={"number":hex(975),"hash":final_bh}
            result_hash="0x"+"b6"*32 if wrong_hash else final_bh
            beacon=lambda path:{
                "finalized":flag,"execution_optimistic":optimistic,
                "data":{"message":{"body":{"execution_payload":{
                    "block_number":"975","block_hash":result_hash
                }}}},
            }
            with self.subTest(optimistic=optimistic,
                              wrong_hash=wrong_hash,flag=flag):
                report=self.call(rpc,beacon_get=beacon)
                self.assertFalse(report["deploymentTxFinalityProved"])
                with self.assertRaises(DeploymentAuditError):
                    self.call(rpc,beacon_get=beacon,
                              require_tx_finality=True)

    def test_wrong_chain_or_bad_contract_binding_rejected(self):
        rpc,txs,receipts,blocks=fixtures()
        with self.assertRaises(DeploymentAuditError):
            audit(rpc_url=RPC,beacon_url=BEACON,
                  rpc=rpc,health={**health(),"executionGenesisHash":"0x"+"11"*32},
                  attestation=binding())
        with self.assertRaises(DeploymentAuditError):
            audit(rpc_url=RPC,beacon_url=BEACON,
                  rpc=rpc,health=health(),
                  attestation={**binding(),"globalMerkleElectionEnabled":True})

if __name__=="__main__":
    unittest.main()
