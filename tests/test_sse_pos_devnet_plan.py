"""SSE own PoS chain31339: zero purchased ETH and protected genesis."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_pos_devnet_plan import _render,plan,apply,DevnetError,UPSTREAM_COMMIT

FAUCET="0x"+"12"*20
MNEMONIC=" ".join(["secret"]*24)

class OwnPoSNetworkTests(unittest.TestCase):
    def test_bespoke_consensus_not_four_permissioned_qbft(self):
        p=plan(faucet=FAUCET)
        self.assertEqual(p["chainId"],31339)
        self.assertEqual(p["underlyingConsensus"],"ETHEREUM_PROOF_OF_STAKE")
        self.assertTrue(p["chainIndependentOfEthereumMainnet"])
        self.assertFalse(p["usesRealEthereum"])
        self.assertEqual(p["minimumValidatorDepositTestEth"],32)
        self.assertEqual(p["initialBootstrapValidators"],64)
        self.assertFalse(p["publicParticipationValidated"])
        self.assertFalse(p["permissionlessEconomicSybilResistanceProved"])
        self.assertEqual(len(p["upstreamCommit"]),40)
        self.assertEqual(p["upstreamCommit"],UPSTREAM_COMMIT)

    def test_render_has_secure_nonpublic_bootstrap_and_funded_test_eoa(self):
        text=_render(faucet=FAUCET,participants=2,validators_per_node=32,
                     enclave="sse-pos-research01",mnemonic=MNEMONIC,public_p2p=False)
        for required in (
            'network_id: "31339"','1000000ETH',
            'validator_count: 32',"preregistered_validator_count: 0",
            'preregistered_validator_keys_mnemonic: "',"cl_type: lighthouse",
            "el_type: besu","sigp/lighthouse:v8.3.3",
            "hyperledger/besu:26.11.1@sha256:",
            "fulu_fork_epoch: 18446744073709551615",
            "port_publisher:","    enabled: false",
        ):
            self.assertIn(required,text)
        self.assertNotIn("giant issue aisle success",text)
        self.assertNotIn("31338",text)
        self.assertNotIn("31337",text)

    def test_rejects_invalid_or_unknown_admin_gate(self):
        for argument in (
            {"faucet":"0x"+"00"*20}, {"faucet":"no-account"},
            {"participants":0}, {"validators_per_node":0},
            {"enclave":"qbft-admin"}, {"public_p2p":"yes"},
        ):
            args={"faucet":FAUCET,**argument}
            with self.subTest(args=args),self.assertRaises(DevnetError):
                plan(**args)

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "owner-only POSIX keystore and secret ACL")
    def test_generate_once_never_overwrite_protected_genesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            os.chmod(base,0o700)
            with patch("eth_account.Account.create_with_mnemonic",return_value=(None,MNEMONIC)):
                m=apply(directory=base,faucet=FAUCET,participants=2)
            self.assertTrue(m["networkConfigCreated"])
            self.assertFalse(m["walletKeysPrinted"])
            self.assertFalse(m["ethereumTransactionsSent"])
            self.assertEqual((base/"network_params.yaml").stat().st_mode&0o777,0o600)
            self.assertEqual((base/"manifest.json").stat().st_mode&0o777,0o600)
            self.assertNotIn(MNEMONIC,(base/"manifest.json").read_text())
            with self.assertRaises(DevnetError):
                apply(directory=base,faucet=FAUCET)

    def test_no_silent_docker_and_no_destructive_reset(self):
        script=(ROOT/"scripts"/"sse_pos_launch.sh").read_text()
        self.assertIn('MODE="${1:---plan}"',script)
        self.assertIn('git -C "$SSE_POS_UPSTREAM_DIR" rev-parse HEAD',script)
        self.assertIn("kurtosis run --enclave",script)
        self.assertNotIn("git reset --hard",script)
        self.assertNotIn("git clean -fd",script)
        self.assertNotIn("kurtosis enclave rm",script)
        self.assertNotIn("sudo docker",script)

if __name__=="__main__":
    unittest.main()
