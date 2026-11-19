"""Own PoS devnet execution and Beacon attestation; no fake role grants."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_pos_devnet_health import observe,HealthError,safe_url
from sse_pos_contract_attest import attest,AttestError,_selector
from sse_pos_test_wallet import plan as wallet_plan, WalletError

GENESIS="0x"+"ab"*32
VALIDATOR="0x"+"cd"*48
POOL="0x"+"11"*20
SETTLEMENT="0x"+"22"*20
BOARD="0x"+"33"*20
SHA="f"*40

def execution(method,params):
    if method=="eth_chainId":return "0x7a6b"
    if method=="eth_getBlockByNumber":return {"hash":GENESIS}
    if method=="eth_blockNumber":return "0x40"
    raise AssertionError(method)

def beacon(path):
    if path=="/eth/v1/beacon/genesis":
        return {"data":{"genesis_time":"1810000000",
                        "genesis_validators_root":"0x"+"ab"*32}}
    if path=="/eth/v1/beacon/headers/head":
        return {"data":{"header":{"message":{"slot":"96"}}}}
    if path=="/eth/v1/beacon/states/head/finality_checkpoints":
        return {"data":{"finalized":{"epoch":"2","root":"0x"+"be"*32}}}
    if path=="/eth/v1/beacon/states/head/validators/"+VALIDATOR:
        return {"data":{"status":"active_ongoing"}}
    raise AssertionError(path)

def on_chain(method,params):
    if method=="eth_chainId":return "0x7a6b"
    if method=="eth_getCode":return "0x60016000f3"
    if method=="eth_call":
        account=params[0]["to"].lower()
        selector=params[0]["data"]
        links={
            (POOL.lower(),_selector("settlement()")):SETTLEMENT,
            (SETTLEMENT.lower(),_selector("committeePool()")):POOL,
            (SETTLEMENT.lower(),_selector("resourceBoard()")):BOARD,
            (BOARD.lower(),_selector("approvedSettlement()")):SETTLEMENT,
        }
        if (account,selector) in links:
            return "0x"+links[(account,selector)][2:].lower().zfill(64)
        if selector==_selector("minimumBond()"):return "0x"+f"{10**15:064x}"
        if selector==_selector("delayedBlockEntropyEnabled()"):return "0x"+f"{1:064x}"
        if selector==_selector("globalMerkleElectionEnabled()"):return "0x"+f"{0:064x}"
    raise AssertionError(method)

class OwnPosEndToEndStaticTests(unittest.TestCase):
    def test_observe_actual_beacon_consensus_not_role_label(self):
        result=observe(execution_url="http://127.0.0.1:32000",
                       beacon_url="http://127.0.0.1:33000",
                       validator_pubkey=VALIDATOR,expected_genesis=GENESIS,
                       require_finality=True,execution_call=execution,
                       beacon_get=beacon)
        self.assertEqual(result["chainId"],31339)
        self.assertEqual(result["executionBlockHeight"],64)
        self.assertEqual(result["finalizedEpoch"],2)
        self.assertTrue(result["finalityObserved"])
        self.assertTrue(result["validatorMembership"]["activeConsensusValidatorObserved"])
        self.assertFalse(result["testEthHasRealEconomicSybilResistance"])
        self.assertFalse(result["externalPeerReachabilityVerified"])
        self.assertFalse(result["ethereumTransactionsSent"])

    def test_pending_validator_does_not_inherit_active_role(self):
        def pending(path):
            if path.startswith("/eth/v1/beacon/states/head/validators/"):
                return {"data":{"status":"pending_queued"}}
            return beacon(path)
        result=observe(execution_url="http://127.0.0.1:32000",
                       beacon_url="http://127.0.0.1:33000",
                       validator_pubkey=VALIDATOR,execution_call=execution,
                       beacon_get=pending)
        self.assertFalse(result["validatorMembership"]["activeConsensusValidatorObserved"])

    def test_bad_genesis_or_wrong_chain_rejected(self):
        with self.assertRaises(HealthError):
            observe(execution_url="http://127.0.0.1:32000",
                    beacon_url="http://127.0.0.1:33000",
                    expected_genesis="0x"+"ef"*32,
                    execution_call=execution,beacon_get=beacon)
        def wrong(method,params):
            if method=="eth_chainId":return "0x7a6a"
            return execution(method,params)
        with self.assertRaises(HealthError):
            observe(execution_url="http://127.0.0.1:32000",
                    beacon_url="http://127.0.0.1:33000",
                    execution_call=wrong,beacon_get=beacon)

    def test_nonfinalized_devnet_not_described_as_final(self):
        def early(path):
            if path.endswith("/finality_checkpoints"):
                return {"data":{"finalized":{"epoch":"0","root":"0x"+"00"*32}}}
            return beacon(path)
        with self.assertRaises(HealthError):
            observe(execution_url="http://127.0.0.1:32000",
                    beacon_url="http://127.0.0.1:33000",
                    require_finality=True,execution_call=execution,beacon_get=early)

    def test_existing_tailnet_not_an_rpc_requirement(self):
        self.assertEqual(safe_url("http://127.0.0.1:32000"),
                         "http://127.0.0.1:32000")
        with self.assertRaises(HealthError):
            safe_url("http://100.65.29.101:8545")
        with self.assertRaises(HealthError):
            safe_url("http://203.0.113.2:8545")

    def test_contracts_linked_on_chain31339_and_positive_bond(self):
        result=attest(rpc_url="http://127.0.0.1:32000",
                      committee=POOL,settlement=SETTLEMENT,board=BOARD,
                      expected_sha=SHA,call=on_chain)
        self.assertTrue(result["bindingsVerified"])
        self.assertEqual(result["minimumMonitorBondTestWei"],10**15)
        self.assertFalse(result["globalMerkleElectionEnabled"])
        self.assertFalse(result["sourceBytecodeEquivalenceVerified"])
        self.assertFalse(result["physicalSLAExecutionVerified"])

    def test_wrong_chain_never_described_as_our_pos_network(self):
        def wrong(method,params):
            if method=="eth_chainId":return "0x7a6a"
            return on_chain(method,params)
        with self.assertRaises(AttestError):
            attest(rpc_url="http://127.0.0.1:32000",
                   committee=POOL,settlement=SETTLEMENT,board=BOARD,
                   expected_sha=SHA,call=wrong)

    def test_foundry_deployment_public_roles_no_external_key(self):
        code=(ROOT/"script"/"DeploySSEPos.s.sol").read_text()
        for required in ("OWN_SSE_POS_CHAIN = 31339","new SSESettlement",
                         "new OpenResourceBoard","new OpenMonitorCommittee",
                         "bindSettlement","enableDelayedBlockEntropy",
                         "bindResourceBoard","vm.startBroadcast()",
                         "vm.stopBroadcast()"):
            self.assertIn(required,code)
        self.assertNotIn("privateKey =",code)
        self.assertNotIn("0xac0974",code)

    def test_foundry_dependency_is_pinned_in_github(self):
        # The source tree is private and fresh VMs had NO lib/forge-std.
        # A GitHub-tracked gitlink, not a local untracked install, is
        # needed for reproducible Forge tests and on-chain deployment.
        import subprocess
        modules=(ROOT/".gitmodules").read_text()
        self.assertIn("path = lib/forge-std",modules)
        self.assertIn("https://github.com/foundry-rs/forge-std.git",modules)
        proc=subprocess.run(
            ["git","ls-tree","HEAD","lib/forge-std"],cwd=ROOT,
            capture_output=True,text=True,timeout=10,check=True
        )
        self.assertIn(
            "160000 commit f3dae6e6ee381f25eb6a246f7da9b85c91a68219",
            proc.stdout
        )

    def test_wallet_is_encrypted_no_real_eth(self):
        p=wallet_plan("faucet")
        self.assertFalse(p["walletCreated"])
        self.assertFalse(p["consensusValidatorKey"])
        self.assertFalse(p["privateKeyPrinted"])
        with self.assertRaises(WalletError):
            wallet_plan("validator; rm -rf /")

if __name__=="__main__":
    unittest.main()
