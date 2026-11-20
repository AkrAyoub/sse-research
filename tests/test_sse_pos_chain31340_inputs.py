"""R34 PUBLIC input builders - synthetic source fixtures only, no validator keys created."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sse_pos_chain31340_inputs import (
    Chain31340InputError, DEPOSIT, EXPECTED_SYSTEM, MAX_UINT64,
    consensus_lines, render_public_inputs, system_predeploys, verify_fork_pair,
)
from sse_pos_genesis_build import check_el_genesis, check_consensus_config
from sse_pos_deposit_predeploy import validate_predeploy

class PublicNativeGenesisSourceTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.contrib = self.root / "synthetic-public-keys-ONLY.json"
        self.eoa = "0x" + "ab" * 20
        self.contrib.write_text(json.dumps({
            "schema": "SSE_R20_PUBLIC_GENESIS_VALIDATORS_V1",
            "operatorId": "operator-own-one",
            "validators": [{
                "pubkey": "0x" + "11" * 48,
                "withdrawalCredentials": "0x01" + "00" * 11 + self.eoa[2:],
                "balanceGwei": 32000000000,
            }],
        }), encoding="utf-8")

    def render(self):
        return render_public_inputs(
            public_contribution=self.contrib, owner_eoa=self.eoa,
            genesis_time=2000000400, initial_supply_test_eth=1000000)

    def files(self, el, cl):
        e, c = self.root / "genesis.json", self.root / "config.yaml"
        e.write_text(json.dumps(el), encoding="utf-8")
        c.write_text(cl, encoding="utf-8")
        return e, c

    def test_real_upstream_ungated_predeploys_at_required_fork_addresses(self):
        sys_contracts = system_predeploys()
        self.assertEqual(len(sys_contracts), 4)
        self.assertEqual(set(a.lower() for a in sys_contracts),
                         set(a.lower() for a in EXPECTED_SYSTEM.values()))
        for a in sys_contracts.values():
            self.assertTrue(a["code"].startswith("0x"))
            self.assertEqual(a["nonce"], "1")

    def test_paired_el_cl_public_config_passes_builder_and_deposit_reference(self):
        el, cl, report = self.render()
        ep, cp = self.files(el, cl)
        parsed = check_el_genesis(ep.read_bytes())
        self.assertEqual(parsed["osakaTime"], None)
        checked = check_consensus_config(cp.read_bytes(), parsed, 1)
        self.assertEqual(checked["consensusForkEpochs"]["FULU"], MAX_UINT64)
        self.assertTrue(validate_predeploy(ep, DEPOSIT)["depositConstructorZeroHashesVerified"])
        self.assertTrue(verify_fork_pair(ep, cp)["osakaAndFuluNotScheduled"])
        self.assertEqual(report["declaredIndependentOperatorFaultDomains"], 1)
        self.assertFalse(report["livePoSFinalityVerified"])

    def test_parity_fails_if_ethereum_fulu_or_osaka_activates_without_pair(self):
        el, cl, _ = self.render()
        el["config"]["osakaTime"] = 0
        ep, cp = self.files(el, cl)
        with self.assertRaisesRegex(Chain31340InputError, "fork pair"):
            verify_fork_pair(ep, cp)
        del el["config"]["osakaTime"]
        cl = cl.replace(f"FULU_FORK_EPOCH: {MAX_UINT64}", "FULU_FORK_EPOCH: 0")
        ep, cp = self.files(el, cl)
        with self.assertRaisesRegex(Chain31340InputError, "fork pair"):
            verify_fork_pair(ep, cp)

    def test_no_arbitrary_mnemonics_or_new_signing_keys_in_public_artifacts(self):
        el, cl, _ = self.render()
        full = json.dumps(el) + cl
        for token in ("mnemonic", "privateKey", "jwtSecret", "signingKey"):
            self.assertNotIn(token, full)
        self.assertEqual(el["alloc"][self.eoa]["balance"], str(1000000 * 10**18))
        self.assertEqual(el["config"]["chainId"], 31340)
        self.assertEqual(el["config"]["pragueTime"], 0)

    def test_real_owner_withdrawal_eoa_must_match_single_contribution(self):
        with self.assertRaisesRegex(Chain31340InputError, "withdrawal credentials mismatch"):
            render_public_inputs(public_contribution=self.contrib,
                                 owner_eoa="0x" + "ef" * 20,
                                 genesis_time=2000000400, initial_supply_test_eth=1)

    def test_independent_operators_not_claimed_and_no_network_role_cap(self):
        el, cl, report = self.render()
        self.assertFalse(report["trueIndependentOperatorsVerified"])
        self.assertFalse(report["publicOutsidePeerVerified"])
        self.assertEqual(report["publicValidatorsCount"], 1)
        self.assertNotIn("MAX_NETWORK_VALIDATORS", cl)
        self.assertNotIn("validator-whitelist", json.dumps(el))

    def test_invalid_nonpositive_or_excessive_funding_refused(self):
        for amount in (0, 10000001, -1):
            with self.subTest(amount=amount), self.assertRaisesRegex(Chain31340InputError, "finite initial TEST ETH"):
                render_public_inputs(public_contribution=self.contrib,
                                     owner_eoa=self.eoa, genesis_time=2000000400,
                                     initial_supply_test_eth=amount)

    def test_only_future_genesis_time_accepted(self):
        with self.assertRaisesRegex(Chain31340InputError, "genesis time"):
            consensus_lines(genesis_time=42, count=1)
        self.assertIn("MIN_GENESIS_TIME: 2000000400", consensus_lines(genesis_time=2000000400, count=1))

    def test_deliberate_single_validator_fixture_never_masquerades_as_live(self):
        el, cl, report = self.render()
        self.assertFalse(report["blsPublicSubgroupVerified"])
        self.assertFalse(report["authenticDepositContractExecutionVerified"])
        self.assertFalse(report["chainStarted"])
        self.assertEqual(report["genesisFork"],
                         "Electra/Prague at epoch zero; Fulu/Osaka not scheduled")


if __name__ == "__main__":
    unittest.main()
