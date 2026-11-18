"""Static checks for QBFT laboratory; does not require Docker or RPC."""
import importlib.util
import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1] / "infra" / "qbft-lab"
SPEC = importlib.util.spec_from_file_location("qbft_lab", BASE / "qbft_lab.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class QBFTLabConfigTest(unittest.TestCase):
    def test_network_parameters(self):
        config = json.loads((BASE / "qbft-config.json").read_text())
        genesis = config["genesis"]
        qbft = genesis["config"]["qbft"]
        self.assertEqual(config["blockchain"]["nodes"]["count"], 4)
        self.assertEqual(genesis["config"]["chainId"], MOD.CHAIN_ID)
        self.assertEqual(qbft["requesttimeoutseconds"],
                         2 * qbft["blockperiodseconds"])
        self.assertEqual(int(genesis["gasLimit"], 16), 10_000_000)
        self.assertTrue(genesis["config"]["zeroBaseFee"])
        self.assertEqual(MOD.PORTS, (18545, 18546, 18547, 18548))

    def test_key_normalization(self):
        key = "ab" * 64
        self.assertEqual(MOD.normalize_public_key(key), key)
        self.assertEqual(MOD.normalize_public_key("0x04" + key), key)
        self.assertEqual(MOD.normalize_public_key(key.upper()), key)
        for invalid in ("", "abcd", "a" * 127, "z" * 128):
            with self.assertRaises(ValueError):
                MOD.normalize_public_key(invalid)

    def test_compose_separation_and_local_rpc(self):
        keys = [f"{i:02x}" * 64 for i in range(1, 5)]
        contents = MOD.make_compose(keys, 1000, 1000)
        self.assertEqual(contents.count("image: hyperledger/besu:26.6.1"), 4)
        self.assertEqual(contents.count("127.0.0.1:"), 4)
        self.assertEqual(contents.count("--bootnodes="), 4)
        for port in MOD.PORTS:
            self.assertIn(f"127.0.0.1:{port}:8545", contents)
        for i in range(1, 5):
            self.assertIn("validator" + str(i) + "/data:/data", contents)
        with self.assertRaises(ValueError):
            MOD.make_compose([keys[0]] * 4, 1000, 1000)


if __name__ == "__main__":
    unittest.main()
