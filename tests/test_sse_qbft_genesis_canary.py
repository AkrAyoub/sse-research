"""Static canary isolation contract: no validator secrets, P2P or legacy Anvil."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class GenesisCanaryTests(unittest.TestCase):
    def test_disposable_canary_cannot_contact_p2p_or_anvil(self):
        text=(ROOT/"infra"/"qbft-multivm"/"genesis-canary.compose.yaml").read_text()
        self.assertIn("--p2p-enabled=false",text)
        self.assertIn("--discovery-enabled=false",text)
        self.assertIn("--network-id=31338",text)
        self.assertIn("--rpc-http-host=127.0.0.1",text)
        self.assertIn("--rpc-http-port=18559",text)
        # A real VM4704 run on 2026-11-18 failed because Docker's
        # noexec tmpfs prevented loading libjnidispatch / Netty .so.
        self.assertIn("/tmp:rw,exec,nosuid,nodev,size=512m,mode=1777",text)
        self.assertIn("cap_drop: [ALL]",text)
        self.assertIn("no-new-privileges:true",text)
        self.assertIn("read_only: true",text)
        self.assertIn("restart: \"no\"",text)
        self.assertNotIn("--node-private-key-file=",text)
        self.assertNotIn("--bootnodes=",text)
        self.assertNotIn("8545",text)
        self.assertNotIn("31337",text)

    def test_later_genuine_network_requires_signed_peer_catalog(self):
        runbook=(ROOT/"infra"/"qbft-multivm"/"README.md").read_text()
        self.assertIn("genesis-canary.compose.yaml",runbook)
        self.assertIn("actual **block-zero hash**",runbook)
        self.assertIn("bootnodes.txt",runbook)
        self.assertIn("sse_qbft_fleet_evidence.py audit",runbook)
        self.assertIn("sse_qbft_readiness.py --require-four",runbook)


if __name__=="__main__":
    unittest.main()
