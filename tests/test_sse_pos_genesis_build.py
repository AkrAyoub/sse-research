"""R25 genesis parser security fixtures. No real validator or network simulated."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sse_pos_genesis_contributions import SCHEMA, CeremonyError, collect
from sse_pos_genesis_build import (
    GenesisBuildError, input_review, check_el_genesis,
    check_consensus_config, checked_generator, main,
)


class GenesisRealBuilderPreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.deposit = "0x" + "d" * 40
        self.el = self.dir / "el.json"
        self.cl = self.dir / "cl.yaml"
        self.contrib = self.dir / "real-key-fixture-not-for-genesis.json"
        # Fixture addresses, fake BLS-shaped keys, and balances below are
        # SYNTHETIC UNIT TEST DATA ONLY, never accepted as real custody.
        self.exec = {
            "config": {
                "chainId": 31340,
                "terminalTotalDifficulty": 0,
                "terminalTotalDifficultyPassed": True,
                "depositContractAddress": self.deposit,
                "shanghaiTime": 0, "cancunTime": 0,
                "pragueTime": 0, "osakaTime": 0,
            },
            "nonce": "0x0", "difficulty": "0x0",
            "gasLimit": "0x1c9c380",
            "alloc": {},
        }
        self.consensus = {
            "PRESET_BASE": "mainnet",
            "GENESIS_FORK_VERSION": "0xc0de0001",
            "GENESIS_DELAY": "0",
            "MIN_GENESIS_ACTIVE_VALIDATOR_COUNT": "2",
            "SECONDS_PER_SLOT": "12",
            "DEPOSIT_CHAIN_ID": "31340",
            "DEPOSIT_CONTRACT_ADDRESS": self.deposit,
            "TERMINAL_TOTAL_DIFFICULTY": "0",
        }
        self.write()
        validators = [
            {
                "pubkey": "0x" + f"{i+1:096x}",
                "withdrawalCredentials": "0x01" + "00" * 11 + "aa" * 20,
                "balanceGwei": 32000000000,
            }
            for i in range(2)
        ]
        self.contrib.write_text(json.dumps({
            "schema": SCHEMA, "operatorId": "operator-own-one",
            "validators": validators,
        }), encoding="utf-8")

    def write(self):
        self.el.write_text(json.dumps(self.exec), encoding="utf-8")
        self.cl.write_text(
            "\n".join(f"{k}: {v}" for k, v in self.consensus.items()) + "\n",
            encoding="utf-8",
        )

    def review(self):
        return input_review(
            self.el, self.cl, [self.contrib],
            min_validators=2, min_operators=1, single_operator_lab=True
        )

    def test_valid_syntactic_inputs_still_report_unverified_and_lab_only(self):
        report, listing = self.review()
        self.assertEqual(report["intendedChainId"], 31340)
        self.assertEqual(report["publicValidatorKeys"], 2)
        self.assertEqual(report["declaredOperators"], 1)
        self.assertEqual(report["mode"], "single-real-operator-LAB-only")
        self.assertFalse(report["independentAdministratorsVerified"])
        self.assertFalse(report["blsPubkeySubgroupAndPossessionVerified"])
        self.assertFalse(report["permissionlessPublicNetworkReady"])
        self.assertEqual(len(listing.splitlines()), 2)

    def test_multioperator_genesis_threshold_is_not_a_fixed_roster_size(self):
        # Three public fixture files with min_operators=2 is valid.
        # No actual independent people or real BLS custody are asserted.
        sources = [self.contrib]
        for i in (2, 3):
            d = json.loads(self.contrib.read_text())
            d["operatorId"] = f"operator-number-{i}"
            for j, v in enumerate(d["validators"]):
                v["pubkey"] = "0x" + f"{i*100+j+1:096x}"
                v["withdrawalCredentials"] = (
                    "0x01" + "00" * 11 + f"{i+1:040x}"
                )
            p = self.dir / f"operator-{i}.json"
            p.write_text(json.dumps(d), encoding="utf-8")
            sources.append(p)
        report, listing = input_review(
            self.el, self.cl, sources,
            min_operators=2, min_validators=2,
            single_operator_lab=False
        )
        self.assertEqual(report["declaredOperators"], 3)
        self.assertEqual(report["publicValidatorKeys"], 6)
        self.assertFalse(report["permissionlessPublicNetworkReady"])
        self.assertEqual(len(listing.splitlines()), 6)

    def test_one_operator_requires_explicit_lab_flag_never_default_independence(self):
        with self.assertRaises(CeremonyError):
            collect([self.contrib], min_operators=1, min_validators=2)
        text, review = collect(
            [self.contrib], min_operators=1, min_validators=2,
            single_operator_lab=True
        )
        self.assertEqual(len(text.splitlines()), 2)
        self.assertTrue(review["singleOperatorLabOnly"])
        self.assertFalse(review["publicMultioperatorNetworkReady"])
        with self.assertRaises(CeremonyError):
            collect([self.contrib], min_operators=2, min_validators=2,
                    single_operator_lab=True)

    def test_cli_read_only_inspect_writes_no_genesis(self):
        argv = [
            "--eth1-genesis", str(self.el),
            "--consensus-config", str(self.cl),
            "--contribution", str(self.contrib),
            "--min-operators", "1", "--min-validators", "2",
            "--single-operator-lab", "--inspect",
        ]
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(main(argv), 0)
        report = json.loads(out.getvalue())
        self.assertFalse(report["consensusGenesisSszGeneratedByPinnedRealBinary"])
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                         sorted([self.el.name, self.cl.name, self.contrib.name]))

    def test_refuses_old_or_wrong_chain_and_permissioned_genesis(self):
        for chain in (31339, 1, 31338, 0):
            self.exec["config"]["chainId"] = chain
            self.write()
            with self.subTest(chain=chain), self.assertRaises(GenesisBuildError):
                self.review()
        self.exec["config"]["chainId"] = 31340
        self.exec["config"]["qbft"] = {"blockperiodseconds": 2}
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()

    def test_bad_deposit_contract_or_el_cl_mismatch_refused(self):
        self.consensus["DEPOSIT_CONTRACT_ADDRESS"] = "0x" + "e" * 40
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()
        self.consensus["DEPOSIT_CONTRACT_ADDRESS"] = self.deposit
        self.exec["config"]["depositContractAddress"] = "0x" + "0" * 40
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()

    def test_duplicate_json_properties_and_secret_bearing_fields_rejected(self):
        blob = b'{"config":{"chainId":31340,"chainId":31339}}'
        with self.assertRaises(GenesisBuildError):
            check_el_genesis(blob)
        self.exec["privateKey"] = "SENSITIVE"
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()

    def test_duplicate_yaml_keys_refused(self):
        self.write()
        with self.cl.open("a") as out:
            out.write("DEPOSIT_CHAIN_ID: 31339\n")
        with self.assertRaises(GenesisBuildError):
            self.review()

    def test_fork_chain_or_validator_minimum_mismatch_refused(self):
        self.consensus["MIN_GENESIS_ACTIVE_VALIDATOR_COUNT"] = "3"
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()
        self.consensus["MIN_GENESIS_ACTIVE_VALIDATOR_COUNT"] = "2"
        self.consensus["GENESIS_FORK_VERSION"] = "0x00000000"
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()
        self.consensus["GENESIS_FORK_VERSION"] = "0xc0de0001"
        self.consensus["DEPOSIT_CHAIN_ID"] = "1"
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()

    def test_no_arbitrary_accelerated_slot_time_or_mining_protocol(self):
        self.consensus["SECONDS_PER_SLOT"] = "2"
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()
        self.consensus["SECONDS_PER_SLOT"] = "12"
        self.exec["difficulty"] = "0x1"
        self.write()
        with self.assertRaises(GenesisBuildError):
            self.review()

    def test_tampered_unverified_generator_rejected_without_execution(self):
        path = self.dir / "eth-genesis-state-generator"
        path.write_bytes(b"NOT A PINNED REAL GENERATOR")
        path.chmod(0o755)
        with self.assertRaises(GenesisBuildError):
            checked_generator(path)
        self.assertEqual(path.read_bytes(), b"NOT A PINNED REAL GENERATOR")

    def test_out_of_range_duplicate_operators_and_fake_distinct_owners_rejected(self):
        with self.assertRaises(GenesisBuildError):
            input_review(self.el, self.cl, [self.contrib],
                         min_validators=2, min_operators=2, single_operator_lab=False)
        with self.assertRaises(CeremonyError):
            collect([self.contrib, self.contrib], min_operators=2, min_validators=2)
        with self.assertRaises(CeremonyError):
            collect([self.contrib, self.contrib], min_operators=1,
                    min_validators=2, single_operator_lab=True)

    def test_lab_build_cannot_be_activated_without_reviewed_command(self):
        argv = [
            "--eth1-genesis", str(self.el), "--consensus-config", str(self.cl),
            "--contribution", str(self.contrib), "--min-operators", "1",
            "--min-validators", "2", "--single-operator-lab",
            "--build-single-operator-lab",
        ]
        with redirect_stdout(StringIO()):
            self.assertEqual(main(argv), 2)
        self.assertFalse((self.dir / "genesis.ssz").exists())


if __name__ == "__main__":
    unittest.main()
