"""Local unit fixtures ONLY. Fictitious pubkeys are never genesis keys."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_pos_genesis_contributions import (
    SCHEMA, CeremonyError, collect, read_contribution, main,
)


class GenesisPublicContributionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def contribution(self, number, keys=1, mutate=None):
        file = self.dir / f"contribution-{number}.json"
        payload = {
            "schema": SCHEMA,
            "operatorId": f"operator-{number}",
            "validators": [
                {
                    "pubkey": "0x" + f"{number * 10000 + i + 1:096x}",
                    "withdrawalCredentials": "0x01" + "00" * 11 + f"{number + 1:040x}",
                    "balanceGwei": 32_000_000_000,
                } for i in range(keys)
            ],
        }
        if mutate:
            mutate(payload)
        file.write_text(json.dumps(payload), encoding="utf-8")
        return file

    def test_multioperator_public_only_collection(self):
        files = [self.contribution(i, keys=16) for i in range(4)]
        listing, review = collect(files)
        self.assertEqual(len(listing.splitlines()), 64)
        self.assertEqual(review["declaredOperators"], 4)
        self.assertEqual(review["publicValidatorKeys"], 64)
        self.assertFalse(review["containsPrivateKeys"])
        self.assertFalse(review["blsProofOfPossessionVerified"])
        self.assertFalse(review["operatorPhysicalIndependenceVerified"])
        self.assertFalse(review["readyToLaunch"])
        self.assertNotIn("mnemonic", listing.lower())
        self.assertNotIn("private", listing.lower())

    def test_deterministic_public_list_digest_independent_of_file_order(self):
        files = [self.contribution(i, keys=2) for i in range(4)]
        a, ra = collect(files, min_validators=8)
        b, rb = collect(list(reversed(files)), min_validators=8)
        self.assertEqual(a, b)
        self.assertEqual(ra["publicValidatorListSha256"], rb["publicValidatorListSha256"])

    def test_fewer_distinct_genesis_operators_fails_closed(self):
        files = [self.contribution(i, keys=16) for i in range(3)]
        with self.assertRaises(CeremonyError):
            collect(files)
        with self.assertRaises(CeremonyError):
            collect(files, min_operators=1)

    def test_duplicate_operator_label_rejected(self):
        files = [self.contribution(i) for i in range(4)]
        contents = json.loads(files[1].read_text())
        contents["operatorId"] = "operator-0"
        files[1].write_text(json.dumps(contents))
        with self.assertRaises(CeremonyError):
            collect(files, min_validators=4)

    def test_same_key_or_same_withdrawal_address_across_operators_rejected(self):
        files = [self.contribution(i) for i in range(4)]
        bad = json.loads(files[1].read_text())
        good = json.loads(files[0].read_text())
        bad["validators"][0]["pubkey"] = good["validators"][0]["pubkey"]
        files[1].write_text(json.dumps(bad))
        with self.assertRaises(CeremonyError):
            collect(files, min_validators=4)
        bad["validators"][0]["pubkey"] = "0x" + f"{90000:096x}"
        bad["validators"][0]["withdrawalCredentials"] = good["validators"][0]["withdrawalCredentials"]
        files[1].write_text(json.dumps(bad))
        with self.assertRaises(CeremonyError):
            collect(files, min_validators=4)

    def test_secret_bearing_fields_and_unknown_keys_rejected(self):
        for forbidden in ("mnemonic", "privateKey", "keystore", "validatorPassword"):
            file = self.contribution(0)
            payload = json.loads(file.read_text())
            payload[forbidden] = "DO_NOT_PUBLISH"
            file.write_text(json.dumps(payload))
            with self.subTest(field=forbidden), self.assertRaises(CeremonyError):
                read_contribution(file)

    def test_wrong_balance_bool_or_invalid_bls_key_rejected(self):
        for value in (0, 31_000_000_000, True, "32000000000"):
            def mutate(p):
                p["validators"][0]["balanceGwei"] = value
            file = self.contribution(0, mutate=mutate)
            with self.subTest(balance=value), self.assertRaises(CeremonyError):
                read_contribution(file)
        for key in ("0x" + "0" * 96, "0x1234", "0x" + "g" * 96):
            file = self.contribution(0, mutate=lambda p: p["validators"][0].update(pubkey=key))
            with self.subTest(key=key[:10]), self.assertRaises(CeremonyError):
                read_contribution(file)

    def test_withdrawal_credentials_must_be_nonzero_el_address(self):
        invalid = [
            "0x00" + "00" * 11 + "22" * 20,
            "0x01" + "00" * 11 + "00" * 20,
            "0x02" + "00" * 11 + "22" * 20,
        ]
        for cred in invalid:
            file = self.contribution(0, mutate=lambda p: p["validators"][0].update(withdrawalCredentials=cred))
            with self.subTest(cred=cred[:6]), self.assertRaises(CeremonyError):
                read_contribution(file)

    def test_duplicate_json_keys_rejected(self):
        file = self.dir / "duplicate.json"
        file.write_text(
            '{"schema":"' + SCHEMA + '","operatorId":"operator-a",'
            '"operatorId":"operator-b","validators":[]}', encoding="utf-8")
        with self.assertRaises(CeremonyError):
            read_contribution(file)

    def test_output_file_create_only_and_not_genesis(self):
        files = [self.contribution(i) for i in range(4)]
        dest = self.dir / "validators.txt"
        cmd = sum((["--contribution", str(p)] for p in files), [])
        cmd += ["--min-validators", "4", "--output", str(dest)]
        with redirect_stdout(StringIO()):
            self.assertEqual(main(cmd), 0)
        self.assertEqual(len(dest.read_text().splitlines()), 4)
        with redirect_stdout(StringIO()):
            self.assertEqual(main(cmd), 2)

    def test_public_list_format_matches_official_generator(self):
        files = [self.contribution(i) for i in range(4)]
        listing, result = collect(files, min_validators=4)
        for line in listing.splitlines():
            pub, wd, balance = line.split(":")
            self.assertTrue(pub.startswith("0x"))
            self.assertEqual(len(pub), 98)
            self.assertEqual(len(wd), 64)
            self.assertEqual(balance, "32000000000")
        self.assertFalse(result["consensusGenesisSszBuilt"])

    def test_existing_tampered_generator_rejected_without_download(self):
        # A repeat installer invocation must never accept a modified binary,
        # nor try to download/overwrite existing content.
        script = ROOT / "scripts" / "r20_install_beacon_genesis_generator.sh"
        home = self.dir / "isolated-home"
        destination = (home / ".local" / "share" / "sse-r19-toolchains"
                       / "eth-beacon-genesis-v0.0.8")
        destination.mkdir(parents=True)
        binary = destination / "eth-genesis-state-generator"
        binary.write_bytes(b"NOT THE VERIFIED GENESIS GENERATOR")
        binary.chmod(0o755)
        p = subprocess.run(
            ["bash", str(script)],
            env={**os.environ, "HOME": str(home)},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(p.returncode, 2)
        self.assertIn("expected generator binary SHA256 mismatch", p.stderr)
        self.assertNotIn("R20_RELEASE_URL=", p.stdout)
        self.assertEqual(binary.read_bytes(), b"NOT THE VERIFIED GENESIS GENERATOR")

    def test_generator_installer_reuses_only_verified_existing_binary(self):
        src = (ROOT / "scripts" / "r20_install_beacon_genesis_generator.sh").read_text()
        self.assertIn(
            'BIN_SHA256="5ee29389cb29e8a1ace8cfc83ff30a1726409152e88cf07681764740ca9244d2"',
            src,
        )
        self.assertIn("R20_GENESIS_TOOL_REUSED_VERIFIED=true", src)
        self.assertIn('verify_binary "$DEST/eth-genesis-state-generator"', src)
        self.assertIn('verify_binary "$STAGE/eth-genesis-state-generator"', src)
        self.assertIn("R20_GENESIS_BINARY_SHA256_VERIFIED=true", src)
        self.assertIn("sha256sum --check --status", src)
        self.assertIn("R20_GENESIS_SSZ_GENERATED=false", src)
        self.assertIn("R20_PUBLIC_POS_NETWORK_DEPLOYED=false", src)
        self.assertEqual(
            subprocess.run(["bash", "-n", str(ROOT / "scripts" / "r20_install_beacon_genesis_generator.sh")],
                           check=False, timeout=10).returncode,
            0,
        )

    def test_no_shared_seed_generator_script(self):
        src = (ROOT / "scripts" / "r20_install_beacon_genesis_generator.sh").read_text()
        self.assertIn("73b5e33ed309e7bd98bd5f115b032a462b7ed8f1b67b204ac2000016c2f1856b", src)
        self.assertIn("sha256sum --check --status", src)
        self.assertIn('tar -xzOf "$ARCHIVE"', src)
        self.assertNotIn("curl -sL | bash", src)
        self.assertIn("R20_PUBLIC_POS_NETWORK_DEPLOYED=false", src)

if __name__ == "__main__":
    unittest.main()
